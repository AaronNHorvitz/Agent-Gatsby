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
LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’.-]*")
NUMBERED_LIST_LINE_RE = re.compile(r"^\d+\.\s+")
CITATION_GLUE_RE = re.compile(r"\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\](?=[A-Za-zÁ-ÿ一-龯])")
MIXED_CJK_LATIN_RE = re.compile(r"(?:[A-Za-z][A-Za-z'’.-]*[\u4e00-\u9fff]|[\u4e00-\u9fff][A-Za-z][A-Za-z'’.-]*)")
VISIBLE_CITATION_RE = re.compile(r"\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\]")
INTERNAL_TOKEN_RE = re.compile(r"AGCIT\w*")
ESCAPE_SEQUENCE_RE = re.compile(r"\$\\\\\w+\b|\\[A-Za-z]+\b")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]+")
HAN_RE = re.compile(r"[\u4e00-\u9fff]+")
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\u2060\ufeff]")
REPEATED_ELLIPSIS_BEFORE_CITATION_RE = re.compile(
    r"[.…]{2,}\s*(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])"
)
MANDARIN_TERMINAL_PUNCTUATION_BEFORE_CITATION_RE = re.compile(r"[。！？]\s*\[(?:\d+|\d+\.\d+)\]")
MANDARIN_ASCII_COMMA_AFTER_CITATION_RE = re.compile(r"\[(?:\d+|\d+\.\d+)\],")
FORBIDDEN_MANDARIN_VARIANTS = ("菲茨平", "菲茨格拉德")
LEAKED_MARKDOWN_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+#\s+.+$")
UNLOCALIZED_BIBLIOGRAPHY_RE = re.compile(r"cited passage beginning|The Great Gatsby")
KNOWN_BAD_SPANISH_TOKENS = (
    "esporádíamos",
    "masimvo",
    "inestímulo",
    "colapiente",
    "desibuja",
    "música de cóctel amarillo",
    "cesta de un catering",
    "su encuentro era un tónico salvaje bajo la lluvia",
    "laberinto de pantallas",
    "robustecido hasta alcanzar la sustancialidad de un hombre",
    "acervo común de la vida",
    "recinto de cuero verde",
    "experiencia altamente curada",
    "dinero viejo y el nuevo",
    "la perfección agresiva y curada",
    "irrealidad de la realidad",
    "rompe físicamente",
    "se rompe literalmente como el cristal",
    "borde irregular del universo",
    "el gran y húmedo corral de Long Island Sound",
    'surgió de su concepción platónica de sí mismo". [13]',
)
KNOWN_BAD_MANDARIN_TOKENS: tuple[str, ...] = (
    "### # 梦想的瓦解",
    "veiled",
    "casual gaming",
    "叙述者最初仅仅是一个人的轮廓",
    "柏拉图式的观念 [13] 与其说",
    "[24]，其叙述",
    "[25]，将叙述者的内在不稳定性",
    "[30] 回声",
    "T. J. 艾克尔堡医生",
    "长岛海峡那巨大的湿润农场",
    "长岛海峡那巨大的湿润院落",
    "谷仓院",
    "从他对自己的一种柏拉图式的构想中脱颖而出",
    "杰·盖茨比",
    "整个大篷车营地就像纸牌屋一样坍塌了",
    "他的眼中不断流露出激动",
    "构成了听觉意象 [30]；这构成了",
    "现实的非真实性",
    "字面上",
    "物理层面",
    "情妇",
    "补剂",
    "男人和姑娘们",
    "人群的旋涡与涡流",
    "从餐饮师的篮子里变出来的",
    "已充实成了一个男人的实体",
    "一打太阳",
    "世界博览会",
)
ENGLISH_HINT_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "for",
    "from",
    "had",
    "has",
    "her",
    "his",
    "in",
    "into",
    "is",
    "it",
    "like",
    "my",
    "of",
    "on",
    "our",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
}
SPANISH_HINT_WORDS = {
    "al",
    "como",
    "con",
    "de",
    "del",
    "el",
    "en",
    "era",
    "es",
    "esta",
    "la",
    "las",
    "lo",
    "los",
    "más",
    "para",
    "por",
    "que",
    "se",
    "su",
    "sus",
    "un",
    "una",
    "y",
}


def load_translation_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Translated report not found: {path}")
    return path.read_text(encoding="utf-8")


