"""
Section-bounded English drafting for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from agent_gatsby.citation_registry import build_context_payload, extract_citation_passage_ids, extract_invalid_bracket_markers
from agent_gatsby.config import AppConfig
from agent_gatsby.index_text import PassageIndex, load_passage_index
from agent_gatsby.llm_client import LLMResponseValidationError, invoke_text_completion
from agent_gatsby.plan_outline import load_evidence_records, load_outline
from agent_gatsby.schemas import EvidenceRecord, OutlinePlan, OutlineSection
from agent_gatsby.translation_common import normalize_english_master_regressions

LOGGER = logging.getLogger(__name__)

DOUBLE_QUOTE_RE = re.compile(r"[\"“](.+?)[\"”]", re.DOTALL)
SINGLE_QUOTE_RE = re.compile(r"(?<!\w)['‘]([^'\n]{2,}?)['’](?!\w)")
ANY_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


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


def build_selection_scope_note(section_count: int) -> str:
    return (
        f"_This report organizes selected metaphor clusters into {section_count} thematic sections for a structured, citation-supported analysis._"
    )


def normalize_section_claim(section_notes: str) -> str:
    normalized = collapse_spaces(section_notes).strip()
    normalized = re.sub(
        r"^(argue|show|explain|demonstrate|trace|analyze|examine|explore|establish|discuss)\s+that\s+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"^(demonstrate|explore|analyze|show|explain|trace|examine|establish|discuss)\s+how\s+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"^(conclude|close|end)\s+the\s+argument\s+by\s+showing\s+how\s+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"^(conclude|close|end)\s+by\s+showing\s+how\s+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"^showing\s+how\s+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^how\s+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^that\s+", "", normalized, flags=re.IGNORECASE)
    return normalized.rstrip(".").strip()


def promote_claim_to_clause(section_claim: str) -> str:
    if not section_claim:
        return ""
    if re.match(r"^Fitzgerald\b", section_claim, flags=re.IGNORECASE):
        return section_claim

    lower_claim = section_claim.lower()
    verbs = (
        "establish",
        "create",
        "set",
        "illustrate",
        "portray",
        "reveal",
        "show",
        "trace",
        "explain",
        "reflect",
        "capture",
        "turn",
        "link",
        "suggest",
        "underscore",
        "highlight",
        "frame",
        "define",
    )
    for verb in verbs:
        marker = f" {verb} "
        index = lower_claim.find(marker)
        if index == -1:
            continue

        subject = section_claim[:index].strip()
        remainder = section_claim[index + len(marker) :].strip()
        if not subject or not remainder:
            continue
        if not re.search(r"\b(metaphor|metaphors|simile|similes|image|images|imagery|figure|figures)\b", subject, flags=re.IGNORECASE):
            continue
        return f"Fitzgerald uses {subject} to {verb} {remainder}"

    return section_claim


def build_metaphor_focus_lead(section_notes: str, *, evidence_count: int) -> str:
    normalized_claim = promote_claim_to_clause(normalize_section_claim(section_notes))
    if not normalized_claim:
        return "This cluster of images points to one shared idea."

    if evidence_count == 1:
        templates = (
            "This image suggests that {claim}.",
            "In this passage, the figurative language suggests that {claim}.",
            "This metaphor points to one central idea: {claim}.",
            "Read closely, this metaphor makes clear that {claim}.",
        )
    else:
        templates = (
            "Read together, these metaphors suggest that {claim}.",
            "Seen side by side, these images make clear that {claim}.",
            "This cluster of metaphors points to one larger idea: {claim}.",
            "Across these passages, the figurative language suggests that {claim}.",
        )

    template_index = sum(ord(character) for character in normalized_claim) % len(templates)
    return templates[template_index].format(claim=normalized_claim)


def render_metaphor_focus_block(evidence_records: list[EvidenceRecord], *, section_notes: str) -> str:
    if not evidence_records:
        return ""

    lines = [build_metaphor_focus_lead(section_notes, evidence_count=len(evidence_records)), "", "Metaphor text:"]
    for record in evidence_records:
        lines.append(f'> "{record.quote}" [{record.passage_id}]')
    return "\n".join(lines)


def strip_metaphor_focus_block(text: str) -> str:
    stripped = text.strip()
    while stripped:
        lines = stripped.splitlines()
        try:
            marker_index = next(index for index, line in enumerate(lines) if line.strip() == "Metaphor text:")
        except StopIteration:
            return stripped

        # Only treat an early leading block as the deterministic focus block.
        if marker_index > 2:
            return stripped

        content_index = marker_index + 1
        while content_index < len(lines) and (
            not lines[content_index].strip() or lines[content_index].lstrip().startswith(">")
        ):
            content_index += 1
        while content_index < len(lines) and not lines[content_index].strip():
            content_index += 1
        stripped = "\n".join(lines[content_index:]).strip()
    return stripped


def split_sentences(text: str) -> list[str]:
    normalized = collapse_spaces(text)
    if not normalized:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", normalized)
        if sentence.strip()
    ]


def summarize_body_section_text(text: str, *, max_sentences: int = 2) -> str:
    body_text = strip_metaphor_focus_block(text)
    sentences = split_sentences(body_text)
    if not sentences:
        return body_text
    return " ".join(sentences[:max_sentences]).strip()


def render_completed_body_context(section_texts: list[tuple[str, str]]) -> str:
    payload = [
        {
            "heading": heading,
            "argument_summary": summarize_body_section_text(text),
        }
        for heading, text in section_texts
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_body_retry_evidence_summary(
    evidence_records: list[EvidenceRecord],
    *,
    passage_index: PassageIndex,
) -> str:
    payload = []
    for record in evidence_records:
        payload.append(
            {
                "evidence_id": record.evidence_id,
                "metaphor": record.metaphor,
                "passage_id": record.passage_id,
                "interpretation": record.interpretation,
            }
        )
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_section_word_target_guidance(
    config: AppConfig,
    *,
    outline: OutlinePlan,
    section_type: str,
) -> str | None:
    minimum_words, maximum_words = section_word_target_bounds(
        config,
        outline=outline,
        section_type=section_type,
    )
    if minimum_words is None and maximum_words is None:
        return None

    if minimum_words and maximum_words:
        return f"Target section length: about {minimum_words}-{maximum_words} words."
    if minimum_words:
        return f"Target section length: at least {minimum_words} words."
    if maximum_words:
        return f"Target section length: no more than {maximum_words} words."
    return None


def section_word_target_bounds(
    config: AppConfig,
    *,
    outline: OutlinePlan,
    section_type: str,
) -> tuple[int | None, int | None]:
    minimum_total = int(config.drafting.get("target_word_count_min", 0))
    maximum_total = int(config.drafting.get("target_word_count_max", 0))
    if minimum_total <= 0 and maximum_total <= 0:
        return None, None

    body_section_count = max(len(outline.sections), 1)
    if section_type == "introduction":
        weight = 0.12
    elif section_type == "conclusion":
        weight = 0.12
    else:
        weight = 0.76 / body_section_count

    minimum_words = max(120, round(minimum_total * weight)) if minimum_total > 0 else None
    maximum_words = max(minimum_words or 120, round(maximum_total * weight)) if maximum_total > 0 else None
    return minimum_words, maximum_words


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


def strip_unauthorized_quotes(text: str, *, evidence_records: list[EvidenceRecord]) -> str:
    allowed_quotes = {normalize_validator_text(record.quote) for record in evidence_records}

    def replace_double(match: re.Match[str]) -> str:
        candidate = collapse_spaces(match.group(1)).strip()
        if normalize_validator_text(candidate) in allowed_quotes:
            return match.group(0)
        return candidate

    def replace_single(match: re.Match[str]) -> str:
        candidate = collapse_spaces(match.group(1)).strip()
        if normalize_validator_text(candidate) in allowed_quotes:
            return match.group(0)
        return candidate

    cleaned = DOUBLE_QUOTE_RE.sub(replace_double, text)
    cleaned = SINGLE_QUOTE_RE.sub(replace_single, cleaned)
    return cleaned


def strip_all_direct_quotes(text: str) -> str:
    cleaned = DOUBLE_QUOTE_RE.sub(lambda match: collapse_spaces(match.group(1)).strip(), text)
    cleaned = SINGLE_QUOTE_RE.sub(lambda match: collapse_spaces(match.group(1)).strip(), cleaned)
    return cleaned.replace('"', "").replace("“", "").replace("”", "")


def strip_invalid_bracket_markers(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        marker = match.group(0)
        if marker not in extract_invalid_bracket_markers(marker):
            return marker
        return match.group(1)

    return ANY_BRACKET_RE.sub(replace, text)


def repair_invalid_section_artifacts(
    text: str,
    *,
    evidence_records: list[EvidenceRecord],
    forbid_direct_quotes: bool = False,
) -> str:
    cleaned = strip_invalid_bracket_markers(text)
    cleaned = strip_unauthorized_quotes(cleaned, evidence_records=evidence_records)
    if forbid_direct_quotes:
        cleaned = strip_all_direct_quotes(cleaned)
    return cleaned


def build_section_response_validator(
    evidence_records: list[EvidenceRecord],
    *,
    require_citation: bool,
    forbid_direct_quotes: bool = False,
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

        if forbid_direct_quotes and extract_quoted_strings(stripped):
            raise ValueError("Drafted section must not contain direct quotations")

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
    completed_body_sections: list[tuple[str, str]] | None = None,
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
        "Use clear, readable English rather than dense academic jargon.",
        "Move quickly from claim to evidence to explanation.",
        "Prefer shorter topic sentences and direct academic prose over lush setup.",
        'Do not overuse empty sentence openings like "The text," "This metaphor," or "This imagery."',
        "Vary your phrasing by referring naturally to Fitzgerald, the novel, the narrator, Gatsby, the scene, the image, or the passage when appropriate.",
        "Prefer concrete literary-analysis prose over abstract academic filler.",
        "Cut decorative phrasing when it slows the argument.",
        "Because a later editorial pass will simplify the prose, keep this first-pass section full, scene-rich, and complete rather than prematurely compressed.",
        "Treat the surrounding context as paraphrase-only background unless the exact words also appear in a provided quote field.",
        "If you use a direct quotation, copy the provided quote field character-for-character and preserve its locator exactly as given.",
        "Do not normalize capitalization, articles, punctuation, or spacing inside a quoted span.",
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
    if section_type == "introduction":
        instructions.append(
            "Write this introduction after the body arguments already exist."
        )
        instructions.append(
            "Write 4 substantial paragraphs rather than one compressed block."
        )
        instructions.append(
            "Open with a clear statement about F. Scott Fitzgerald's writing style in The Great Gatsby."
        )
        instructions.append(
            "State a thesis about how Fitzgerald uses metaphor in the novel, based on the verified text discussed in the body sections."
        )
        instructions.append(
            "Explain in plain English what the story is about, why these selected metaphors matter, "
            "and how the body sections will prove the essay's argument."
        )
        instructions.append("Keep the introduction direct and readable rather than ornate.")
        instructions.append(
            "End with a transition sentence that leads naturally into the first body section."
        )
        instructions.append("Prefer paraphrase over direct quotation in the introduction.")
        instructions.append("Develop the introduction fully enough to land near the high end of the section target range.")
    if section_type == "conclusion":
        instructions.append("Write this conclusion after the body arguments already exist.")
        instructions.append("Keep the conclusion short, direct, and easy to read.")
        instructions.append("Write 3 substantial paragraphs rather than one compressed block.")
        instructions.append("Synthesize the body arguments into one closing judgment about Fitzgerald's use of metaphor.")
        instructions.append("Avoid decorative recap; close with a concise final judgment.")
    if section_type == "body":
        instructions.append(
            "Structure this section as a compact argument chain: opening claim, cited supporting evidence, "
            "analysis of how the text proves the claim in scene context, and a closing or transition sentence."
        )
        instructions.append(
            "Do not collapse the body section into outline prose. Develop the reasoning fully enough that a later plain-English edit can shorten the sentences without stripping out the argument."
        )
        instructions.append(
            "Treat the provided metaphors as one thematic cluster rather than as separate mini-sections."
        )
        instructions.append(
            "The opening sentence should make an arguable point, not just announce the topic."
        )
        instructions.append("Use at least one bracketed chapter.paragraph citation from the provided evidence.")
        instructions.append(
            "Assume the exact metaphor text will be shown immediately before your analysis, so do not waste the opening sentence restating it."
        )
        instructions.append(
            "Do not use direct quotations or quotation marks in the analytical prose body; rely on citations and paraphrase because the exact quoted text already appears in the section's `Metaphor text:` block."
        )
        instructions.append(
            "The final report will place a short thematic lead-in sentence before the `Metaphor text:` block, so make the analysis deepen that shared theme rather than reintroduce it."
        )
        instructions.append(
            "Develop the section across 3 or 4 purposeful paragraphs so the grouped metaphors can build one cohesive argument."
        )
        instructions.append(
            "Do not collapse the section into one dense block, but keep the argument moving briskly."
        )
        instructions.append(
            "Aim for the high end of the section target range and keep building the argument until each paragraph has concrete evidence and explanation."
        )
        instructions.append(
            "Address every quotation shown in the section's `Metaphor text:` block at least once, but combine related images when that keeps the analysis direct and readable."
        )
    instructions.append(
        "The only allowed locator markers for this section are: "
        + ", ".join(f"[{record.passage_id}]" for record in evidence_records)
    )
    prompt_text = "\n".join(instructions) + "\n\nVerified evidence entries:\n" + render_evidence_payload(
        evidence_records,
        passage_index=passage_index,
        context_before=int(config.drafting.get("context_window_paragraphs_before", 1)),
        context_after=int(config.drafting.get("context_window_paragraphs_after", 1)),
    )
    if section_type in {"introduction", "conclusion"} and completed_body_sections:
        prompt_text += "\n\nCompleted body arguments:\n" + render_completed_body_context(completed_body_sections)
    return prompt_text


def build_intro_retry_user_prompt(
    config: AppConfig,
    outline: OutlinePlan,
    *,
    heading: str,
    section_notes: str,
    completed_body_sections: list[tuple[str, str]],
) -> str:
    instructions = [
        "Compact retry mode: introductory summary only.",
        f"Essay title: {outline.title}",
        f"Thesis: {outline.thesis}",
        f"Section heading: {heading}",
        f"Section notes: {section_notes.strip()}",
        "Write markdown prose only for this section body.",
        "Write 4 substantial paragraphs in clear, readable English.",
        "Do not repeat the section heading.",
        "Do not include notes, self-critique, drafting commentary, or word-count checks.",
        "Use only the completed body arguments provided below.",
        "Do not use any direct quotations or quotation marks in this introduction; paraphrase the evidence instead.",
        'Do not open multiple sentences with "The text" or similar abstract filler.',
        "Keep the prose direct and lightly academic rather than ornamental.",
        "Explain F. Scott Fitzgerald's writing style in The Great Gatsby and how he uses metaphor, based on the body arguments already drafted.",
        "Briefly explain what happens in the story, how the text uses metaphor as a literary device, and how the selected metaphor clusters organize the analysis.",
        "End with a transition sentence leading into the first body section.",
        "Land near the high end of the section target range instead of compressing the introduction.",
    ]
    overall_word_target = build_overall_word_target_guidance(config)
    if overall_word_target:
        instructions.append(overall_word_target)
    section_word_target = build_section_word_target_guidance(
        config,
        outline=outline,
        section_type="introduction",
    )
    if section_word_target:
        instructions.append(section_word_target)
    return "\n".join(instructions) + "\n\nCompleted body arguments:\n" + render_completed_body_context(
        completed_body_sections
    )


def build_body_retry_user_prompt(
    config: AppConfig,
    outline: OutlinePlan,
    *,
    heading: str,
    section_notes: str,
    evidence_records: list[EvidenceRecord],
    passage_index: PassageIndex,
) -> str:
    instructions = [
        "Compact retry mode: body argument only.",
        f"Essay title: {outline.title}",
        f"Thesis: {outline.thesis}",
        f"Section heading: {heading}",
        f"Section notes: {section_notes.strip()}",
        "Write markdown prose only for this section body.",
        "Write 4 substantial paragraphs in clear, readable English.",
        "Do not repeat the section heading.",
        "Do not include notes, self-critique, drafting commentary, or word-count checks.",
        "Use only the evidence summary provided below.",
        "Do not use any direct quotations or quotation marks in this compact retry; the exact quoted text already appears in the section's `Metaphor text:` block.",
        "Build a compact argument chain: opening claim, cited supporting evidence, explanation of how the scene context supports the claim, and a short closing or transition sentence.",
        "Treat the provided metaphors as one thematic cluster rather than as separate mini-sections.",
        "Address every quotation in the evidence summary at least once.",
        'Do not overuse abstract openings such as "The text" or "This metaphor."',
        "Keep the prose direct, lightly academic, and faster-moving than a full literary close-reading seminar.",
        "Combine related images when that keeps the section concise and readable.",
        "Use citations rather than direct quotation when referring back to the evidence.",
        "The only allowed locator markers for this section are: "
        + ", ".join(f"[{record.passage_id}]" for record in evidence_records),
    ]
    overall_word_target = build_overall_word_target_guidance(config)
    if overall_word_target:
        instructions.append(overall_word_target)
    section_word_target = build_section_word_target_guidance(
        config,
        outline=outline,
        section_type="body",
    )
    if section_word_target:
        instructions.append(section_word_target)
    return "\n".join(instructions) + "\n\nEvidence summary:\n" + render_body_retry_evidence_summary(
        evidence_records,
        passage_index=passage_index,
    )


def build_conclusion_retry_user_prompt(
    config: AppConfig,
    outline: OutlinePlan,
    *,
    heading: str,
    section_notes: str,
    completed_body_sections: list[tuple[str, str]],
) -> str:
    instructions = [
        "Compact retry mode: conclusion synthesis only.",
        f"Essay title: {outline.title}",
        f"Thesis: {outline.thesis}",
        f"Section heading: {heading}",
        f"Section notes: {section_notes.strip()}",
        "Write markdown prose only for this section body.",
        "Write 4 substantial paragraphs in clear, readable English.",
        "Do not repeat the section heading.",
        "Do not include notes, self-critique, drafting commentary, or word-count checks.",
        "Use only the completed body arguments provided below.",
        "Do not use any direct quotations or quotation marks in this conclusion; paraphrase the evidence instead.",
        "Synthesize the body arguments into one final judgment about Fitzgerald's use of metaphor.",
        "Keep the prose direct, plainspoken, and controlled rather than ornamental.",
        "Do not turn the conclusion into outline bullets or compressed notes.",
        "Close with a clear final judgment about the collapse of Gatsby's dream.",
    ]
    overall_word_target = build_overall_word_target_guidance(config)
    if overall_word_target:
        instructions.append(overall_word_target)
    section_word_target = build_section_word_target_guidance(
        config,
        outline=outline,
        section_type="conclusion",
    )
    if section_word_target:
        instructions.append(section_word_target)
    return "\n".join(instructions) + "\n\nCompleted body arguments:\n" + render_completed_body_context(
        completed_body_sections
    )


def build_section_expansion_user_prompt(
    config: AppConfig,
    outline: OutlinePlan,
    *,
    section_type: str,
    heading: str,
    section_notes: str,
    current_text: str,
    evidence_records: list[EvidenceRecord],
    passage_index: PassageIndex,
    completed_body_sections: list[tuple[str, str]] | None = None,
) -> str:
    instructions = [
        "Expansion mode: revise and expand the existing section so the essay can reach its target length.",
        f"Section type: {section_type}",
        f"Essay title: {outline.title}",
        f"Thesis: {outline.thesis}",
        f"Section heading: {heading}",
        f"Section notes: {section_notes.strip()}",
        "Return markdown prose only for the revised section body.",
        "Preserve the section's core claim and overall direction.",
        "Keep all existing valid citation markers unchanged.",
        "Do not add new citation locators.",
        "Do not add new direct quotations.",
        "If a direct quotation already appears, preserve it character-for-character.",
        "Expand by adding more scene-specific explanation, clearer transitions, and fuller claim-evidence-analysis development.",
        "Prefer concrete literary analysis over abstraction or filler.",
    ]
    section_word_target = build_section_word_target_guidance(
        config,
        outline=outline,
        section_type=section_type,
    )
    if section_word_target:
        instructions.append(section_word_target)
    if section_type == "body":
        instructions.extend(
            [
                "The deterministic `Metaphor text:` block will be reattached separately, so revise only the analytical prose body shown below.",
                "Use only the evidence records and surrounding locked-source context provided below.",
                "Do not use direct quotations or quotation marks in this expansion; rely on citations and paraphrase instead.",
                "Keep the analysis moving paragraph by paragraph rather than collapsing it into one dense block.",
                "Address all provided evidence at least once while deepening the explanation.",
            ]
        )
        prompt_text = "\n".join(instructions)
        prompt_text += "\n\nCurrent analytical prose:\n\n" + current_text.strip()
        prompt_text += "\n\nVerified evidence entries:\n" + render_evidence_payload(
            evidence_records,
            passage_index=passage_index,
            context_before=int(config.drafting.get("context_window_paragraphs_before", 1)),
            context_after=int(config.drafting.get("context_window_paragraphs_after", 1)),
        )
        return prompt_text
    if section_type == "introduction":
        instructions.extend(
            [
                "Do not add direct quotations or quotation marks to the introduction.",
                "Use the completed body arguments below to expand the framing, stakes, and roadmap.",
            ]
        )
    if section_type == "conclusion":
        instructions.extend(
            [
                "Do not add direct quotations or quotation marks to the conclusion.",
                "Use the completed body arguments below to deepen the synthesis and final judgment.",
            ]
        )
    prompt_text = "\n".join(instructions)
    prompt_text += "\n\nCurrent section draft:\n\n" + current_text.strip()
    if completed_body_sections:
        prompt_text += "\n\nCompleted body arguments:\n" + render_completed_body_context(completed_body_sections)
    return prompt_text


def build_section_expansion_response_validator(
    original_text: str,
    evidence_records: list[EvidenceRecord],
    *,
    require_citation: bool,
    minimum_word_count: int,
    forbid_direct_quotes: bool,
):
    section_validator = build_section_response_validator(
        evidence_records,
        require_citation=require_citation,
    )

    def validator(response_text: str) -> None:
        section_validator(response_text)
        if forbid_direct_quotes and extract_quoted_strings(response_text):
            raise ValueError("Expanded section must not contain direct quotations")
        revised_word_count = count_words(response_text)
        if revised_word_count < minimum_word_count:
            raise ValueError(
                f"Expanded section is still too short: {revised_word_count} < {minimum_word_count}"
            )
        if revised_word_count <= count_words(original_text):
            raise ValueError("Expanded section did not materially increase length")

    return validator


def expand_section(
    config: AppConfig,
    *,
    outline: OutlinePlan,
    section_type: str,
    heading: str,
    section_notes: str,
    current_text: str,
    evidence_records: list[EvidenceRecord],
    passage_index: PassageIndex,
    output_path: str,
    require_citation: bool,
    completed_body_sections: list[tuple[str, str]] | None = None,
) -> str:
    current_body_text = strip_metaphor_focus_block(current_text) if section_type == "body" else current_text.strip()
    current_word_count = count_words(current_body_text)
    minimum_words, _ = section_word_target_bounds(
        config,
        outline=outline,
        section_type=section_type,
    )
    minimum_increase = int(config.drafting.get("expansion_pass_min_increase_words", 120))
    target_word_count = max(current_word_count + minimum_increase, minimum_words or 0)
    response_validator = build_section_expansion_response_validator(
        current_body_text,
        evidence_records,
        require_citation=require_citation,
        minimum_word_count=target_word_count,
        forbid_direct_quotes=True,
    )
    transport_override = (
        str(config.drafting.get("expansion_pass_transport", "")).strip()
        or str(config.drafting.get("llm_transport", "")).strip()
        or None
    )
    try:
        response_text = invoke_text_completion(
            config,
            stage_name="expand_english_section",
            system_prompt=load_draft_prompt(config),
            user_prompt=build_section_expansion_user_prompt(
                config,
                outline,
                section_type=section_type,
                heading=heading,
                section_notes=section_notes,
                current_text=current_body_text,
                evidence_records=evidence_records,
                passage_index=passage_index,
                completed_body_sections=completed_body_sections,
            ),
            output_path=output_path,
            response_validator=response_validator,
            transport_override=transport_override,
        )
    except LLMResponseValidationError as exc:
        if not exc.response_text:
            raise
        repaired_text = repair_invalid_section_artifacts(
            exc.response_text,
            evidence_records=evidence_records,
            forbid_direct_quotes=True,
        )
        LOGGER.warning(
            "Expanded section failed validation; applying deterministic cleanup before retrying validation: %s",
            exc,
        )
        response_validator(repaired_text)
        response_text = repaired_text
    section_text = validate_section_text(response_text, heading=heading, require_citation=require_citation)
    section_text = apply_draft_regression_fixes(section_text, label=f"expanded section '{heading}'")
    section_text = validate_section_text(section_text, heading=heading, require_citation=require_citation)
    if section_type == "body":
        focus_block = render_metaphor_focus_block(evidence_records, section_notes=section_notes)
        return f"{focus_block}\n\n{section_text}".strip()
    return section_text


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
    completed_body_sections: list[tuple[str, str]] | None = None,
) -> str:
    transport_override = str(config.drafting.get("llm_transport", "")).strip() or None
    response_validator = build_section_response_validator(
        evidence_records,
        require_citation=require_citation,
        forbid_direct_quotes=section_type == "body",
    )
    try:
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
                completed_body_sections=completed_body_sections,
            ),
            output_path=output_path,
            response_validator=response_validator,
            transport_override=transport_override,
        )
    except LLMResponseValidationError as exc:
        if exc.response_text:
            repaired_text = repair_invalid_section_artifacts(
                exc.response_text,
                evidence_records=evidence_records,
                forbid_direct_quotes=section_type == "body",
            )
            if repaired_text != exc.response_text:
                LOGGER.warning(
                    "Drafted section failed validation; applying deterministic cleanup before retrying validation: %s",
                    exc,
                )
                try:
                    response_validator(repaired_text)
                    section_text = validate_section_text(
                        repaired_text,
                        heading=heading,
                        require_citation=require_citation,
                    )
                    section_text = apply_draft_regression_fixes(section_text, label=f"section '{heading}'")
                    section_text = validate_section_text(
                        section_text,
                        heading=heading,
                        require_citation=require_citation,
                    )
                    if section_type == "body":
                        focus_block = render_metaphor_focus_block(evidence_records, section_notes=section_notes)
                        return f"{focus_block}\n\n{section_text}".strip()
                    return section_text
                except ValueError as repair_exc:
                    LOGGER.warning(
                        "Deterministic cleanup still failed validation; continuing to compact retry path: %s",
                        repair_exc,
                    )
        if section_type == "conclusion":
            LOGGER.warning(
                "Conclusion draft failed validation; retrying with compact conclusion prompt: %s",
                exc,
            )
            response_text = invoke_text_completion(
                config,
                stage_name="draft_english",
                system_prompt=load_draft_prompt(config),
                user_prompt=build_conclusion_retry_user_prompt(
                    config,
                    outline,
                    heading=heading,
                    section_notes=section_notes,
                    completed_body_sections=completed_body_sections or [],
                ),
                output_path=output_path,
                response_validator=response_validator,
                transport_override=transport_override,
            )
        elif section_type == "body":
            LOGGER.warning(
                "Body section draft failed validation; retrying with compact body prompt: %s",
                exc,
            )
            response_text = invoke_text_completion(
                config,
                stage_name="draft_english",
                system_prompt=load_draft_prompt(config),
                user_prompt=build_body_retry_user_prompt(
                    config,
                    outline,
                    heading=heading,
                    section_notes=section_notes,
                    evidence_records=evidence_records,
                    passage_index=passage_index,
                ),
                output_path=output_path,
                response_validator=response_validator,
                transport_override=transport_override,
            )
        elif "Model returned empty content" not in str(exc):
            raise
        elif section_type == "introduction":
            LOGGER.warning(
                "Introduction draft returned empty content; retrying with compact intro prompt: %s",
                exc,
            )
            response_text = invoke_text_completion(
                config,
                stage_name="draft_english",
                system_prompt=load_draft_prompt(config),
                user_prompt=build_intro_retry_user_prompt(
                    config,
                    outline,
                    heading=heading,
                    section_notes=section_notes,
                    completed_body_sections=completed_body_sections or [],
                ),
                output_path=output_path,
                response_validator=response_validator,
                transport_override=transport_override,
            )
        else:
            raise
    section_text = validate_section_text(response_text, heading=heading, require_citation=require_citation)
    section_text = apply_draft_regression_fixes(section_text, label=f"section '{heading}'")
    section_text = validate_section_text(section_text, heading=heading, require_citation=require_citation)
    if section_type == "body":
        focus_block = render_metaphor_focus_block(evidence_records, section_notes=section_notes)
        return f"{focus_block}\n\n{section_text}".strip()
    return section_text


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
        build_selection_scope_note(len(outline.sections)),
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


def apply_draft_regression_fixes(text: str, *, label: str) -> str:
    normalized_text, applied_fixes = normalize_english_master_regressions(text)
    if applied_fixes:
        LOGGER.info("Applied %d deterministic regression fixes to %s", len(applied_fixes), label)
    return normalized_text

def write_english_draft(config: AppConfig, draft_text: str) -> None:
    output_path = config.draft_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(draft_text, encoding="utf-8")
    LOGGER.info("Wrote English draft to %s", output_path)


def draft_timing_output_path(config: AppConfig) -> Path:
    return config.resolve_repo_path(
        str(config.drafting.get("timing_output_path", "artifacts/qa/english_draft_timing.json"))
    )


def write_draft_timing_report(config: AppConfig, payload: dict[str, object]) -> None:
    output_path = draft_timing_output_path(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote English draft timing report to %s", output_path)


def expansion_pass_enabled(config: AppConfig) -> bool:
    return bool(config.drafting.get("expansion_pass_enabled", False))


def expansion_pass_max_rounds(config: AppConfig) -> int:
    return max(0, int(config.drafting.get("expansion_pass_max_rounds", 1)))


def draft_english(
    config: AppConfig,
    *,
    outline: OutlinePlan | None = None,
    evidence_records: list[EvidenceRecord] | None = None,
    passage_index: PassageIndex | None = None,
) -> str:
    draft_started_at = time.perf_counter()
    loaded_outline = outline or load_outline(config)
    loaded_records = evidence_records or load_evidence_records(config)
    loaded_index = passage_index or load_passage_index(config)
    evidence_lookup = build_evidence_lookup(loaded_records)
    outline_records = gather_outline_evidence(loaded_outline, evidence_lookup)

    section_texts: list[tuple[str, str]] = []
    section_timings: list[dict[str, object]] = []
    for section in loaded_outline.sections:
        section_records = gather_section_evidence(section, evidence_lookup)
        section_started_at = time.perf_counter()
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
        section_timings.append(
            {
                "section_id": section.section_id,
                "section_type": "body",
                "heading": section.heading,
                "elapsed_seconds": round(time.perf_counter() - section_started_at, 3),
            }
        )

    introduction_started_at = time.perf_counter()
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
        completed_body_sections=section_texts,
    )
    write_section_file(
        config,
        filename="00_introduction.md",
        heading="Introduction",
        text=introduction_text,
    )
    section_timings.append(
        {
            "section_id": "00_introduction",
            "section_type": "introduction",
            "heading": "Introduction",
            "elapsed_seconds": round(time.perf_counter() - introduction_started_at, 3),
        }
    )

    conclusion_started_at = time.perf_counter()
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
        completed_body_sections=section_texts,
    )
    write_section_file(
        config,
        filename="99_conclusion.md",
        heading="Conclusion",
        text=conclusion_text,
    )
    section_timings.append(
        {
            "section_id": "99_conclusion",
            "section_type": "conclusion",
            "heading": "Conclusion",
            "elapsed_seconds": round(time.perf_counter() - conclusion_started_at, 3),
        }
    )

    draft_text = compose_full_draft(
        loaded_outline,
        introduction_text=introduction_text,
        section_texts=section_texts,
        conclusion_text=conclusion_text,
    )
    draft_text = apply_draft_regression_fixes(draft_text, label="combined English draft")
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
    expansion_rounds_used = 0
    if minimum_words > 0 and word_count < minimum_words and expansion_pass_enabled(config):
        for round_index in range(expansion_pass_max_rounds(config)):
            LOGGER.info(
                "Starting English expansion round %d because draft is below target: %d < %d",
                round_index + 1,
                word_count,
                minimum_words,
            )
            expanded_any = False

            for index, section in enumerate(loaded_outline.sections):
                current_text = section_texts[index][1]
                section_minimum_words, _ = section_word_target_bounds(
                    config,
                    outline=loaded_outline,
                    section_type="body",
                )
                if section_minimum_words is not None and count_words(current_text) >= section_minimum_words:
                    continue
                section_records = gather_section_evidence(section, evidence_lookup)
                expanded_text = expand_section(
                    config,
                    outline=loaded_outline,
                    section_type="body",
                    heading=section.heading,
                    section_notes=section.purpose or loaded_outline.thesis,
                    current_text=current_text,
                    evidence_records=section_records,
                    passage_index=loaded_index,
                    output_path=str(config.section_drafts_dir_path / f"{section.section_id}.md"),
                    require_citation=True,
                )
                if count_words(expanded_text) > count_words(current_text):
                    expanded_any = True
                section_texts[index] = (section.heading, expanded_text)
                write_section_file(
                    config,
                    filename=f"{section.section_id}.md",
                    heading=section.heading,
                    text=expanded_text,
                )

            intro_minimum_words, _ = section_word_target_bounds(
                config,
                outline=loaded_outline,
                section_type="introduction",
            )
            if intro_minimum_words is None or count_words(introduction_text) < intro_minimum_words:
                expanded_intro = expand_section(
                    config,
                    outline=loaded_outline,
                    section_type="introduction",
                    heading="Introduction",
                    section_notes=loaded_outline.intro_notes,
                    current_text=introduction_text,
                    evidence_records=outline_records,
                    passage_index=loaded_index,
                    output_path=str(config.section_drafts_dir_path / "00_introduction.md"),
                    require_citation=False,
                    completed_body_sections=section_texts,
                )
                if count_words(expanded_intro) > count_words(introduction_text):
                    expanded_any = True
                introduction_text = expanded_intro
                write_section_file(
                    config,
                    filename="00_introduction.md",
                    heading="Introduction",
                    text=introduction_text,
                )

            conclusion_minimum_words, _ = section_word_target_bounds(
                config,
                outline=loaded_outline,
                section_type="conclusion",
            )
            if conclusion_minimum_words is None or count_words(conclusion_text) < conclusion_minimum_words:
                expanded_conclusion = expand_section(
                    config,
                    outline=loaded_outline,
                    section_type="conclusion",
                    heading="Conclusion",
                    section_notes=loaded_outline.conclusion_notes,
                    current_text=conclusion_text,
                    evidence_records=outline_records,
                    passage_index=loaded_index,
                    output_path=str(config.section_drafts_dir_path / "99_conclusion.md"),
                    require_citation=False,
                    completed_body_sections=section_texts,
                )
                if count_words(expanded_conclusion) > count_words(conclusion_text):
                    expanded_any = True
                conclusion_text = expanded_conclusion
                write_section_file(
                    config,
                    filename="99_conclusion.md",
                    heading="Conclusion",
                    text=conclusion_text,
                )

            if not expanded_any:
                LOGGER.warning("English expansion round %d made no measurable progress", round_index + 1)
                break

            draft_text = compose_full_draft(
                loaded_outline,
                introduction_text=introduction_text,
                section_texts=section_texts,
                conclusion_text=conclusion_text,
            )
            draft_text = apply_draft_regression_fixes(draft_text, label="expanded English draft")
            validate_combined_draft(draft_text, loaded_outline)
            write_english_draft(config, draft_text)

            word_count = count_words(draft_text)
            estimated_pages = estimate_page_count(word_count, words_per_page)
            expansion_rounds_used = round_index + 1
            LOGGER.info(
                "English draft length after expansion round %d: %d words, %.2f estimated pages",
                expansion_rounds_used,
                word_count,
                estimated_pages,
            )
            if word_count >= minimum_words:
                break

    if maximum_words > 0 and word_count > maximum_words:
        LOGGER.warning("English draft is above target word count: %d > %d", word_count, maximum_words)

    total_elapsed_seconds = round(time.perf_counter() - draft_started_at, 3)
    write_draft_timing_report(
        config,
        {
            "stage": "draft_english",
            "title": loaded_outline.title,
            "section_count": len(loaded_outline.sections),
            "word_count": word_count,
            "estimated_pages": estimated_pages,
            "expansion_rounds_used": expansion_rounds_used,
            "total_elapsed_seconds": total_elapsed_seconds,
            "transport": str(config.drafting.get("llm_transport", "")).strip()
            or str(config.models.get("provider", "")).strip()
            or "openai_compatible",
            "sections": section_timings,
        },
    )
    LOGGER.info("Completed English report draft in %.3f seconds", total_elapsed_seconds)

    if (
        minimum_words > 0
        and word_count < minimum_words
        and bool(config.drafting.get("fail_below_target_word_count", False))
    ):
        raise ValueError(
            f"English draft is below target word count: {word_count} < {minimum_words}"
        )

    return draft_text
