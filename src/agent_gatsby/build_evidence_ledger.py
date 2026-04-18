"""
Verified evidence ledger construction for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from agent_gatsby.config import AppConfig
from agent_gatsby.extract_metaphors import load_metaphor_candidates
from agent_gatsby.index_text import load_passage_index
from agent_gatsby.schemas import EvidenceRecord, MetaphorCandidate, PassageIndex, PassageRecord, RejectedCandidate

LOGGER = logging.getLogger(__name__)

DEFAULT_MANUAL_OVERRIDE_PATH = "artifacts/evidence/manual_overrides.json"


class ManualEvidenceOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metaphor: str
    passage_id: str
    quote: str
    interpretation: str
    supporting_theme_tags: list[str] = Field(default_factory=list)


def collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def normalize_label(label: str) -> str:
    return collapse_spaces(label).strip().lower()


def rationale_is_too_vague(rationale: str) -> bool:
    normalized = collapse_spaces(rationale).strip()
    if len(normalized) < 20:
        return True
    if len(normalized.split()) < 5:
        return True
    if normalized.lower() in {"important symbol", "important metaphor", "metaphor", "symbol"}:
        return True
    return False


def build_passage_lookup(passage_index: PassageIndex) -> dict[str, PassageRecord]:
    return {passage.passage_id: passage for passage in passage_index.passages}


def candidate_rejection(candidate: MetaphorCandidate, reason: str) -> RejectedCandidate:
    return RejectedCandidate(
        candidate_id=candidate.candidate_id,
        reason=reason,
        passage_id=candidate.passage_id,
        label=candidate.label,
        quote=candidate.quote,
    )


def validate_candidate(
    candidate: MetaphorCandidate,
    *,
    passage_lookup: dict[str, PassageRecord],
    config: AppConfig,
) -> tuple[bool, str | None, PassageRecord | None]:
    passage = passage_lookup.get(candidate.passage_id)
    if passage is None:
        return False, "Passage ID does not exist in passage index", None

    if config.evidence_ledger.get("reject_empty_rationales", True) and not candidate.rationale.strip():
        return False, "Rationale is empty", passage

    minimum_quote_length = int(config.evidence_ledger.get("minimum_quote_length", 8))
    if len(candidate.quote.strip()) < minimum_quote_length:
        return False, "Quote is too short to support analysis", passage

    if config.evidence_ledger.get("require_exact_quote_match", True) and candidate.quote not in passage.text:
        return False, "Quote does not exact-match the source passage", passage

    if rationale_is_too_vague(candidate.rationale):
        return False, "Rationale is too vague to support analysis", passage

    return True, None, passage


def promote_candidate(
    candidate: MetaphorCandidate,
    *,
    evidence_id: str,
    passage: PassageRecord,
    status: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        metaphor=normalize_label(candidate.label),
        quote=candidate.quote,
        passage_id=candidate.passage_id,
        chapter=passage.chapter,
        interpretation=collapse_spaces(candidate.rationale).strip(),
        supporting_theme_tags=[],
        status=status,
        source_candidate_id=candidate.candidate_id,
        source_type="candidate",
    )


def promote_manual_override(
    override: ManualEvidenceOverride,
    *,
    evidence_id: str,
    passage: PassageRecord,
    status: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        metaphor=normalize_label(override.metaphor),
        quote=override.quote,
        passage_id=override.passage_id,
        chapter=passage.chapter,
        interpretation=collapse_spaces(override.interpretation).strip(),
        supporting_theme_tags=override.supporting_theme_tags,
        status=status,
        source_type="manual_override",
    )


def manual_override_path(config: AppConfig) -> Path:
    return config.resolve_repo_path(DEFAULT_MANUAL_OVERRIDE_PATH)


def load_manual_overrides(config: AppConfig) -> list[ManualEvidenceOverride]:
    path = manual_override_path(config)
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Manual override file at {path} must contain a JSON array")
    return [ManualEvidenceOverride.model_validate(item) for item in data]


def write_evidence_ledger(config: AppConfig, evidence_records: list[EvidenceRecord]) -> None:
    output_path = config.evidence_ledger_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([record.model_dump() for record in evidence_records], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote %d verified evidence records to %s", len(evidence_records), output_path)


def write_rejections(config: AppConfig, rejected_candidates: list[RejectedCandidate]) -> None:
    output_path = config.rejected_candidates_path
    if not rejected_candidates:
        if output_path.exists():
            output_path.unlink()
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([record.model_dump(exclude_none=True) for record in rejected_candidates], indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote %d rejected candidates to %s", len(rejected_candidates), output_path)


def build_evidence_ledger(
    config: AppConfig,
    candidates: list[MetaphorCandidate] | None = None,
    passage_index: PassageIndex | None = None,
) -> tuple[list[EvidenceRecord], list[RejectedCandidate]]:
    loaded_candidates = candidates or load_metaphor_candidates(config)
    loaded_index = passage_index or load_passage_index(config)
    passage_lookup = build_passage_lookup(loaded_index)
    status = str(config.evidence_ledger.get("status_for_verified_entries", "verified"))

    evidence_records: list[EvidenceRecord] = []
    rejected_candidates: list[RejectedCandidate] = []

    for candidate in loaded_candidates:
        is_valid, rejection_reason, passage = validate_candidate(
            candidate,
            passage_lookup=passage_lookup,
            config=config,
        )
        if not is_valid or passage is None:
            rejected_candidates.append(candidate_rejection(candidate, rejection_reason or "Rejected"))
            continue

        evidence_records.append(
            promote_candidate(
                candidate,
                evidence_id=f"E{len(evidence_records) + 1:03d}",
                passage=passage,
                status=status,
            )
        )

    manual_overrides = load_manual_overrides(config)
    if manual_overrides:
        LOGGER.info("Applying %d manual evidence overrides from %s", len(manual_overrides), manual_override_path(config))
    for override in manual_overrides:
        passage = passage_lookup.get(override.passage_id)
        if passage is None:
            raise ValueError(f"Manual override references missing passage ID: {override.passage_id}")
        if override.quote not in passage.text:
            raise ValueError(f"Manual override quote does not exact-match passage {override.passage_id}")
        if rationale_is_too_vague(override.interpretation):
            raise ValueError(f"Manual override interpretation is too vague for passage {override.passage_id}")
        evidence_records.append(
            promote_manual_override(
                override,
                evidence_id=f"E{len(evidence_records) + 1:03d}",
                passage=passage,
                status=status,
            )
        )

    write_evidence_ledger(config, evidence_records)
    write_rejections(config, rejected_candidates)
    target_verified_record_count = int(config.evidence_ledger.get("target_verified_record_count", 0))
    if target_verified_record_count > 0:
        if len(evidence_records) < target_verified_record_count:
            LOGGER.warning(
                "Verified evidence count is below target: %d < %d. Human review or manual overrides may be needed before freezing the English master.",
                len(evidence_records),
                target_verified_record_count,
            )
        else:
            LOGGER.info(
                "Verified evidence count meets target: %d >= %d",
                len(evidence_records),
                target_verified_record_count,
            )
    LOGGER.info("Promoted %d evidence records and rejected %d candidates", len(evidence_records), len(rejected_candidates))
    return evidence_records, rejected_candidates