def span_looks_untranslated_english(span: str) -> bool:
    if not ENGLISH_MULTIWORD_RE.search(span):
        return False
    tokens = [token.lower() for token in LATIN_WORD_RE.findall(span)]
    if len(tokens) < 3:
        return False
    english_hint_count = sum(1 for token in tokens if token in ENGLISH_HINT_WORDS)
    spanish_hint_count = sum(1 for token in tokens if token in SPANISH_HINT_WORDS)
    if english_hint_count >= 2 and english_hint_count > spanish_hint_count:
        return True
    ascii_only = all(ord(char) < 128 for char in span)
    return ascii_only and spanish_hint_count == 0


def find_untranslated_body_quotes(text: str) -> list[str]:
    return [span for span in extract_quote_spans(text) if span_looks_untranslated_english(span)]


def count_protected_quote_units(text: str) -> int:
    total = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if not (stripped.startswith(">") or NUMBERED_LIST_LINE_RE.match(stripped)):
            continue
        if extract_quote_spans(line):
            total += 1
    return total


def find_citation_glue_issues(text: str) -> list[str]:
    return [match.group(0) for match in CITATION_GLUE_RE.finditer(text)]


def find_mixed_script_issues(text: str) -> list[str]:
    return [match.group(0) for match in MIXED_CJK_LATIN_RE.finditer(text)]


def find_forbidden_mandarin_variants(text: str) -> list[str]:
    return [variant for variant in FORBIDDEN_MANDARIN_VARIANTS if variant in text]


def find_internal_token_issues(text: str) -> list[str]:
    return [match.group(0) for match in INTERNAL_TOKEN_RE.finditer(text)]


def find_escape_sequence_issues(text: str) -> list[str]:
    return [match.group(0) for match in ESCAPE_SEQUENCE_RE.finditer(text)]


def find_zero_width_issues(text: str) -> list[str]:
    return [match.group(0) for match in ZERO_WIDTH_RE.finditer(text)]


def find_spanish_foreign_script_issues(text: str) -> list[str]:
    issues: list[str] = []
    issues.extend(match.group(0) for match in CYRILLIC_RE.finditer(text))
    issues.extend(match.group(0) for match in HAN_RE.finditer(text))
    return issues


def find_repeated_ellipsis_before_citations(text: str) -> list[str]:
    return [match.group(0) for match in REPEATED_ELLIPSIS_BEFORE_CITATION_RE.finditer(text)]


def find_known_bad_tokens(text: str, tokens: tuple[str, ...]) -> list[str]:
    issues: list[str] = []
    for token in tokens:
        issues.extend(token for _ in range(text.count(token)))
    return issues


def find_markdown_heading_leaks(text: str) -> list[str]:
    return [match.group(0) for match in LEAKED_MARKDOWN_HEADING_RE.finditer(text)]


def find_bibliography_localization_issues(text: str) -> list[str]:
    return [match.group(0) for match in UNLOCALIZED_BIBLIOGRAPHY_RE.finditer(text)]


