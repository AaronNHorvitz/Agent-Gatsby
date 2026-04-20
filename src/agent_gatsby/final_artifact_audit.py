"""
Post-render PDF extraction audit for final submission artifacts.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from agent_gatsby.bilingual_qa import (
    find_citation_neighborhood_issues,
    find_escape_sequence_issues,
    find_internal_token_issues,
    find_known_bad_tokens,
    find_repeated_ellipsis_before_citations,
    find_spanish_foreign_script_issues,
)
from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso

LOGGER = logging.getLogger(__name__)

KNOWN_BAD_ENGLISH_TOKENS = ("Valley of West", "punctiliously manner")
KNOWN_BAD_SPANISH_TOKENS = ("esporádíamos",)
KNOWN_BAD_MANDARIN_TOKENS: tuple[str, ...] = ()
AUDIT_LANGUAGE_NAMES = ("english", "spanish", "mandarin")


def pdf_audit_report_path(config: AppConfig, language: str) -> Path:
    default_name = f"{language}_pdf_audit_report.json"
    return config.resolve_repo_path(
        str(
            config.verification.get(
                f"{language}_pdf_audit_output_path",
                f"artifacts/qa/{default_name}",
            )
        )
    )


def pdf_audit_report_paths(config: AppConfig) -> list[Path]:
    return [pdf_audit_report_path(config, language) for language in AUDIT_LANGUAGE_NAMES]


def extract_pdf_text(pdf_path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise FileNotFoundError("pdftotext is required for final PDF audits")
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ValueError(f"pdftotext failed for {pdf_path}: {stderr or 'unknown error'}")
    return result.stdout


def build_pdf_audit_report(*, language: str, pdf_path: Path, extracted_text: str) -> dict[str, object]:
    internal_token_issues = find_internal_token_issues(extracted_text)
    escape_sequence_issues = find_escape_sequence_issues(extracted_text)
    citation_neighborhood_issues = find_citation_neighborhood_issues(extracted_text, language=language)
    known_bad_tokens: list[str] = []
    foreign_script_issues: list[str] = []
    repeated_ellipsis_issues: list[str] = []

    if language == "english":
        known_bad_tokens = find_known_bad_tokens(extracted_text, KNOWN_BAD_ENGLISH_TOKENS)
    elif language == "spanish":
        known_bad_tokens = find_known_bad_tokens(extracted_text, KNOWN_BAD_SPANISH_TOKENS)
        foreign_script_issues = find_spanish_foreign_script_issues(extracted_text)
        citation_neighborhood_issues = find_citation_neighborhood_issues(
            extracted_text,
            language=language,
            known_bad_tokens=KNOWN_BAD_SPANISH_TOKENS,
        )
    elif language == "mandarin":
        known_bad_tokens = find_known_bad_tokens(extracted_text, KNOWN_BAD_MANDARIN_TOKENS)
        repeated_ellipsis_issues = find_repeated_ellipsis_before_citations(extracted_text)
        citation_neighborhood_issues = find_citation_neighborhood_issues(
            extracted_text,
            language=language,
            known_bad_tokens=KNOWN_BAD_MANDARIN_TOKENS,
        )

    major_issues: list[str] = []
    if internal_token_issues:
        major_issues.append("Rendered PDF text leaked internal tokens.")
    if escape_sequence_issues:
        major_issues.append("Rendered PDF text contains escape-sequence artifacts.")
    if foreign_script_issues:
        major_issues.append("Rendered Spanish PDF contains non-Latin script intrusions.")
    if repeated_ellipsis_issues:
        major_issues.append("Rendered Mandarin PDF contains repeated ellipsis before citation markers.")
    if known_bad_tokens:
        major_issues.append("Rendered PDF text contains known regression strings.")
    if citation_neighborhood_issues:
        major_issues.append("Rendered PDF text contains malformed citation-adjacent neighborhoods.")

    return {
        "stage": "audit_final_pdfs",
        "language": language,
        "generated_at": utc_now_iso(),
        "pdf_path": str(pdf_path),
        "status": "passed" if not major_issues else "failed",
        "internal_token_issue_count": len(internal_token_issues),
        "escape_sequence_issue_count": len(escape_sequence_issues),
        "foreign_script_issue_count": len(foreign_script_issues),
        "repeated_ellipsis_issue_count": len(repeated_ellipsis_issues),
        "known_bad_token_count": len(known_bad_tokens),
        "citation_neighborhood_issue_count": len(citation_neighborhood_issues),
        "major_issues": major_issues,
    }


def write_pdf_audit_report(output_path: Path, report: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s PDF audit report to %s", report["language"], output_path)


def audit_rendered_pdfs(config: AppConfig) -> dict[str, dict[str, object]]:
    reports: dict[str, dict[str, object]] = {}
    pdf_paths = {
        "english": config.english_pdf_output_path,
        "spanish": config.spanish_pdf_output_path,
        "mandarin": config.mandarin_pdf_output_path,
    }
    for language, pdf_path in pdf_paths.items():
        report = build_pdf_audit_report(
            language=language,
            pdf_path=pdf_path,
            extracted_text=extract_pdf_text(pdf_path),
        )
        write_pdf_audit_report(pdf_audit_report_path(config, language), report)
        reports[language] = report
    return reports


def pdf_audit_reports_are_renderable(reports: dict[str, dict[str, object]]) -> bool:
    return all(report.get("status") == "passed" for report in reports.values())
