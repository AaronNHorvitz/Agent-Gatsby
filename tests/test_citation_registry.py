from __future__ import annotations

from agent_gatsby.citation_registry import (
    build_citation_registry,
    build_context_payload,
    extract_citation_passage_ids,
    render_citation_text_document,
    render_final_report,
)
from agent_gatsby.schemas import PassageIndex, PassageRecord


def sample_passage_index() -> PassageIndex:
    return PassageIndex(
        source_name="gatsby_locked",
        normalized_path="data/normalized/gatsby_locked.txt",
        chapter_count=2,
        passage_count=4,
        generated_at="2026-04-18T00:00:00Z",
        passages=[
            PassageRecord(
                passage_id="1.1",
                chapter=1,
                paragraph=1,
                text="Nick arrives with a cautious sense of distance from the East.",
                char_start=0,
                char_end=58,
            ),
            PassageRecord(
                passage_id="1.2",
                chapter=1,
                paragraph=2,
                text="Gatsby reached toward the green light at the end of the dock.",
                char_start=60,
                char_end=118,
            ),
            PassageRecord(
                passage_id="2.1",
                chapter=2,
                paragraph=1,
                text="Ashes spread outward beneath the billboard and the road.",
                char_start=120,
                char_end=178,
            ),
            PassageRecord(
                passage_id="2.2",
                chapter=2,
                paragraph=2,
                text="The valley of ashes lay under the gray morning like a ruined field.",
                char_start=180,
                char_end=248,
            ),
        ],
    )


def test_extract_citation_passage_ids_handles_canonical_and_display_forms() -> None:
    text = "One [1.2]. Two [#4, Chapter 2, Paragraph 2]."

    assert extract_citation_passage_ids(text) == ["1.2", "2.2"]


def test_build_context_payload_collects_same_chapter_neighbors() -> None:
    context_payload = build_context_payload(
        sample_passage_index(),
        passage_id="1.2",
        count_before=1,
        count_after=1,
    )

    assert context_payload["cited_passage"]["passage_id"] == "1.2"
    assert context_payload["previous_passages"][0]["passage_id"] == "1.1"
    assert context_payload["next_passages"] == []


def test_render_final_report_and_citation_text_document_use_note_numbers_and_exact_text() -> None:
    body_text = (
        "# Old Title\n\n"
        "_Citation note: bracketed locators reference chapter.paragraph positions in the locked source text._\n\n"
        "## Introduction\n\n"
        'The "green light" matters here [1.2].\n'
    )
    registry = build_citation_registry(
        body_text,
        sample_passage_index(),
        display_format="[{citation_number}]",
    )

    rendered_report = render_final_report(
        body_text,
        registry,
        title_override="An Analysis of Metaphors in The Great Gatsby",
        appendix_heading="Citations",
    )
    citation_text = render_citation_text_document(registry, title="Citation Text")

    assert "# An Analysis of Metaphors in The Great Gatsby" in rendered_report
    assert "_Citation note:" not in rendered_report
    assert "## Citations" in rendered_report
    assert "### Introduction" in rendered_report
    assert '*"green light"* matters here [1].' in rendered_report
    assert '1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 2' in rendered_report
    assert "# Citation Text" in citation_text
    assert "## [1]" in citation_text
    assert "Chapter 1, Paragraph 2" in citation_text
    assert "Gatsby reached toward the green light at the end of the dock." in citation_text