def find_citation_neighborhood_issues(
    text: str,
    *,
    language: str,
    known_bad_tokens: tuple[str, ...] = (),
) -> list[str]:
    issues: list[str] = []
    normalized_language = language.lower()
    for match in VISIBLE_CITATION_RE.finditer(text):
        start = max(0, match.start() - 24)
        end = min(len(text), match.end() + 24)
        window = text[start:end]
        has_issue = False
        if find_internal_token_issues(window) or find_escape_sequence_issues(window):
            has_issue = True
        if normalized_language == "spanish" and find_spanish_foreign_script_issues(window):
            has_issue = True
        if normalized_language == "mandarin":
            if find_repeated_ellipsis_before_citations(window):
                has_issue = True
            if MANDARIN_TERMINAL_PUNCTUATION_BEFORE_CITATION_RE.search(window):
                has_issue = True
            if MANDARIN_ASCII_COMMA_AFTER_CITATION_RE.search(window):
                has_issue = True
        if known_bad_tokens and find_known_bad_tokens(window, known_bad_tokens):
            has_issue = True
        if has_issue:
            issues.append(window)
    return issues


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
    english_quote_spans = count_protected_quote_units(english_master)
    translated_quote_spans = count_protected_quote_units(translated_text)
    untranslated_body_quotes = find_untranslated_body_quotes(translated_body)
    citation_glue_issues = find_citation_glue_issues(translated_body)
    citations_section_present = bool(translated_citations_section.strip())
    english_citation_entry_count = count_numbered_citation_entries(english_citations_section)
    translated_citation_entry_count = count_numbered_citation_entries(translated_citations_section)
    citation_entry_count_match = english_citation_entry_count == translated_citation_entry_count
    citations_heading_without_entries = citations_section_present and translated_citation_entry_count == 0
    internal_token_issues = find_internal_token_issues(translated_text)
    escape_sequence_issues = find_escape_sequence_issues(translated_text)
    zero_width_issues = find_zero_width_issues(translated_text)
    foreign_script_issues: list[str] = []
    repeated_ellipsis_issues: list[str] = []
    known_bad_tokens: list[str] = []
    mixed_script_issues: list[str] = []
    forbidden_mandarin_variants: list[str] = []
    markdown_heading_leaks: list[str] = []
    bibliography_localization_issues: list[str] = []
    if language.lower() == "spanish":
        foreign_script_issues = find_spanish_foreign_script_issues(translated_text)
        known_bad_tokens = find_known_bad_tokens(translated_text, KNOWN_BAD_SPANISH_TOKENS)
        bibliography_localization_issues = find_bibliography_localization_issues(translated_citations_section)
    if language.lower() == "mandarin":
        mixed_script_issues = find_mixed_script_issues(translated_body)
        forbidden_mandarin_variants = find_forbidden_mandarin_variants(translated_body)
        repeated_ellipsis_issues = find_repeated_ellipsis_before_citations(translated_text)
        known_bad_tokens = find_known_bad_tokens(translated_text, KNOWN_BAD_MANDARIN_TOKENS)
        markdown_heading_leaks = find_markdown_heading_leaks(translated_text)
        bibliography_localization_issues = find_bibliography_localization_issues(translated_citations_section)
    citation_neighborhood_issues = find_citation_neighborhood_issues(
        translated_text,
        language=language,
        known_bad_tokens=KNOWN_BAD_SPANISH_TOKENS if language.lower() == "spanish" else KNOWN_BAD_MANDARIN_TOKENS,
    )

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
    if internal_token_issues:
        major_issues.append("Translated output leaked internal placeholder or helper tokens.")
    if escape_sequence_issues:
        major_issues.append("Translated output contains escape-sequence artifacts.")
    if zero_width_issues:
        major_issues.append("Translated output contains hidden zero-width characters.")
    if foreign_script_issues:
        major_issues.append("Spanish output contains non-Latin script intrusions.")
    if repeated_ellipsis_issues:
        major_issues.append("Mandarin output contains repeated ellipsis directly before citation markers.")
    if known_bad_tokens:
        major_issues.append("Translated output contains known bad regression tokens.")
    if citation_neighborhood_issues:
        major_issues.append("Translated output contains malformed text adjacent to citation markers.")
    if mixed_script_issues:
        major_issues.append("Mandarin body contains mixed Chinese-English artifacts.")
    if forbidden_mandarin_variants:
        major_issues.append("Mandarin body contains forbidden proper-noun variants.")
    if markdown_heading_leaks:
        major_issues.append("Translated output leaked markdown heading markers into visible text.")
    if bibliography_localization_issues:
        major_issues.append("Translated bibliography metadata was not localized.")

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
        "internal_token_issue_count": len(internal_token_issues),
        "escape_sequence_issue_count": len(escape_sequence_issues),
        "zero_width_issue_count": len(zero_width_issues),
        "foreign_script_issue_count": len(foreign_script_issues),
        "repeated_ellipsis_issue_count": len(repeated_ellipsis_issues),
        "known_bad_token_count": len(known_bad_tokens),
        "citation_neighborhood_issue_count": len(citation_neighborhood_issues),
        "mixed_script_issue_count": len(mixed_script_issues),
        "forbidden_mandarin_variant_count": len(forbidden_mandarin_variants),
        "markdown_heading_leak_count": len(markdown_heading_leaks),
        "bibliography_localization_issue_count": len(bibliography_localization_issues),
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
    if english_entry_count != translated_entry_count:
        return False
    required_zero_fields = (
        "untranslated_body_quote_count",
        "citation_glue_issue_count",
        "internal_token_issue_count",
        "escape_sequence_issue_count",
        "zero_width_issue_count",
        "foreign_script_issue_count",
        "repeated_ellipsis_issue_count",
        "known_bad_token_count",
        "citation_neighborhood_issue_count",
        "mixed_script_issue_count",
        "forbidden_mandarin_variant_count",
        "markdown_heading_leak_count",
        "bibliography_localization_issue_count",
    )
    return all(int(report.get(field, 0) or 0) == 0 for field in required_zero_fields)
