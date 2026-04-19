"""
Deterministic structural QA for translated reports.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.translation_common import (
    count_quote_spans,
    extract_heading_levels,
    extract_visible_citation_markers,
    load_english_master,
)

LOGGER = logging.getLogger(__name__)


def load_translation_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Translated report not found: {path}")
    return path.read_text(encoding="utf-8")


def build_translation_qa_report(
    *,
    language: str,
    english_master: str,
    translated_text: str,
) -> dict[str, object]:
    english_headings = extract_heading_levels(english_master)
    translated_headings = extract_heading_levels(translated_text)
    english_citations = extract_visible_citation_markers(english_master)
    translated_citations = extract_visible_citation_markers(translated_text)
    english_quote_spans = count_quote_spans(english_master)
    translated_quote_spans = count_quote_spans(translated_text)

    heading_count_match = len(english_headings) == len(translated_headings)
    section_order_match = english_headings == translated_headings
    citation_count_match = english_citations == translated_citations
    quote_marker_count_match = english_quote_spans == translated_quote_spans
    non_empty_translation = bool(translated_text.strip())

    major_issues: list[str] = []
    if not non_empty_translation:
        major_issues.append("Translated output is empty.")
    if not heading_count_match:
        major_issues.append("Heading count does not match the English master.")
    elif not section_order_match:
        major_issues.append("Heading levels or section order do not match the English master.")
    if not citation_count_match:
        major_issues.append("Citation marker inventory does not match the English master.")
    if not quote_marker_count_match:
        major_issues.append("Quoted-span count does not match the English master.")

    notes = "No major structural mismatch detected." if not major_issues else " ".join(major_issues)
    return {
        "language": language,
        "generated_at": utc_now_iso(),
        "heading_count_match": heading_count_match,
        "section_order_match": section_order_match,
        "citation_count_match": citation_count_match,
        "quote_marker_count_match": quote_marker_count_match,
        "non_empty_translation": non_empty_translation,
        "major_issues": major_issues,
        "notes": notes,
    }


def write_translation_qa_report(output_path: Path, report: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote translation QA report to %s", output_path)


def qa_spanish(
    config: AppConfig,
    *,
    english_master_text: str | None = None,
    translated_text: str | None = None,
) -> dict[str, object]:
    master_text = english_master_text or load_english_master(config)
    current_translation = translated_text or load_translation_text(config.spanish_translation_output_path)
    report = build_translation_qa_report(
        language="spanish",
        english_master=master_text,
        translated_text=current_translation,
    )
    write_translation_qa_report(config.spanish_qa_report_path, report)
    return report


def qa_mandarin(
    config: AppConfig,
    *,
    english_master_text: str | None = None,
    translated_text: str | None = None,
) -> dict[str, object]:
    master_text = english_master_text or load_english_master(config)
    current_translation = translated_text or load_translation_text(config.mandarin_translation_output_path)
    report = build_translation_qa_report(
        language="mandarin",
        english_master=master_text,
        translated_text=current_translation,
    )
    write_translation_qa_report(config.mandarin_qa_report_path, report)
    return report
