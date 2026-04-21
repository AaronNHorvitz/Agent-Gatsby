"""Deterministic citation registry and report-rendering helpers.

This module converts canonical ``[chapter.paragraph]`` locators into stable
numbered citations for the final reader-facing report, while also preserving a
machine-auditable registry and an exact-source citation-text companion
document.
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
TITLE_HEADING_RE = re.compile(r"(?m)^# .+$")
STRAIGHT_DOUBLE_QUOTE_RE = re.compile(r'(?<!\*)"([^"\n]+?)"(?!\*)')
CURLY_DOUBLE_QUOTE_RE = re.compile(r"(?<!\*)“([^”\n]+?)”(?!\*)")


def canonical_locator_from_passage(passage: PassageRecord) -> str:
    """Return the canonical locator string for a passage.

    Parameters
    ----------
    passage : PassageRecord
        Indexed passage record.

    Returns
    -------
    str
        Canonical ``chapter.paragraph`` locator.
    """

    return f"{passage.chapter}.{passage.paragraph}"


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


def build_position_lookup(passage_index: PassageIndex) -> dict[str, int]:
    """Build a passage-position lookup keyed by passage identifier.

    Parameters
    ----------
    passage_index : PassageIndex
        Loaded passage index.

    Returns
    -------
    dict of str to int
        Mapping from ``passage_id`` to source-order position.
    """

    return {passage.passage_id: index for index, passage in enumerate(passage_index.passages)}


def format_display_citation(*, display_format: str, citation_number: int, passage: PassageRecord) -> str:
    """Format a human-readable display citation.

    Parameters
    ----------
    display_format : str
        Display-citation format template.
    citation_number : int
        Sequential citation number.
    passage : PassageRecord
        Passage referenced by the citation.

    Returns
    -------
    str
        Formatted display citation label.
    """

    return display_format.format(
        citation_number=citation_number,
        chapter=passage.chapter,
        paragraph=passage.paragraph,
        passage_id=passage.passage_id,
    )


def is_valid_citation_marker(marker: str) -> bool:
    """Return whether a bracket marker matches a supported citation form.

    Parameters
    ----------
    marker : str
        Bracketed marker string.

    Returns
    -------
    bool
        ``True`` when the marker is canonical or already in display form.
    """

    return bool(CANONICAL_CITATION_RE.fullmatch(marker) or DISPLAY_CITATION_RE.fullmatch(marker))


def extract_citation_passage_ids(text: str) -> list[str]:
    """Extract cited passage identifiers in source order from report text.

    Parameters
    ----------
    text : str
        Report text containing canonical or display citation markers.

    Returns
    -------
    list of str
        Passage identifiers in text order.
    """

    matches: list[tuple[int, str]] = []

    for match in CANONICAL_CITATION_RE.finditer(text):
        matches.append((match.start(), f"{int(match.group(1))}.{int(match.group(2))}"))

    for match in DISPLAY_CITATION_RE.finditer(text):
        matches.append((match.start(), f"{int(match.group(2))}.{int(match.group(3))}"))

    return [passage_id for _, passage_id in sorted(matches, key=lambda item: item[0])]


def extract_invalid_bracket_markers(text: str) -> list[str]:
    """Collect bracket markers that are not valid citations.

    Parameters
    ----------
    text : str
        Text to scan.

    Returns
    -------
    list of str
        Invalid bracket markers in encounter order.
    """

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
    """Collect nearby same-chapter passages around a cited passage.

    Parameters
    ----------
    passage_index : PassageIndex
        Loaded passage index.
    passage_id : str
        Passage identifier to center the context window on.
    count_before : int
        Maximum number of preceding passages to include.
    count_after : int
        Maximum number of following passages to include.

    Returns
    -------
    tuple of (list of PassageRecord, list of PassageRecord)
        Previous and next context passages from the same chapter.

    Raises
    ------
    ValueError
        If the supplied passage identifier does not exist in the index.
    """

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
    """Build a JSON-serializable context payload around a cited passage.

    Parameters
    ----------
    passage_index : PassageIndex
        Loaded passage index.
    passage_id : str
        Passage identifier to center the payload on.
    count_before : int
        Maximum number of preceding passages to include.
    count_after : int
        Maximum number of following passages to include.

    Returns
    -------
    dict of str to object
        Context payload describing the cited passage and neighboring passages.
    """

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
    """Build the numbered citation registry for a report body.

    Parameters
    ----------
    text : str
        Report text containing canonical citations.
    passage_index : PassageIndex
        Loaded passage index used to resolve locators.
    display_format : str
        Display-citation format template.

    Returns
    -------
    list of CitationRegistryEntry
        Unique citation entries in first-use order.
    """

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
    """Replace canonical citations with numbered display citations.

    Parameters
    ----------
    text : str
        Report text containing canonical citations.
    registry : list of CitationRegistryEntry
        Citation registry defining the numbered display labels.

    Returns
    -------
    str
        Text with canonical citations converted to display citations.
    """

    display_lookup = {entry.passage_id: entry.display_label for entry in registry}

    def replace(match: re.Match[str]) -> str:
        """Map one canonical citation match to its numbered display label.

        Parameters
        ----------
        match : re.Match[str]
            Regex match for a canonical citation marker.

        Returns
        -------
        str
            Replacement display citation, or the original text when no registry
            entry exists.
        """

        passage_id = f"{int(match.group(1))}.{int(match.group(2))}"
        display_label = display_lookup.get(passage_id)
        if display_label is None:
            return match.group(0)
        return display_label

    return CANONICAL_CITATION_RE.sub(replace, text)


def build_short_excerpt(text: str, *, max_words: int = 14) -> str:
    """Build a short excerpt for bibliography-style citation rendering.

    Parameters
    ----------
    text : str
        Full source passage text.
    max_words : int, default=14
        Maximum number of words to retain before truncation.

    Returns
    -------
    str
        Truncated excerpt suitable for a citation list entry.
    """

    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(" ,;:") + "..."


def italicize_quoted_text(text: str) -> str:
    """Italicize quoted spans in the rendered report body.

    Parameters
    ----------
    text : str
        Report text with inline quotations.

    Returns
    -------
    str
        Text with straight and curly double-quoted spans wrapped in markdown
        emphasis markers.
    """

    italicized = STRAIGHT_DOUBLE_QUOTE_RE.sub(r'*"\1"*', text)
    return CURLY_DOUBLE_QUOTE_RE.sub(r"*“\1”*", italicized)


def strip_legacy_citation_note(text: str) -> str:
    """Remove legacy citation-note boilerplate from report text.

    Parameters
    ----------
    text : str
        Report text to clean.

    Returns
    -------
    str
        Cleaned report text with legacy note blocks removed.
    """

    stripped = LEGACY_CITATION_NOTE_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def shrink_body_headings(text: str) -> str:
    """Demote body section headings for the final report layout.

    Parameters
    ----------
    text : str
        Report markdown.

    Returns
    -------
    str
        Markdown with body headings reduced from ``##`` to ``###``.
    """

    return BODY_SECTION_HEADING_RE.sub("### ", text)


def normalize_report_title(text: str, *, title_override: str | None) -> str:
    """Apply a canonical title to the final report when configured.

    Parameters
    ----------
    text : str
        Report markdown.
    title_override : str or None
        Replacement title to enforce.

    Returns
    -------
    str
        Markdown with the requested report title applied.
    """

    if not title_override:
        return text
    if TITLE_HEADING_RE.search(text):
        return TITLE_HEADING_RE.sub(f"# {title_override}", text, count=1)
    return f"# {title_override}\n\n{text.strip()}"


def render_citations_section(
    registry: list[CitationRegistryEntry],
    *,
    heading: str,
) -> str:
    """Render the reader-facing citations section for the final report.

    Parameters
    ----------
    registry : list of CitationRegistryEntry
        Numbered citation registry.
    heading : str
        Heading label for the citations section.

    Returns
    -------
    str
        Markdown citations section, or an empty string when no citations exist.
    """

    if not registry:
        return ""

    parts = [f"## {heading}", ""]
    for entry in registry:
        excerpt = build_short_excerpt(entry.exact_passage_text)
        parts.append(
            f"{entry.citation_number}. F. Scott Fitzgerald, *The Great Gatsby*, ch. {entry.chapter}, para. {entry.paragraph}, cited passage beginning \"{excerpt}\"."
        )
    return "\n".join(parts).strip()


def render_final_report(
    body_text: str,
    registry: list[CitationRegistryEntry],
    *,
    title_override: str | None = None,
    appendix_heading: str = "Citations",
) -> str:
    """Render the final reader-facing English report.

    Parameters
    ----------
    body_text : str
        Report body using canonical citations.
    registry : list of CitationRegistryEntry
        Numbered citation registry.
    title_override : str or None, optional
        Replacement title for the report.
    appendix_heading : str, default="Citations"
        Heading used for the citations appendix.

    Returns
    -------
    str
        Final rendered report with display citations and appendix.
    """

    rendered_body = strip_legacy_citation_note(body_text.strip())
    rendered_body = normalize_report_title(rendered_body, title_override=title_override)
    rendered_body = render_text_with_display_citations(rendered_body, registry).strip()
    rendered_body = italicize_quoted_text(rendered_body)
    rendered_body = shrink_body_headings(rendered_body)
    citations_section = render_citations_section(registry, heading=appendix_heading)
    if citations_section:
        rendered_body = rendered_body.strip() + "\n\n" + citations_section
    return rendered_body.strip() + "\n"


def render_citation_text_document(
    registry: list[CitationRegistryEntry],
    *,
    title: str,
) -> str:
    """Render the exact-source citation companion document.

    Parameters
    ----------
    registry : list of CitationRegistryEntry
        Numbered citation registry.
    title : str
        Title for the citation-text document.

    Returns
    -------
    str
        Markdown document listing exact source passages for each numbered
        citation.
    """

    if not registry:
        return f"# {title}\n\nNo citation text entries were recorded.\n"

    parts = [
        f"# {title}",
        "",
        "This document lists the exact English source passages referenced by the numbered citations in the essays.",
        "It is provided separately so the main report can stay readable while the evidence remains auditable.",
        "",
    ]
    for entry in registry:
        parts.extend(
            [
                f"## {entry.display_label}",
                "",
                f"Chapter {entry.chapter}, Paragraph {entry.paragraph}",
                "",
                entry.exact_passage_text,
                "",
            ]
        )
    return "\n".join(parts).strip() + "\n"


def write_citation_registry(config: AppConfig, registry: list[CitationRegistryEntry]) -> None:
    """Write the citation registry artifact to disk.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    registry : list of CitationRegistryEntry
        Citation registry to serialize.

    Returns
    -------
    None
        The citation registry is written to the configured artifact path.
    """

    output_path = config.citation_registry_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([entry.model_dump() for entry in registry], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_citation_text_document(config: AppConfig, document_text: str) -> None:
    """Write the citation-text companion document to disk.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    document_text : str
        Rendered citation-text document.

    Returns
    -------
    None
        The document is written to the configured output path.
    """

    output_path = config.citation_text_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document_text, encoding="utf-8")
