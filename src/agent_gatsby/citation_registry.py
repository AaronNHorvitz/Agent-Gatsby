"""
Deterministic citation registry and human-readable citation rendering helpers.
"""

from __future__ import annotations

import json
import re

from agent_gatsby.config import AppConfig
from agent_gatsby.schemas import CitationRegistryEntry, PassageIndex, PassageRecord

CANONICAL_CITATION_RE = re.compile(r"\[(\d+)\.(\d+)\]")
DISPLAY_CITATION_RE = re.compile(r"\[#(\d+),\s*Chapter\s+(\d+),\s*Paragraph\s+(\d+)\]")
ANY_BRACKET_RE = re.compile(r"\[([^\]]+)\]")
LEGACY_CITATION_NOTE_RE = re.compile(r"(?m)^_?Citation note:[^\n]*_?\n?")
BODY_SECTION_HEADING_RE = re.compile(r"(?m)^## (?!Citations$)")
STRAIGHT_DOUBLE_QUOTE_RE = re.compile(r'(?<!\*)"([^"\n]+?)"(?!\*)')
CURLY_DOUBLE_QUOTE_RE = re.compile(r"(?<!\*)“([^”\n]+?)”(?!\*)")


def canonical_locator_from_passage(passage: PassageRecord) -> str:
    return f"{passage.chapter}.{passage.paragraph}"


def build_passage_lookup(passage_index: PassageIndex) -> dict[str, PassageRecord]:
    return {passage.passage_id: passage for passage in passage_index.passages}


def build_position_lookup(passage_index: PassageIndex) -> dict[str, int]:
    return {passage.passage_id: index for index, passage in enumerate(passage_index.passages)}


def format_display_citation(*, display_format: str, citation_number: int, passage: PassageRecord) -> str:
    return display_format.format(
        citation_number=citation_number,
        chapter=passage.chapter,
        paragraph=passage.paragraph,
        passage_id=passage.passage_id,
    )


def citation_anchor_id(citation_number: int) -> str:
    return f"citation-{citation_number}"


def is_valid_citation_marker(marker: str) -> bool:
    return bool(CANONICAL_CITATION_RE.fullmatch(marker) or DISPLAY_CITATION_RE.fullmatch(marker))


def extract_citation_passage_ids(text: str) -> list[str]:
    matches: list[tuple[int, str]] = []

    for match in CANONICAL_CITATION_RE.finditer(text):
        matches.append((match.start(), f"{int(match.group(1))}.{int(match.group(2))}"))

    for match in DISPLAY_CITATION_RE.finditer(text):
        matches.append((match.start(), f"{int(match.group(2))}.{int(match.group(3))}"))

    return [passage_id for _, passage_id in sorted(matches, key=lambda item: item[0])]


def extract_invalid_bracket_markers(text: str) -> list[str]:
    invalid: list[str] = []
    for match in ANY_BRACKET_RE.finditer(text):
        marker = match.group(0)
        if not is_valid_citation_marker(marker):
            invalid.append(marker)
    return invalid


def collect_context_passages(
    passage_index: PassageIndex,
    *,
    passage_id: str,
    count_before: int,
    count_after: int,
) -> tuple[list[PassageRecord], list[PassageRecord]]:
    passage_lookup = build_passage_lookup(passage_index)
    position_lookup = build_position_lookup(passage_index)
    if passage_id not in passage_lookup:
        raise ValueError(f"Passage ID does not exist in passage index: {passage_id}")

    current_passage = passage_lookup[passage_id]
    current_position = position_lookup[passage_id]

    previous_passages: list[PassageRecord] = []
    next_passages: list[PassageRecord] = []

    for offset in range(1, count_before + 1):
        candidate_position = current_position - offset
        if candidate_position < 0:
            break
        candidate = passage_index.passages[candidate_position]
        if candidate.chapter != current_passage.chapter:
            break
        previous_passages.insert(0, candidate)

    for offset in range(1, count_after + 1):
        candidate_position = current_position + offset
        if candidate_position >= len(passage_index.passages):
            break
        candidate = passage_index.passages[candidate_position]
        if candidate.chapter != current_passage.chapter:
            break
        next_passages.append(candidate)

    return previous_passages, next_passages


