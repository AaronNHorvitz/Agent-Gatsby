"""Evidence-ledger construction and candidate promotion rules.

This module validates extracted metaphor candidates against the deterministic
passage index, rejects weak or mismatched records, optionally applies manual
overrides, and writes the verified evidence ledger that all downstream English
planning and drafting stages depend on.
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
    """Manual evidence record used to supplement model extraction.

    Attributes
    ----------
    metaphor : str
        Normalized metaphor label to promote.
    passage_id : str
        Passage identifier for the source quote.
    quote : str
        Exact quote to promote from the passage.
    interpretation : str
        Short explanatory interpretation for the quote.
    supporting_theme_tags : list of str
        Optional thematic tags attached to the record.
    """

    model_config = ConfigDict(extra="forbid")

    metaphor: str
    passage_id: str
    quote: str
    interpretation: str
    supporting_theme_tags: list[str] = Field(default_factory=list)


def collapse_spaces(text: str) -> str:
    """Collapse repeated whitespace to single spaces.

    Parameters
    ----------
    text : str
        Raw text to normalize.

    Returns
    -------
    str
        Whitespace-normalized text.
    """

    return " ".join(text.split())


def normalize_label(label: str) -> str:
    """Normalize a candidate or override metaphor label.

    Parameters
    ----------
    label : str
        Raw metaphor label.

    Returns
    -------
    str
        Lowercased, whitespace-normalized label.
    """

    return collapse_spaces(label).strip().lower()


def rationale_is_too_vague(rationale: str) -> bool:
    """Return whether a rationale is too weak for promotion.

    Parameters
    ----------
    rationale : str
        Candidate rationale or manual interpretation.

    Returns
    -------
    bool
        ``True`` when the rationale is too short or too generic to support the
        evidence-ledger standard.
    """

    normalized = collapse_spaces(rationale).strip()
    if len(normalized) < 20:
        return True
    if len(normalized.split()) < 5:
        return True
    if normalized.lower() in {"important symbol", "important metaphor", "metaphor", "symbol"}:
        return True
    return False


def build_passage_lookup(passage_index: PassageIndex) -> dict[str, PassageRecord]:
    """Build a passage lookup keyed by passage identifier.

    Parameters
    ----------
    passage_index : PassageIndex
        Loaded passage index.

    Returns
    -------
    dict of str to PassageRecord
        Lookup table keyed by ``passage_id``.
    """

    return {passage.passage_id: passage for passage in passage_index.passages}


def candidate_rejection(candidate: MetaphorCandidate, reason: str) -> RejectedCandidate:
    """Build a rejected-candidate record from a failed candidate.

    Parameters
    ----------
    candidate : MetaphorCandidate
        Candidate that failed validation.
    reason : str
        Human-readable rejection reason.

    Returns
    -------
    RejectedCandidate
        Rejection record written to the rejected-candidates artifact.
    """

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
    """Validate a candidate against the passage index and ledger rules.

    Parameters
    ----------
    candidate : MetaphorCandidate
        Candidate to validate.
    passage_lookup : dict of str to PassageRecord
        Passage lookup keyed by ``passage_id``.
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    tuple of (bool, str or None, PassageRecord or None)
        Validation success flag, optional rejection reason, and the resolved
        passage record when available.
    """

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
    """Promote a validated model candidate into a verified evidence record.

    Parameters
    ----------
    candidate : MetaphorCandidate
        Validated candidate to promote.
    evidence_id : str
        New stable evidence identifier.
    passage : PassageRecord
        Source passage backing the candidate.
    status : str
        Promotion status to store on the record.

    Returns
    -------
    EvidenceRecord
        Promoted evidence record.
    """

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
    """Promote a manual override into a verified evidence record.

    Parameters
    ----------
    override : ManualEvidenceOverride
        Manual override definition.
    evidence_id : str
        New stable evidence identifier.
    passage : PassageRecord
        Source passage backing the override.
    status : str
        Promotion status to store on the record.

    Returns
    -------
    EvidenceRecord
        Promoted manual evidence record.
    """

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
    """Return the configured manual-override file path.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    Path
        Resolved manual override path.
    """

    return config.resolve_repo_path(DEFAULT_MANUAL_OVERRIDE_PATH)


def load_manual_overrides(config: AppConfig) -> list[ManualEvidenceOverride]:
    """Load manual evidence overrides from disk when present.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    list of ManualEvidenceOverride
        Loaded override records. Returns an empty list when no override file is
        present.

    Raises
    ------
    ValueError
        If the override file exists but does not contain a JSON array.
    """

    path = manual_override_path(config)
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Manual override file at {path} must contain a JSON array")
    return [ManualEvidenceOverride.model_validate(item) for item in data]


def write_evidence_ledger(config: AppConfig, evidence_records: list[EvidenceRecord]) -> None:
    """Write the evidence ledger artifact to disk.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    evidence_records : list of EvidenceRecord
        Promoted evidence records to serialize.

    Returns
    -------
    None
        The evidence ledger is written to the configured artifact path.
    """

    output_path = config.evidence_ledger_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([record.model_dump() for record in evidence_records], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote %d verified evidence records to %s", len(evidence_records), output_path)


def write_rejections(config: AppConfig, rejected_candidates: list[RejectedCandidate]) -> None:
    """Write rejected candidates to disk or remove stale rejection output.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    rejected_candidates : list of RejectedCandidate
        Rejection records to serialize.

    Returns
    -------
    None
        The rejection artifact is updated in place on disk.
    """

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
    """Validate candidates, apply overrides, and build the evidence ledger.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    candidates : list of MetaphorCandidate or None, optional
        Preloaded extraction candidates. When omitted, the stage loads the
        serialized candidate artifact from disk.
    passage_index : PassageIndex or None, optional
        Preloaded passage index. When omitted, the stage loads the serialized
        passage index from disk.

    Returns
    -------
    tuple of (list of EvidenceRecord, list of RejectedCandidate)
        Promoted evidence records and rejected candidate records.

    Raises
    ------
    ValueError
        If a manual override references a missing passage, does not exact-match
        its passage, or contains a too-vague interpretation.
    """

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
