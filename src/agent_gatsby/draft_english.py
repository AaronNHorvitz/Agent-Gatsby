"""
Section-bounded English drafting for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agent_gatsby.citation_registry import build_context_payload, extract_citation_passage_ids, extract_invalid_bracket_markers
from agent_gatsby.config import AppConfig
from agent_gatsby.index_text import PassageIndex, load_passage_index
from agent_gatsby.llm_client import invoke_text_completion
from agent_gatsby.plan_outline import load_evidence_records, load_outline
from agent_gatsby.schemas import EvidenceRecord, OutlinePlan, OutlineSection

LOGGER = logging.getLogger(__name__)

DOUBLE_QUOTE_RE = re.compile(r"[\"“](.+?)[\"”]", re.DOTALL)
SINGLE_QUOTE_RE = re.compile(r"(?<!\w)['‘]([^'\n]{2,}?)['’](?!\w)")


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


def render_evidence_payload(
    evidence_records: list[EvidenceRecord],
    *,
    passage_index: PassageIndex,
    context_before: int,
    context_after: int,
) -> str:
    payload = [
        {
            "evidence_id": record.evidence_id,
            "metaphor": record.metaphor,
            "quote": record.quote,
            "passage_id": record.passage_id,
            "citation": f"[{record.passage_id}]",
            "interpretation": record.interpretation,
            "context_window": build_context_payload(
                passage_index,
                passage_id=record.passage_id,
                count_before=context_before,
                count_after=context_after,
            ),
        }
        for record in evidence_records
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def count_words(text: str) -> int:
    cleaned = re.sub(r"\[[^\]]+\]", "", text.replace("#", " ").replace("_", " "))
    return len(re.findall(r"\b[\w'-]+\b", cleaned, flags=re.UNICODE))


def estimate_page_count(word_count: int, words_per_page: int) -> float:
    if words_per_page <= 0:
        return 0.0
    return round(word_count / words_per_page, 2)


def build_overall_word_target_guidance(config: AppConfig) -> str | None:
    minimum_words = int(config.drafting.get("target_word_count_min", 0))
    maximum_words = int(config.drafting.get("target_word_count_max", 0))
    estimated_pages = int(config.drafting.get("estimated_page_target", 0))
    words_per_page = int(config.drafting.get("words_per_page_estimate", 280))

    if minimum_words <= 0 and maximum_words <= 0 and estimated_pages <= 0:
        return None

    word_target_bits: list[str] = []
    if minimum_words > 0 and maximum_words > 0:
        word_target_bits.append(f"about {minimum_words}-{maximum_words} words")
    elif minimum_words > 0:
        word_target_bits.append(f"at least {minimum_words} words")
    elif maximum_words > 0:
        word_target_bits.append(f"no more than {maximum_words} words")

    if estimated_pages > 0:
        word_target_bits.append(
            f"roughly {estimated_pages} pages at about {words_per_page} words per page"
        )

    return "Overall essay target: " + "; ".join(word_target_bits) + "."


def build_section_word_target_guidance(
    config: AppConfig,
    *,
    outline: OutlinePlan,
    section_type: str,
) -> str | None:
    minimum_total = int(config.drafting.get("target_word_count_min", 0))
    maximum_total = int(config.drafting.get("target_word_count_max", 0))
    if minimum_total <= 0 and maximum_total <= 0:
        return None

    body_section_count = max(len(outline.sections), 1)
    if section_type == "introduction":
        weight = 0.12
    elif section_type == "conclusion":
        weight = 0.12
    else:
        weight = 0.76 / body_section_count

    minimum_words = max(120, round(minimum_total * weight)) if minimum_total > 0 else None
    maximum_words = max(minimum_words or 120, round(maximum_total * weight)) if maximum_total > 0 else None

    if minimum_words and maximum_words:
        return f"Target section length: about {minimum_words}-{maximum_words} words."
    if minimum_words:
        return f"Target section length: at least {minimum_words} words."
    if maximum_words:
        return f"Target section length: no more than {maximum_words} words."
    return None


def normalize_validator_text(text: str) -> str:
    normalized = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )
    return collapse_spaces(normalized).strip()


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
    allowed_passage_ids = {record.passage_id for record in evidence_records}

    def validator(response_text: str) -> None:
        stripped = response_text.strip()
        if not stripped:
            raise ValueError("Drafted section is empty")

        invalid_markers = extract_invalid_bracket_markers(stripped)
        if invalid_markers:
            raise ValueError(f"Drafted section contains invalid bracket markers: {', '.join(invalid_markers)}")

        citations = extract_citation_passage_ids(stripped)
        if require_citation and not citations:
            raise ValueError("Drafted section must contain at least one valid [chapter.paragraph] citation")

        disallowed_citations = sorted({marker for marker in citations if marker not in allowed_passage_ids})
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
    config: AppConfig,
    outline: OutlinePlan,
    *,
    section_type: str,
    heading: str,
    section_notes: str,
    evidence_records: list[EvidenceRecord],
    passage_index: PassageIndex,
) -> str:
    instructions = [
        f"Section type: {section_type}",
        f"Essay title: {outline.title}",
        f"Thesis: {outline.thesis}",
        f"Section heading: {heading}",
        f"Section notes: {section_notes.strip()}",
        "Write markdown prose only for this section body.",
        "Do not repeat the section heading.",
        "Use only the evidence records and surrounding locked-source context provided below.",
        "Ground the analysis in what the text is doing in the current scene, not in unsupported claims about author intent.",
        "Explain why the metaphor makes sense in the surrounding paragraphs and how it clarifies character, setting, or theme in that moment.",
        "Only connect a metaphor to later developments in the novel when that claim is supported by the provided evidence.",
        "If you use a direct quotation, keep it exact and preserve its locator exactly as given.",
        "Never place quotation marks around any phrase unless it exactly matches one of the provided quote strings.",
        "Do not shorten, trim, or partially quote any provided quote string.",
    ]
    overall_word_target = build_overall_word_target_guidance(config)
    if overall_word_target:
        instructions.append(overall_word_target)
    section_word_target = build_section_word_target_guidance(
        config,
        outline=outline,
        section_type=section_type,
    )
    if section_word_target:
        instructions.append(section_word_target)
    if section_type == "body":
        instructions.append("Use at least one bracketed chapter.paragraph citation from the provided evidence.")
    instructions.append(
        "The only allowed locator markers for this section are: "
        + ", ".join(f"[{record.passage_id}]" for record in evidence_records)
    )
    return "\n".join(instructions) + "\n\nVerified evidence entries:\n" + render_evidence_payload(
        evidence_records,
        passage_index=passage_index,
        context_before=int(config.drafting.get("context_window_paragraphs_before", 1)),
        context_after=int(config.drafting.get("context_window_paragraphs_after", 1)),
    )


def validate_section_text(text: str, *, heading: str, require_citation: bool) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"Drafted section '{heading}' is empty")
    if require_citation and not extract_citation_passage_ids(stripped):
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
    passage_index: PassageIndex,
    output_path: str,
    require_citation: bool,
) -> str:
    response_text = invoke_text_completion(
        config,
        stage_name="draft_english",
        system_prompt=load_draft_prompt(config),
        user_prompt=build_draft_user_prompt(
            config,
            outline,
            section_type=section_type,
            heading=heading,
            section_notes=section_notes,
            evidence_records=evidence_records,
            passage_index=passage_index,
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
    passage_index: PassageIndex | None = None,
) -> str:
    loaded_outline = outline or load_outline(config)
    loaded_records = evidence_records or load_evidence_records(config)
    loaded_index = passage_index or load_passage_index(config)
    evidence_lookup = build_evidence_lookup(loaded_records)
    outline_records = gather_outline_evidence(loaded_outline, evidence_lookup)

    introduction_text = draft_section(
        config,
        outline=loaded_outline,
        section_type="introduction",
        heading="Introduction",
        section_notes=loaded_outline.intro_notes,
        evidence_records=outline_records,
        passage_index=loaded_index,
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
            passage_index=loaded_index,
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
        passage_index=loaded_index,
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

    word_count = count_words(draft_text)
    words_per_page = int(config.drafting.get("words_per_page_estimate", 280))
    estimated_pages = estimate_page_count(word_count, words_per_page)
    LOGGER.info(
        "English draft length: %d words, %.2f estimated pages at %d words/page",
        word_count,
        estimated_pages,
        words_per_page,
    )

    minimum_words = int(config.drafting.get("target_word_count_min", 0))
    maximum_words = int(config.drafting.get("target_word_count_max", 0))
    if minimum_words > 0 and word_count < minimum_words:
        LOGGER.warning("English draft is below target word count: %d < %d", word_count, minimum_words)
    if maximum_words > 0 and word_count > maximum_words:
        LOGGER.warning("English draft is above target word count: %d > %d", word_count, maximum_words)

    return draft_text