def build_context_payload(
    passage_index: PassageIndex,
    *,
    passage_id: str,
    count_before: int,
    count_after: int,
) -> dict[str, object]:
    passage_lookup = build_passage_lookup(passage_index)
    current_passage = passage_lookup[passage_id]
    previous_passages, next_passages = collect_context_passages(
        passage_index,
        passage_id=passage_id,
        count_before=count_before,
        count_after=count_after,
    )

    return {
        "cited_passage": {
            "passage_id": current_passage.passage_id,
            "chapter": current_passage.chapter,
            "paragraph": current_passage.paragraph,
            "text": current_passage.text,
        },
        "previous_passages": [
            {
                "passage_id": passage.passage_id,
                "chapter": passage.chapter,
                "paragraph": passage.paragraph,
                "text": passage.text,
            }
            for passage in previous_passages
        ],
        "next_passages": [
            {
                "passage_id": passage.passage_id,
                "chapter": passage.chapter,
                "paragraph": passage.paragraph,
                "text": passage.text,
            }
            for passage in next_passages
        ],
    }


def build_citation_registry(
    text: str,
    passage_index: PassageIndex,
    *,
    display_format: str,
) -> list[CitationRegistryEntry]:
    passage_lookup = build_passage_lookup(passage_index)
    registry: list[CitationRegistryEntry] = []
    seen_passage_ids: set[str] = set()

    for passage_id in extract_citation_passage_ids(text):
        if passage_id in seen_passage_ids:
            continue
        if passage_id not in passage_lookup:
            continue
        seen_passage_ids.add(passage_id)
        passage = passage_lookup[passage_id]
        citation_number = len(registry) + 1
        registry.append(
            CitationRegistryEntry(
                citation_number=citation_number,
                display_label=format_display_citation(
                    display_format=display_format,
                    citation_number=citation_number,
                    passage=passage,
                ),
                canonical_locator=f"[{canonical_locator_from_passage(passage)}]",
                passage_id=passage.passage_id,
                chapter=passage.chapter,
                paragraph=passage.paragraph,
                exact_passage_text=passage.text,
            )
        )

    return registry


def render_text_with_display_citations(text: str, registry: list[CitationRegistryEntry]) -> str:
    display_lookup = {
        entry.passage_id: (entry.display_label, citation_anchor_id(entry.citation_number))
        for entry in registry
    }

    def replace(match: re.Match[str]) -> str:
        passage_id = f"{int(match.group(1))}.{int(match.group(2))}"
        display_entry = display_lookup.get(passage_id)
        if display_entry is None:
            return match.group(0)
        display_label, anchor = display_entry
        return f"<a href='#{anchor}'><u>{display_label}</u></a>"

    return CANONICAL_CITATION_RE.sub(replace, text)


def italicize_quoted_text(text: str) -> str:
    italicized = STRAIGHT_DOUBLE_QUOTE_RE.sub(r'*"\1"*', text)
    return CURLY_DOUBLE_QUOTE_RE.sub(r"*“\1”*", italicized)


def strip_legacy_citation_note(text: str) -> str:
    stripped = LEGACY_CITATION_NOTE_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def shrink_body_headings(text: str) -> str:
    return BODY_SECTION_HEADING_RE.sub("### ", text)


def render_citations_appendix(
    registry: list[CitationRegistryEntry],
    *,
    heading: str,
) -> str:
    if not registry:
        return f"## {heading}\n\nNo citations were recorded.\n"

    parts = [f"## {heading}", ""]
    for entry in registry:
        parts.extend(
            [
                f"### <a id='{citation_anchor_id(entry.citation_number)}'></a>{entry.display_label}",
                "",
                italicize_quoted_text(f"> {entry.exact_passage_text}"),
                "",
            ]
        )
    return "\n".join(parts).strip() + "\n"


def render_report_with_citation_appendix(
    body_text: str,
    registry: list[CitationRegistryEntry],
    *,
    appendix_heading: str,
) -> str:
    rendered_body = strip_legacy_citation_note(body_text.strip())
    rendered_body = render_text_with_display_citations(rendered_body, registry).strip()
    rendered_body = italicize_quoted_text(rendered_body)
    rendered_body = shrink_body_headings(rendered_body)
    appendix = render_citations_appendix(registry, heading=appendix_heading).strip()
    return rendered_body + "\n\n" + appendix + "\n"


def write_citation_registry(config: AppConfig, registry: list[CitationRegistryEntry]) -> None:
    output_path = config.citation_registry_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([entry.model_dump() for entry in registry], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
