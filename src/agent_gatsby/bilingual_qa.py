"""
Deterministic structural QA for translated reports.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.translation_common import (
    count_protected_quote_spans,
    count_numbered_citation_entries,
    extract_quote_spans,
    extract_heading_levels,
    extract_visible_citation_markers,
    load_english_master,
    split_body_and_citations,
    split_translated_output_and_citations,
)

LOGGER = logging.getLogger(__name__)

ENGLISH_MULTIWORD_RE = re.compile(r"[A-Za-z][A-Za-z'’.-]*(?:\s+[a-z][A-Za-z'’.-]*){2,}")
CITATION_GLUE_RE = re.compile(r"\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\](?=[A-Za-zÁ-ÿ一-龯])")
MIXED_CJK_LATIN_RE = re.compile(r"(?:[A-Za-z][A-Za-z'’.-]*[\u4e00-\u9fff]|[\u4e00-\u9fff][A-Za-z][A-Za-z'’.-]*)")
FORBIDDEN_MANDARIN_VARIANTS = ("菲茨平", "菲茨格拉德")


def load_translation_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Translated report not found: {path}")
    return path.read_text(encoding="utf-8")


def find_untranslated_body_quotes(text: str) -> list[str]:
    return [span for span in extract_quote_spans(text) if ENGLISH_MULTIWORD_RE.search(span)]


def find_citation_glue_issues(text: str) -> list[str]:
    return [match.group(0) for match in CITATION_GLUE_RE.finditer(text)]


def find_mixed_script_issues(text: str) -> list[str]:
    return [match.group(0) for match in MIXED_CJK_LATIN_RE.finditer(text)]


def find_forbidden_mandarin_variants(text: str) -> list[str]:
    return [variant for variant in FORBIDDEN_MANDARIN_VARIANTS if variant in text]


def build_translation_qa_report(
    *,
    language: str,
    english_master: str,
    translated_text: str,
) -> dict[str, object]:
    english_body, english_citations_section = split_body_and_citations(english_master)
    translated_body, translated_citations_section = split_translated_output_and_citations(translated_text)
    english_headings = extract_heading_levels(english_master)
    translated_headings = extract_heading_levels(translated_text)
    english_citations = extract_visible_citation_markers(english_master)
    translated_citations = extract_visible_citation_markers(translated_text)
    english_quote_spans = count_protected_quote_spans(english_master)
    translated_quote_spans = count_protected_quote_spans(translated_text)
    untranslated_body_quotes = find_untranslated_body_quotes(translated_body)
    citation_glue_issues = find_citation_glue_issues(translated_body)
    citations_section_present = bool(translated_citations_section.strip())
    english_citation_entry_count = count_numbered_citation_entries(english_citations_section)
    translated_citation_entry_count = count_numbered_citation_entries(translated_citations_section)
    citation_entry_count_match = english_citation_entry_count == translated_citation_entry_count
    citations_heading_without_entries = citations_section_present and translated_citation_entry_count == 0
    mixed_script_issues: list[str] = []
    forbidden_mandarin_variants: list[str] = []
    if language.lower() == "mandarin":
        mixed_script_issues = find_mixed_script_issues(translated_body)
        forbidden_mandarin_variants = find_forbidden_mandarin_variants(translated_body)

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
    if not citations_section_present:
        major_issues.append("Translated output is missing the citations section.")
    elif citations_heading_without_entries:
        major_issues.append("Translated output kept the citations heading but dropped the citation entries.")
    elif not citation_entry_count_match:
        major_issues.append("Citations section entry count does not match the English master.")
    if untranslated_body_quotes:
        major_issues.append("Translated body still contains untranslated English quotation spans.")
    if citation_glue_issues:
        major_issues.append("Translated body has citations glued directly to surrounding prose.")
    if mixed_script_issues:
        major_issues.append("Mandarin body contains mixed Chinese-English artifacts.")
    if forbidden_mandarin_variants:
        major_issues.append("Mandarin body contains forbidden proper-noun variants.")

    notes = "No major structural mismatch detected." if not major_issues else " ".join(major_issues)
    return {
        "language": language,
        "generated_at": utc_now_iso(),
        "heading_count_match": heading_count_match,
        "section_order_match": section_order_match,
        "citation_count_match": citation_count_match,
        "quote_marker_count_match": quote_marker_count_match,
        "citations_section_present": citations_section_present,
        "english_citation_entry_count": english_citation_entry_count,
        "translated_citation_entry_count": translated_citation_entry_count,
        "citation_entry_count_match": citation_entry_count_match,
        "citations_heading_without_entries": citations_heading_without_entries,
        "untranslated_body_quote_count": len(untranslated_body_quotes),
        "citation_glue_issue_count": len(citation_glue_issues),
        "mixed_script_issue_count": len(mixed_script_issues),
        "forbidden_mandarin_variant_count": len(forbidden_mandarin_variants),
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


def translation_report_is_renderable(report: dict[str, object]) -> bool:
    required_true_fields = (
        "non_empty_translation",
        "heading_count_match",
        "section_order_match",
        "citation_count_match",
        "quote_marker_count_match",
        "citations_section_present",
        "citation_entry_count_match",
    )
    if any(report.get(field) is not True for field in required_true_fields):
        return False
    if report.get("citations_heading_without_entries") is True:
        return False
    english_entry_count = int(report.get("english_citation_entry_count", 0) or 0)
    translated_entry_count = int(report.get("translated_citation_entry_count", 0) or 0)
    if english_entry_count <= 0 or translated_entry_count <= 0:
        return False
    return english_entry_count == translated_entry_count
