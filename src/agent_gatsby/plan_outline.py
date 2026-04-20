"""
Evidence-led outline planning for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agent_gatsby.config import AppConfig
from agent_gatsby.llm_client import invoke_text_completion
from agent_gatsby.schemas import EvidenceRecord, OutlinePlan

LOGGER = logging.getLogger(__name__)

JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
JSON_OBJECT_RE = re.compile(r"{.*}", re.DOTALL)


def find_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped

    object_match = JSON_OBJECT_RE.search(stripped)
    if object_match:
        return object_match.group(0)

    return stripped


def extract_json_payload(response_text: str) -> str:
    text = response_text.strip()
    if text.startswith("```"):
        text = JSON_FENCE_RE.sub("", text).strip()
    return find_json_object(text)


def parse_outline_response(response_text: str) -> OutlinePlan:
    payload = json.loads(extract_json_payload(response_text))
    if not isinstance(payload, dict):
        raise ValueError("Expected outline response to be a JSON object")
    return OutlinePlan.model_validate(payload)


def validate_outline_response(response_text: str) -> None:
    parse_outline_response(response_text)


def load_outline_prompt(config: AppConfig) -> str:
    return config.resolve_prompt_path("outline_prompt_path").read_text(encoding="utf-8")


def load_evidence_records(source: AppConfig | str | Path) -> list[EvidenceRecord]:
    if isinstance(source, AppConfig):
        path = source.evidence_ledger_path
    else:
        path = Path(source)

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected evidence ledger at {path} to contain a JSON array")
    return [EvidenceRecord.model_validate(item) for item in data]


def load_outline(source: AppConfig | str | Path) -> OutlinePlan:
    if isinstance(source, AppConfig):
        path = source.outline_output_path
    else:
        path = Path(source)

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected outline at {path} to contain a JSON object")
    return OutlinePlan.model_validate(data)


def round_robin_records_by_chapter(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    chapter_buckets: dict[int, list[EvidenceRecord]] = {}
    for record in records:
        chapter_buckets.setdefault(record.chapter, []).append(record)

    ordered: list[EvidenceRecord] = []
    chapter_order = sorted(chapter_buckets)
    while any(chapter_buckets.values()):
        for chapter in chapter_order:
            bucket = chapter_buckets[chapter]
            if bucket:
                ordered.append(bucket.pop(0))
    return ordered


def select_outline_evidence_records(config: AppConfig, evidence_records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    max_records = int(config.outline.get("max_prompt_evidence_records", 0))
    if max_records <= 0 or len(evidence_records) <= max_records:
        return evidence_records

    unique_passage_records: list[EvidenceRecord] = []
    seen_passage_ids: set[str] = set()
    for record in evidence_records:
        if record.passage_id in seen_passage_ids:
            continue
        unique_passage_records.append(record)
        seen_passage_ids.add(record.passage_id)

    selected = round_robin_records_by_chapter(unique_passage_records)

    if len(selected) < max_records:
        seen_evidence_ids = {record.evidence_id for record in selected}
        remaining_records = [record for record in evidence_records if record.evidence_id not in seen_evidence_ids]
        selected.extend(round_robin_records_by_chapter(remaining_records))

    selected = selected[:max_records]

    LOGGER.info(
        "Trimmed outline prompt evidence set from %d to %d records",
        len(evidence_records),
        len(selected),
    )
    return selected


def build_outline_user_prompt(config: AppConfig, evidence_records: list[EvidenceRecord]) -> str:
    minimum_sections = int(config.outline.get("minimum_section_count", 0))
    maximum_sections = int(config.outline.get("maximum_section_count", 0))
    fixed_title = str(config.outline.get("fixed_title", "")).strip()
    evidence_payload = [record.model_dump(exclude_none=True) for record in evidence_records]

    instructions = [
        "Create a structured essay outline from the verified evidence ledger.",
        "Return only a JSON object with the required schema.",
        "Read the full verified evidence ledger before choosing the essay order.",
        "Use only evidence IDs that appear in the ledger.",
        "Do not invent evidence, quotations, or section support.",
        "This outline should support a reader-friendly English report rather than an abstract technical artifact.",
        "Keep the title, thesis, introduction notes, conclusion notes, and body section headings in plain English.",
        "Prefer short, concrete section headings over abstract or literary-sounding labels.",
        "Keep the wording plainspoken, conversational, and easy to follow.",
        "Keep abstraction low and favor concrete nouns and verbs.",
        "Plan the body arguments first, then make the introduction and conclusion summarize those body arguments.",
        "The introduction should explain F. Scott Fitzgerald's writing style in The Great Gatsby and how he uses metaphor, based only on the evidence in the sections that follow.",
        "Prefer cohesive clusters of related metaphors per body section when those images clearly support the same theme or argumentative point.",
        "Make each body section feel like part of one flowing essay, not a disconnected catalog of isolated quotations.",
        "Each body section must include a short 'purpose' field that states the argumentative claim the section will prove.",
        "Order the body sections so the argument builds clearly from one metaphor to the next.",
        "Prefer an outline that spans multiple chapters across the novel when the verified ledger supports that breadth.",
        "Do not build the full essay from opening-chapter evidence alone if later chapters provide strong metaphors for the same thesis.",
        "Favor argumentative coverage across the novel over repeated close reading of one early scene.",
    ]
    if fixed_title:
        instructions.append(f'Use this exact essay title: "{fixed_title}".')
    if minimum_sections:
        instructions.append(f"Use at least {minimum_sections} body sections.")
    if maximum_sections:
        instructions.append(f"Use no more than {maximum_sections} body sections.")

    return "\n".join(instructions) + "\n\nVerified evidence ledger:\n" + json.dumps(
        evidence_payload,
        indent=2,
        ensure_ascii=False,
    )


def validate_outline_against_evidence(
    outline: OutlinePlan,
    *,
    evidence_records: list[EvidenceRecord],
    config: AppConfig,
) -> None:
    if not outline.title.strip():
        raise ValueError("Outline title must be non-empty")

    if config.outline.get("require_thesis", True) and not outline.thesis.strip():
        raise ValueError("Outline thesis must be non-empty")

    if config.outline.get("require_intro", True) and not outline.intro_notes.strip():
        raise ValueError("Outline intro notes must be non-empty")

    if config.outline.get("require_conclusion", True) and not outline.conclusion_notes.strip():
        raise ValueError("Outline conclusion notes must be non-empty")

    minimum_sections = int(config.outline.get("minimum_section_count", 0))
    maximum_sections = int(config.outline.get("maximum_section_count", 0))
    if minimum_sections and len(outline.sections) < minimum_sections:
        raise ValueError(
            f"Outline section count {len(outline.sections)} is below configured minimum {minimum_sections}"
        )
    if maximum_sections and len(outline.sections) > maximum_sections:
        raise ValueError(
            f"Outline section count {len(outline.sections)} exceeds configured maximum {maximum_sections}"
        )

    evidence_ids = {record.evidence_id for record in evidence_records}
    seen_section_ids: set[str] = set()
    for section in outline.sections:
        if not section.section_id.strip():
            raise ValueError("Outline sections must have non-empty section IDs")
        if section.section_id in seen_section_ids:
            raise ValueError(f"Duplicate outline section ID: {section.section_id}")
        seen_section_ids.add(section.section_id)

        if not section.heading.strip():
            raise ValueError(f"Outline section {section.section_id} must have a non-empty heading")

        if config.outline.get("require_evidence_ids_per_section", True) and not section.evidence_ids:
            raise ValueError(f"Outline section {section.section_id} must include at least one evidence ID")

        for evidence_id in section.evidence_ids:
            if evidence_id not in evidence_ids:
                raise ValueError(f"Outline references missing evidence ID: {evidence_id}")


def write_outline(config: AppConfig, outline: OutlinePlan) -> None:
    output_path = config.outline_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(outline.model_dump(exclude_none=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote outline with %d sections to %s", len(outline.sections), output_path)


def plan_outline(
    config: AppConfig,
    evidence_records: list[EvidenceRecord] | None = None,
) -> OutlinePlan:
    loaded_records = evidence_records or load_evidence_records(config)
    prompt_records = select_outline_evidence_records(config, loaded_records)
    response_text = invoke_text_completion(
        config,
        stage_name="plan_outline",
        system_prompt=load_outline_prompt(config),
        user_prompt=build_outline_user_prompt(config, prompt_records),
        output_path=str(config.outline_output_path),
        response_validator=validate_outline_response,
        transport_override=str(config.outline.get("llm_transport", "")).strip() or None,
    )
    outline = parse_outline_response(response_text)
    fixed_title = str(config.outline.get("fixed_title", "")).strip()
    if fixed_title:
        outline = outline.model_copy(update={"title": fixed_title})
    validate_outline_against_evidence(outline, evidence_records=loaded_records, config=config)
    write_outline(config, outline)
    return outline
