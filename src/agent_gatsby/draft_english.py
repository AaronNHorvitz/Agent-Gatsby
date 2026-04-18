"""
Section-bounded English drafting for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agent_gatsby.config import AppConfig
from agent_gatsby.llm_client import invoke_text_completion
from agent_gatsby.plan_outline import load_evidence_records, load_outline
from agent_gatsby.schemas import EvidenceRecord, OutlinePlan, OutlineSection

LOGGER = logging.getLogger(__name__)

CITATION_RE = re.compile(r"\[\d+\.\d+\]")
ANY_BRACKET_RE = re.compile(r"\[([^\]]+)\]")
DOUBLE_QUOTE_RE = re.compile(r"[\"“](.+?)[\"”]", re.DOTALL)
SINGLE_QUOTE_RE = re.compile(r"(?<!\w)['‘]([^'\n]{2,}?)['’](?!\w)")
LOCATOR_NOTE = "Citation note: bracketed locators reference chapter.paragraph positions in the locked source text."


def load_draft_prompt(config: AppConfig) -> str:
    return config.resolve_prompt_path("draft_prompt_path").read_text(encoding="utf-8")


def build_evidence_lookup(evidence_records: list[EvidenceRecord]) -> dict[str, EvidenceRecord]:
    return {record.evidence_id: record for record in evidence_records}


def gather_section_evidence(section: OutlineSection, evidence_lookup: dict[str, EvidenceRecord]) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    for evidence_id in section.evidence_ids:
        if evidence_id not in evidence_lookup:
            raise ValueError(f"Outline section {section.section_id} references missing evidence ID: {evidence_id}")
        records.append(evidence_lookup[evidence_id])
    return records


def gather_outline_evidence(outline: OutlinePlan, evidence_lookup: dict[str, EvidenceRecord]) -> list[EvidenceRecord]:
    seen_ids: set[str] = set()
    ordered_records: list[EvidenceRecord] = []
    for section in outline.sections:
        for evidence_id in section.evidence_ids:
            if evidence_id in seen_ids:
                continue
            seen_ids.add(evidence_id)
            if evidence_id not in evidence_lookup:
                raise ValueError(f"Outline references missing evidence ID: {evidence_id}")
            ordered_records.append(evidence_lookup[evidence_id])
    return ordered_records


def render_evidence_payload(evidence_records: list[EvidenceRecord]) -> str:
    payload = [
        {
            "evidence_id": record.evidence_id,
            "metaphor": record.metaphor,
            "quote": record.quote,
            "passage_id": record.passage_id,
            "citation": f"[{record.passage_id}]",
            "interpretation": record.interpretation,
        }
        for record in evidence_records
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def normalize_validator_text(text: str) -> str:
    normalized = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )
    return collapse_spaces(normalized).strip()


def extract_citation_markers(text: str) -> list[str]:
    return [match.group(0) for match in CITATION_RE.finditer(text)]


def extract_invalid_bracket_markers(text: str) -> list[str]:
    invalid: list[str] = []
    for match in ANY_BRACKET_RE.finditer(text):
        if not CITATION_RE.fullmatch(match.group(0)):
            invalid.append(match.group(0))
    return invalid


def extract_quoted_strings(text: str) -> list[str]:
    quotes: list[str] = []
    for pattern in (DOUBLE_QUOTE_RE, SINGLE_QUOTE_RE):
        for match in pattern.finditer(text):
            candidate = collapse_spaces(match.group(1)).strip()
            if candidate:
                quotes.append(candidate)
    return quotes


def build_section_response_validator(
    evidence_records: list[EvidenceRecord],
    *,
    require_citation: bool,
) -> callable:
    allowed_quotes = {normalize_validator_text(record.quote) for record in evidence_records}
    allowed_citations = {f"[{record.passage_id}]" for record in evidence_records}

    def validator(response_text: str) -> None:
        stripped = response_text.strip()
        if not stripped:
            raise ValueError("Drafted section is empty")

        invalid_markers = extract_invalid_bracket_markers(stripped)
        if invalid_markers:
            raise ValueError(f"Drafted section contains invalid bracket markers: {', '.join(invalid_markers)}")

        citations = extract_citation_markers(stripped)
        if require_citation and not citations:
            raise ValueError("Drafted section must contain at least one valid [chapter.paragraph] citation")

        disallowed_citations = sorted({marker for marker in citations if marker not in allowed_citations})
        if disallowed_citations:
            raise ValueError(
                "Drafted section contains citations outside the allowed evidence set: "
                + ", ".join(disallowed_citations)
            )

        disallowed_quotes = sorted(
            {
                quote
                for quote in extract_quoted_strings(stripped)
                if normalize_validator_text(quote) not in allowed_quotes
            }
        )
        if disallowed_quotes:
            raise ValueError(
                "Drafted section contains quoted text outside the allowed evidence set: "
                + "; ".join(disallowed_quotes)
            )

    return validator


def build_draft_user_prompt(
    outline: OutlinePlan,
    *,
    section_type: str,
    heading: str,
    section_notes: str,
    evidence_records: list[EvidenceRecord],
) -> str:
    instructions = [
        f"Section type: {section_type}",
        f"Essay title: {outline.title}",
        f"Thesis: {outline.thesis}",
        f"Section heading: {heading}",
        f"Section notes: {section_notes.strip()}",
        "Write markdown prose only for this section body.",
        "Do not repeat the section heading.",
        "Use only the evidence records provided below.",
        "If you use a direct quotation, keep it exact and preserve its locator exactly as given.",
        "Never place quotation marks around any phrase unless it exactly matches one of the provided quote strings.",
        "Do not shorten, trim, or partially quote any provided quote string.",
    ]
    if section_type == "body":
        instructions.append("Use at least one bracketed chapter.paragraph citation from the provided evidence.")
    instructions.append(
        "The only allowed locator markers for this section are: "
        + ", ".join(f"[{record.passage_id}]" for record in evidence_records)
    )
    return "\n".join(instructions) + "\n\nVerified evidence entries:\n" + render_evidence_payload(evidence_records)


def validate_section_text(text: str, *, heading: str, require_citation: bool) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"Drafted section '{heading}' is empty")
    if require_citation and not CITATION_RE.search(stripped):
        raise ValueError(f"Drafted section '{heading}' does not contain a valid [chapter.paragraph] citation")
    return stripped


def write_section_file(config: AppConfig, *, filename: str, heading: str, text: str) -> Path:
    output_dir = config.section_drafts_dir_path
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(f"## {heading}\n\n{text.strip()}\n", encoding="utf-8")
    LOGGER.info("Wrote section draft to %s", output_path)
    return output_path


def draft_section(
    config: AppConfig,
    *,
    outline: OutlinePlan,
    section_type: str,
    heading: str,
    section_notes: str,
    evidence_records: list[EvidenceRecord],
    output_path: str,
    require_citation: bool,
) -> str:
    response_text = invoke_text_completion(
        config,
        stage_name="draft_english",
        system_prompt=load_draft_prompt(config),
        user_prompt=build_draft_user_prompt(
            outline,
            section_type=section_type,
            heading=heading,
            section_notes=section_notes,
            evidence_records=evidence_records,
        ),
        output_path=output_path,
        response_validator=build_section_response_validator(
            evidence_records,
            require_citation=require_citation,
        ),
    )
    return validate_section_text(response_text, heading=heading, require_citation=require_citation)


def compose_full_draft(
    outline: OutlinePlan,
    *,
    introduction_text: str,
    section_texts: list[tuple[str, str]],
    conclusion_text: str,
) -> str:
    parts = [
        f"# {outline.title}",
        "",
        f"_{LOCATOR_NOTE}_",
        "",
        "## Introduction",
        "",
        introduction_text.strip(),
        "",
    ]
    for heading, text in section_texts:
        parts.extend([f"## {heading}", "", text.strip(), ""])
    parts.extend(["## Conclusion", "", conclusion_text.strip(), ""])
    return "\n".join(parts).strip() + "\n"


def validate_combined_draft(draft_text: str, outline: OutlinePlan) -> None:
    if not draft_text.strip():
        raise ValueError("English draft is empty")

    last_position = -1
    expected_headings = ["## Introduction", *[f"## {section.heading}" for section in outline.sections], "## Conclusion"]
    for heading in expected_headings:
        position = draft_text.find(heading)
        if position == -1:
            raise ValueError(f"Combined draft is missing heading: {heading}")
        if position <= last_position:
            raise ValueError(f"Combined draft heading order is invalid around: {heading}")
        last_position = position

    if LOCATOR_NOTE not in draft_text:
        raise ValueError("Combined draft is missing the locator convention note")


def write_english_draft(config: AppConfig, draft_text: str) -> None:
    output_path = config.draft_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(draft_text, encoding="utf-8")
    LOGGER.info("Wrote English draft to %s", output_path)


def draft_english(
    config: AppConfig,
    *,
    outline: OutlinePlan | None = None,
    evidence_records: list[EvidenceRecord] | None = None,
) -> str:
    loaded_outline = outline or load_outline(config)
    loaded_records = evidence_records or load_evidence_records(config)
    evidence_lookup = build_evidence_lookup(loaded_records)
    outline_records = gather_outline_evidence(loaded_outline, evidence_lookup)

    introduction_text = draft_section(
        config,
        outline=loaded_outline,
        section_type="introduction",
        heading="Introduction",
        section_notes=loaded_outline.intro_notes,
        evidence_records=outline_records,
        output_path=str(config.section_drafts_dir_path / "00_introduction.md"),
        require_citation=False,
    )
    write_section_file(
        config,
        filename="00_introduction.md",
        heading="Introduction",
        text=introduction_text,
    )

    section_texts: list[tuple[str, str]] = []
    for section in loaded_outline.sections:
        section_records = gather_section_evidence(section, evidence_lookup)
        section_text = draft_section(
            config,
            outline=loaded_outline,
            section_type="body",
            heading=section.heading,
            section_notes=section.purpose or loaded_outline.thesis,
            evidence_records=section_records,
            output_path=str(config.section_drafts_dir_path / f"{section.section_id}.md"),
            require_citation=True,
        )
        write_section_file(
            config,
            filename=f"{section.section_id}.md",
            heading=section.heading,
            text=section_text,
        )
        section_texts.append((section.heading, section_text))

    conclusion_text = draft_section(
        config,
        outline=loaded_outline,
        section_type="conclusion",
        heading="Conclusion",
        section_notes=loaded_outline.conclusion_notes,
        evidence_records=outline_records,
        output_path=str(config.section_drafts_dir_path / "99_conclusion.md"),
        require_citation=False,
    )
    write_section_file(
        config,
        filename="99_conclusion.md",
        heading="Conclusion",
        text=conclusion_text,
    )

    draft_text = compose_full_draft(
        loaded_outline,
        introduction_text=introduction_text,
        section_texts=section_texts,
        conclusion_text=conclusion_text,
    )
    validate_combined_draft(draft_text, loaded_outline)
    write_english_draft(config, draft_text)
    return draft_text
