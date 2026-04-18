from __future__ import annotations

from agent_gatsby.citation_registry import (
    build_citation_registry,
    build_context_payload,
    extract_citation_passage_ids,
    render_report_with_citation_appendix,
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


def test_render_report_with_citation_appendix_uses_display_labels_and_exact_text() -> None:
    body_text = (
        "# Sample Essay\n\n"
        "_Citation note: bracketed locators reference chapter.paragraph positions in the locked source text._\n\n"
        "## Introduction\n\n"
        'The "green light" matters here [1.2].\n'
    )
    registry = build_citation_registry(
        body_text,
        sample_passage_index(),
        display_format="[#{citation_number}, Chapter {chapter}, Paragraph {paragraph}]",
    )

    rendered = render_report_with_citation_appendix(body_text, registry, appendix_heading="Citations")

    assert "<a href='#citation-1'><u>[#1, Chapter 1, Paragraph 2]</u></a>" in rendered
    assert "## Citations" in rendered
    assert "Canonical locator:" not in rendered
    assert "_Citation note:" not in rendered
    assert "### Introduction" in rendered
    assert '*"green light"*' in rendered
    assert "### <a id='citation-1'></a>[#1, Chapter 1, Paragraph 2]" in rendered
    assert "Gatsby reached toward the green light at the end of the dock." in rendered
