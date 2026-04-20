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
    find_bibliography_localization_issues,
    find_citation_neighborhood_issues,
    find_escape_sequence_issues,
    find_internal_token_issues,
    find_known_bad_tokens,
    find_markdown_heading_leaks,
    find_repeated_ellipsis_before_citations,
    find_spanish_foreign_script_issues,
    find_zero_width_issues,
)
from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.translation_common import find_unquoted_english_quote_reuse

LOGGER = logging.getLogger(__name__)

KNOWN_BAD_ENGLISH_TOKENS = (
    "Valley of West",
    "punctiliously manner",
    "theragged edge",
    "it actively populating the landscape",
    "to fit an approximately ten-page assignment requirement",
    "could be expanded with additional metaphor clusters if a longer study were desired",
    "sea-change of color and voice",
    "unreality of reality",
    "This fragility becomes literal during the confrontation with Tom",
    "physically breaks the carefully curated veneer",
    "a complex, labyrinth of windshields",
    "the persona of Jay Gatsby literally broken up like glass",
    "look out over the solemn dumping ground [5]",
    "a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity [6]",
    "the thin and far away [30] echoes of a dead dream",
    'The social world Gatsby built is revealed to be "the whole caravansary" that has fallen like a card house [21]',
)
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


def extract_pdf_page_count(pdf_path: Path) -> int | None:
    if shutil.which("pdfinfo") is None:
        LOGGER.warning("pdfinfo is unavailable; skipping page-count audit for %s", pdf_path)
        return None
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        LOGGER.warning("pdfinfo failed for %s: %s", pdf_path, result.stderr.strip() or "unknown error")
        return None
    for line in result.stdout.splitlines():
        if not line.startswith("Pages:"):
            continue
        try:
            return int(line.split(":", maxsplit=1)[1].strip())
        except ValueError:
            LOGGER.warning("Could not parse page count from pdfinfo output for %s", pdf_path)
            return None
    LOGGER.warning("pdfinfo did not report page count for %s", pdf_path)
    return None


def build_pdf_audit_report(
    *,
    language: str,
    pdf_path: Path,
    extracted_text: str,
    page_count: int | None = None,
    min_page_count: int | None = None,
    max_page_count: int | None = None,
) -> dict[str, object]:
    internal_token_issues = find_internal_token_issues(extracted_text)
    escape_sequence_issues = find_escape_sequence_issues(extracted_text)
    zero_width_issues = find_zero_width_issues(extracted_text)
    citation_neighborhood_issues = find_citation_neighborhood_issues(extracted_text, language=language)
    known_bad_tokens: list[str] = []
    foreign_script_issues: list[str] = []
    repeated_ellipsis_issues: list[str] = []
    markdown_heading_leaks: list[str] = []
    bibliography_localization_issues: list[str] = []
    unquoted_quote_reuse_matches: list[str] = []
    page_count_issues: list[str] = []

    if language == "english":
        known_bad_tokens = find_known_bad_tokens(extracted_text, KNOWN_BAD_ENGLISH_TOKENS)
        unquoted_quote_reuse_matches = find_unquoted_english_quote_reuse(extracted_text)
    elif language == "spanish":
        known_bad_tokens = find_known_bad_tokens(extracted_text, KNOWN_BAD_SPANISH_TOKENS)
        foreign_script_issues = find_spanish_foreign_script_issues(extracted_text)
        bibliography_localization_issues = find_bibliography_localization_issues(extracted_text)
        citation_neighborhood_issues = find_citation_neighborhood_issues(
            extracted_text,
            language=language,
            known_bad_tokens=KNOWN_BAD_SPANISH_TOKENS,
        )
    elif language == "mandarin":
        known_bad_tokens = find_known_bad_tokens(extracted_text, KNOWN_BAD_MANDARIN_TOKENS)
        repeated_ellipsis_issues = find_repeated_ellipsis_before_citations(extracted_text)
        markdown_heading_leaks = find_markdown_heading_leaks(extracted_text)
        bibliography_localization_issues = find_bibliography_localization_issues(extracted_text)
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
    if zero_width_issues:
        major_issues.append("Rendered PDF text contains hidden zero-width characters.")
    if foreign_script_issues:
        major_issues.append("Rendered Spanish PDF contains non-Latin script intrusions.")
    if repeated_ellipsis_issues:
        major_issues.append("Rendered Mandarin PDF contains repeated ellipsis before citation markers.")
    if known_bad_tokens:
        major_issues.append("Rendered PDF text contains known regression strings.")
    if citation_neighborhood_issues:
        major_issues.append("Rendered PDF text contains malformed citation-adjacent neighborhoods.")
    if markdown_heading_leaks:
        major_issues.append("Rendered PDF text leaked markdown heading markers.")
    if bibliography_localization_issues:
        major_issues.append("Rendered translated PDF kept English bibliography metadata.")
    if unquoted_quote_reuse_matches:
        major_issues.append("Rendered English PDF reused exact source-language quotations without quotation marks.")
    if page_count is not None and (
        (min_page_count is not None and page_count < min_page_count)
        or (max_page_count is not None and page_count > max_page_count)
    ):
        page_count_issues.append(
            f"Rendered {language} PDF page count {page_count} fell outside the expected range "
            f"{min_page_count}-{max_page_count}."
        )
        major_issues.append("Rendered PDF page count fell outside the configured range.")

    return {
        "stage": "audit_final_pdfs",
        "language": language,
        "generated_at": utc_now_iso(),
        "pdf_path": str(pdf_path),
        "status": "passed" if not major_issues else "failed",
        "page_count": page_count,
        "page_count_issue_count": len(page_count_issues),
        "page_count_issues": page_count_issues,
        "internal_token_issue_count": len(internal_token_issues),
        "escape_sequence_issue_count": len(escape_sequence_issues),
        "zero_width_issue_count": len(zero_width_issues),
        "foreign_script_issue_count": len(foreign_script_issues),
        "repeated_ellipsis_issue_count": len(repeated_ellipsis_issues),
        "known_bad_token_count": len(known_bad_tokens),
        "citation_neighborhood_issue_count": len(citation_neighborhood_issues),
        "markdown_heading_leak_count": len(markdown_heading_leaks),
        "bibliography_localization_issue_count": len(bibliography_localization_issues),
        "unquoted_quote_reuse_count": len(unquoted_quote_reuse_matches),
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
        page_count = extract_pdf_page_count(pdf_path)
        report = build_pdf_audit_report(
            language=language,
            pdf_path=pdf_path,
            extracted_text=extract_pdf_text(pdf_path),
            page_count=page_count,
            min_page_count=config.pdf.get(f"{language}_page_count_min"),
            max_page_count=config.pdf.get(f"{language}_page_count_max"),
        )
        write_pdf_audit_report(pdf_audit_report_path(config, language), report)
        reports[language] = report
    return reports


def pdf_audit_reports_are_renderable(reports: dict[str, dict[str, object]]) -> bool:
    return all(report.get("status") == "passed" for report in reports.values())
