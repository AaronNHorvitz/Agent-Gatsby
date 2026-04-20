from __future__ import annotations

from pathlib import Path

from agent_gatsby.final_artifact_audit import build_pdf_audit_report, pdf_audit_reports_are_renderable


def test_build_pdf_audit_report_flags_spanish_contamination() -> None:
    report = build_pdf_audit_report(
        language="spanish",
        pdf_path=Path("spanish.pdf"),
        extracted_text='la luna prematura AGCIT себя [10] y como si la casa hubiera guiñado un$\\\\un ojo [12]. juegos nerviosos y esporádíamos [15].',
    )

    assert report["status"] == "failed"
    assert report["internal_token_issue_count"] >= 1
    assert report["foreign_script_issue_count"] >= 1
    assert report["escape_sequence_issue_count"] >= 1
    assert report["known_bad_token_count"] >= 1
    assert report["citation_neighborhood_issue_count"] >= 1


def test_build_pdf_audit_report_flags_english_known_regressions() -> None:
    report = build_pdf_audit_report(
        language="english",
        pdf_path=Path("english.pdf"),
        extracted_text="The Valley of West was there, and Gatsby tried to maintain a punctiliously manner.",
    )

    assert report["status"] == "failed"
    assert report["known_bad_token_count"] >= 2


def test_build_pdf_audit_report_flags_mandarin_punctuation_bleed() -> None:
    report = build_pdf_audit_report(
        language="mandarin",
        pdf_path=Path("mandarin.pdf"),
        extracted_text="这构成了听觉意象……………… [30]",
    )

    assert report["status"] == "failed"
    assert report["repeated_ellipsis_issue_count"] >= 1
    assert report["citation_neighborhood_issue_count"] >= 1


def test_pdf_audit_reports_are_renderable_requires_all_reports_to_pass() -> None:
    reports = {
        "english": {"status": "passed"},
        "spanish": {"status": "failed"},
        "mandarin": {"status": "passed"},
    }

    assert pdf_audit_reports_are_renderable(reports) is False
