from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_gatsby.schemas import CitationRegistryEntry, EvidenceRecord, PassageRecord, VerificationIssue, VerificationReport


def test_schema_models_accept_expected_fields_and_defaults() -> None:
    record = EvidenceRecord(
        evidence_id="E001",
        metaphor="green light",
        quote="green light",
        passage_id="1.1",
        chapter=1,
        interpretation="A recurring image that condenses Gatsby's longing.",
        status="verified",
    )
    report = VerificationReport(
        stage="verify_english",
        status="passed",
        generated_at="2026-04-18T00:00:00Z",
        word_count=2800,
        estimated_pages=10.0,
        quote_checks_total=12,
        quote_checks_passed=12,
        citation_checks_total=15,
        citation_checks_passed=15,
        invalid_quote_rate=0.0,
        invalid_citation_rate=0.0,
        prose_sentence_count=100,
        unsupported_sentence_count=3,
        unsupported_sentence_ratio=0.03,
        issues=[VerificationIssue(code="warning", message="Advisory only")],
    )
    citation_entry = CitationRegistryEntry(
        citation_number=1,
        display_label="[#1, Chapter 1, Paragraph 4]",
        canonical_locator="[1.4]",
        passage_id="1.4",
        chapter=1,
        paragraph=4,
        exact_passage_text="Example cited passage text.",
    )

    assert record.supporting_theme_tags == []
    assert record.source_type == "candidate"
    assert report.issues[0].message == "Advisory only"
    assert report.word_count == 2800
    assert report.unsupported_sentence_ratio == 0.03
    assert citation_entry.canonical_locator == "[1.4]"


def test_schema_models_reject_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        PassageRecord.model_validate(
            {
                "passage_id": "1.1",
                "chapter": 1,
                "paragraph": 1,
                "text": "Example passage text.",
                "char_start": 0,
                "char_end": 21,
                "unexpected": True,
            }
        )
