"""Post-render audits for the final PDF submission artifacts.

This module performs the last deterministic and model-assisted QA pass on the
rendered English, Spanish, and Mandarin PDFs. It extracts text from the final
artifacts, checks them for known regressions and structural problems, optionally
runs a forensic LLM audit, and produces machine-readable reports that gate final
artifact promotion.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

from agent_gatsby.bilingual_qa import (
    find_assistant_prompt_leaks,
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
from agent_gatsby.llm_client import invoke_text_completion
from agent_gatsby.translation_common import find_unquoted_english_quote_reuse

LOGGER = logging.getLogger(__name__)
JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
JSON_OBJECT_RE = re.compile(r"{.*}", re.DOTALL)

KNOWN_BAD_ENGLISH_TOKENS = (
    "Valley of West",
    "punctiliously manner",
    "theragged edge",
    "He does not use metaphor merely",
    "grotesleque",
    "Nick Carrawical",
    "it actively populating the landscape",
    "literal and figurative heat",
    "outward edge of the universe [2]",
    "Es World’s Fair",
    r"The exhilarating ripple of her voice was a\ wild tonic in the rain",
    "The confrontation between Gatsby and Tom provides the moment where this artificiality physically breaks.",
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
    "fairy’s wing [20]",
    "foul dust [1]",
    "place of inexplicable amount of dust [26]",
    '*"*“Jay Gatsby”* had broken up like glass against Tom’s hard malice"* [27]',
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
    "episodio deshilachado del universo",
    "el gran y húmedo corral de Long Island Sound",
    "Please provide the Spanish markdown fragment you would like me to revise.",
    "professional academic copyediting standards",
    "emocionante murmullo de su voz",
    "pierta",
    "ilustcionar",
    "metáfor yas",
    "apogeencia",
    "servicio de catering",
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
    "菲茨杰是否存在",
    "长显长岛海峡",
    "餐饮承包园",
    "构想中的杰伊·盖茨比",
    "厚实感",
    "实体感感",
    "叙骗手段",
    "盖盖茨比",
    "鸿望",
    "世界及其女主人",
    "男人和姑娘们",
    "人群的旋涡与涡流",
    "从餐饮师的篮子里变出来的",
    "已充实成了一个男人的实体",
    "一打太阳",
    "世界博览会",
)
AUDIT_LANGUAGE_NAMES = ("english", "spanish", "mandarin")
FORENSIC_AUDIT_SEVERITIES = {"high", "medium", "low"}
DEFAULT_LLM_FORENSIC_BLOCKLIST_CATEGORIES = ("system_leak", "prompt_leak")
DEFAULT_LLM_FORENSIC_BLOCKLIST_PATTERNS = (
    "please provide the spanish markdown fragment",
    "professional academic copyediting standards described in your instructions",
)


def pdf_audit_report_path(config: AppConfig, language: str) -> Path:
    """Resolve the deterministic PDF audit report path for one language.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.
    language : str
        Language key being audited.

    Returns
    -------
    Path
        Output path for the language-specific PDF audit report.
    """

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
    """Return deterministic PDF audit report paths for all final languages.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    list of Path
        Report paths for English, Spanish, and Mandarin PDF audits.
    """

    return [pdf_audit_report_path(config, language) for language in AUDIT_LANGUAGE_NAMES]


def llm_forensic_audit_report_path(config: AppConfig, language: str) -> Path:
    """Resolve the advisory LLM forensic audit report path for one language.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.
    language : str
        Language key being audited.

    Returns
    -------
    Path
        Output path for the LLM forensic audit report.
    """

    default_name = f"{language}_llm_forensic_audit_report.json"
    return config.resolve_repo_path(
        str(
            config.verification.get(
                f"{language}_llm_forensic_audit_output_path",
                f"artifacts/qa/{default_name}",
            )
        )
    )


def llm_forensic_audit_report_paths(config: AppConfig) -> list[Path]:
    """Return LLM forensic audit report paths for all final languages.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    list of Path
        Report paths for English, Spanish, and Mandarin LLM forensic audits.
    """

    return [llm_forensic_audit_report_path(config, language) for language in AUDIT_LANGUAGE_NAMES]


def llm_forensic_audit_enabled(config: AppConfig) -> bool:
    """Check whether the advisory LLM forensic PDF audit is enabled.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    bool
        ``True`` when the LLM forensic audit should run.
    """

    return bool(config.verification.get("llm_forensic_audit_enabled", False))


def llm_forensic_blocklist_categories(config: AppConfig) -> set[str]:
    """Load blocklisted forensic defect categories from configuration.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    set of str
        Normalized category names that should upgrade LLM findings into hard
        failures.
    """

    configured = config.verification.get(
        "llm_forensic_blocklist_categories",
        list(DEFAULT_LLM_FORENSIC_BLOCKLIST_CATEGORIES),
    )
    if not isinstance(configured, list):
        return set(DEFAULT_LLM_FORENSIC_BLOCKLIST_CATEGORIES)
    return {str(category).strip().lower() for category in configured if str(category).strip()}


def llm_forensic_blocklist_patterns(config: AppConfig) -> list[str]:
    """Load blocklisted forensic text patterns from configuration.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    list of str
        Lowercased substrings that should upgrade LLM findings into hard
        failures.
    """

    configured = config.verification.get(
        "llm_forensic_blocklist_patterns",
        list(DEFAULT_LLM_FORENSIC_BLOCKLIST_PATTERNS),
    )
    if not isinstance(configured, list):
        return list(DEFAULT_LLM_FORENSIC_BLOCKLIST_PATTERNS)
    return [str(pattern).strip().lower() for pattern in configured if str(pattern).strip()]


def load_forensic_audit_prompt(config: AppConfig) -> str:
    """Load the system prompt used for LLM forensic PDF auditing.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    str
        Prompt text for the forensic audit critic.
    """

    return config.resolve_prompt_path("final_forensic_audit_prompt_path").read_text(encoding="utf-8")


def extract_json_payload(response_text: str) -> str:
    """Extract a JSON object from a possibly fenced model response.

    Parameters
    ----------
    response_text : str
        Raw model response text.

    Returns
    -------
    str
        JSON payload candidate suitable for ``json.loads``.
    """

    text = response_text.strip()
    if text.startswith("```"):
        text = JSON_FENCE_RE.sub("", text).strip()
    if text.startswith("{"):
        return text
    match = JSON_OBJECT_RE.search(text)
    if match:
        return match.group(0)
    return text


def parse_forensic_audit_response(response_text: str, *, language: str) -> dict[str, object]:
    """Parse and normalize an LLM forensic audit response.

    Parameters
    ----------
    response_text : str
        Raw response from the forensic audit model.
    language : str
        Expected document language for the report.

    Returns
    -------
    dict of str to object
        Normalized report payload containing defects and free-form notes.

    Raises
    ------
    ValueError
        If the response is not valid JSON or does not follow the expected
        forensic defect schema.
    """

    payload = json.loads(extract_json_payload(response_text))
    if not isinstance(payload, dict):
        raise ValueError("Expected forensic audit response to be a JSON object")

    defects = payload.get("defects", [])
    if not isinstance(defects, list):
        raise ValueError("Expected forensic audit response to contain a defects list")

    normalized_defects: list[dict[str, str]] = []
    for index, defect in enumerate(defects, start=1):
        if not isinstance(defect, dict):
            raise ValueError(f"Defect {index} is not a JSON object")

        defect_language = str(defect.get("language", language)).strip().lower()
        if defect_language != language:
            raise ValueError(f"Defect {index} reported language '{defect_language}' but expected '{language}'")

        original_text = str(defect.get("original_text", "")).strip()
        proposed_correction = str(defect.get("proposed_correction", "")).strip()
        severity = str(defect.get("severity", "")).strip().lower()
        if not original_text:
            raise ValueError(f"Defect {index} is missing original_text")
        if not proposed_correction:
            raise ValueError(f"Defect {index} is missing proposed_correction")
        if severity not in FORENSIC_AUDIT_SEVERITIES:
            raise ValueError(f"Defect {index} severity must be one of High, Medium, or Low")

        normalized_defects.append(
            {
                "language": language,
                "original_text": original_text,
                "proposed_correction": proposed_correction,
                "severity": severity.title(),
                "category": str(defect.get("category", "")).strip() or "unspecified",
            }
        )

    notes = str(payload.get("notes", "")).strip() or "No notes provided."
    return {"defects": normalized_defects, "notes": notes}


def validate_forensic_audit_response(response_text: str, *, language: str) -> None:
    """Validate that an LLM forensic response is parseable and well shaped.

    Parameters
    ----------
    response_text : str
        Raw response from the forensic audit model.
    language : str
        Expected document language for the report.

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If the response cannot be parsed into the expected schema.
    """

    parse_forensic_audit_response(response_text, language=language)


def find_blocking_forensic_defects(
    config: AppConfig,
    defects: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Filter forensic findings down to defects that should block promotion.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.
    defects : list of dict of str to str
        Parsed forensic defects from the LLM audit.

    Returns
    -------
    list of dict of str to str
        Subset of defects that match configured blocklist categories or text
        patterns.
    """

    blocked_categories = llm_forensic_blocklist_categories(config)
    blocked_patterns = llm_forensic_blocklist_patterns(config)
    blocking_defects: list[dict[str, str]] = []
    for defect in defects:
        category = str(defect.get("category", "")).strip().lower()
        original_text = str(defect.get("original_text", "")).strip().lower()
        proposed_correction = str(defect.get("proposed_correction", "")).strip().lower()
        if category in blocked_categories or any(
            pattern in original_text or pattern in proposed_correction for pattern in blocked_patterns
        ):
            blocking_defects.append(defect)
    return blocking_defects


def build_forensic_audit_user_prompt(
    *,
    language: str,
    pdf_path: Path,
    extracted_text: str,
    page_count: int | None,
) -> str:
    """Build the user prompt for the forensic PDF audit critic.

    Parameters
    ----------
    language : str
        Document language being audited.
    pdf_path : Path
        Path to the rendered PDF.
    extracted_text : str
        Text extracted from the rendered PDF.
    page_count : int or None
        Observed PDF page count when available.

    Returns
    -------
    str
        User prompt instructing the critic to audit the extracted PDF text.
    """

    page_count_text = "unknown" if page_count is None else str(page_count)
    return "\n".join(
        [
            f"Document language: {language}",
            f"Rendered PDF path: {pdf_path}",
            f"Rendered PDF page count: {page_count_text}",
            "",
            "Audit rules:",
            "- Audit only the visible text provided below.",
            "- Focus on system leaks, citation-adjacent corruption, hallucinated vocabulary, and last-mile source accuracy.",
            "- Treat localized bibliography labels as acceptable in the target language.",
            "- Do not flag page-count differences by themselves; page-range checks are handled elsewhere.",
            "- If no defects are found, return an empty defects array.",
            "",
            "Extracted PDF text:",
            extracted_text.strip(),
        ]
    )


def write_llm_forensic_audit_report(output_path: Path, report: dict[str, object]) -> None:
    """Persist an LLM forensic audit report to disk.

    Parameters
    ----------
    output_path : Path
        Destination JSON report path.
    report : dict of str to object
        Report payload to serialize.

    Returns
    -------
    None
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s LLM forensic audit report to %s", report["language"], output_path)


def run_llm_forensic_audit(
    config: AppConfig,
    *,
    language: str,
    pdf_path: Path,
    extracted_text: str,
    page_count: int | None,
) -> dict[str, object]:
    """Run the advisory LLM forensic audit for one rendered PDF.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.
    language : str
        Document language being audited.
    pdf_path : Path
        Path to the rendered PDF.
    extracted_text : str
        Text extracted from the PDF.
    page_count : int or None
        Observed page count when available.

    Returns
    -------
    dict of str to object
        Serialized audit report, including skipped and error cases.

    Notes
    -----
    This audit is advisory by default, but configured blocklist categories and
    patterns can upgrade selected findings into hard failures.
    """

    output_path = llm_forensic_audit_report_path(config, language)
    if not llm_forensic_audit_enabled(config):
        report = {
            "stage": "llm_forensic_pdf_audit",
            "language": language,
            "generated_at": utc_now_iso(),
            "pdf_path": str(pdf_path),
            "status": "skipped",
            "page_count": page_count,
            "defect_count": 0,
            "blocking_defect_count": 0,
            "defects": [],
            "blocking_defects": [],
            "notes": "LLM forensic audit disabled in config.",
        }
        write_llm_forensic_audit_report(output_path, report)
        return report

    prompt = load_forensic_audit_prompt(config)
    user_prompt = build_forensic_audit_user_prompt(
        language=language,
        pdf_path=pdf_path,
        extracted_text=extracted_text,
        page_count=page_count,
    )
    try:
        response_text = invoke_text_completion(
            config,
            stage_name=f"final_forensic_audit_{language}",
            system_prompt=prompt,
            user_prompt=user_prompt,
            output_path=str(output_path),
            model_name=str(config.models.get("final_critic", config.models.get("primary_reasoner", ""))),
            response_validator=lambda text: validate_forensic_audit_response(text, language=language),
            transport_override="ollama_native_chat",
        )
        parsed = parse_forensic_audit_response(response_text, language=language)
        blocking_defects = find_blocking_forensic_defects(config, parsed["defects"])
        report = {
            "stage": "llm_forensic_pdf_audit",
            "language": language,
            "generated_at": utc_now_iso(),
            "pdf_path": str(pdf_path),
            "status": "passed" if not parsed["defects"] else "blocked" if blocking_defects else "defects_found",
            "page_count": page_count,
            "defect_count": len(parsed["defects"]),
            "blocking_defect_count": len(blocking_defects),
            "defects": parsed["defects"],
            "blocking_defects": blocking_defects,
            "notes": parsed["notes"],
        }
    except Exception as exc:
        LOGGER.warning("LLM forensic audit failed for %s PDF: %s", language, exc)
        report = {
            "stage": "llm_forensic_pdf_audit",
            "language": language,
            "generated_at": utc_now_iso(),
            "pdf_path": str(pdf_path),
            "status": "error",
            "page_count": page_count,
            "defect_count": 0,
            "blocking_defect_count": 0,
            "defects": [],
            "blocking_defects": [],
            "notes": str(exc),
        }

    write_llm_forensic_audit_report(output_path, report)
    return report


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract visible text from a rendered PDF using ``pdftotext``.

    Parameters
    ----------
    pdf_path : Path
        PDF artifact to inspect.

    Returns
    -------
    str
        Extracted text content.

    Raises
    ------
    FileNotFoundError
        If ``pdftotext`` is unavailable.
    ValueError
        If text extraction fails.
    """

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
    """Extract a rendered PDF's page count using ``pdfinfo`` when available.

    Parameters
    ----------
    pdf_path : Path
        PDF artifact to inspect.

    Returns
    -------
    int or None
        Observed page count, or ``None`` when it cannot be determined.
    """

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
    """Build the deterministic audit report for one rendered PDF.

    Parameters
    ----------
    language : str
        Document language being audited.
    pdf_path : Path
        Path to the rendered PDF.
    extracted_text : str
        Text extracted from the PDF.
    page_count : int or None, optional
        Observed page count.
    min_page_count : int or None, optional
        Minimum acceptable page count.
    max_page_count : int or None, optional
        Maximum acceptable page count.

    Returns
    -------
    dict of str to object
        Machine-readable deterministic audit report.
    """

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
    prompt_leak_issues = find_assistant_prompt_leaks(extracted_text)

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
    if prompt_leak_issues:
        major_issues.append("Rendered PDF text leaked assistant or prompt-revision text into the document.")
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
        "prompt_leak_issue_count": len(prompt_leak_issues),
        "major_issues": major_issues,
    }


def write_pdf_audit_report(output_path: Path, report: dict[str, object]) -> None:
    """Persist a deterministic PDF audit report to disk.

    Parameters
    ----------
    output_path : Path
        Destination JSON report path.
    report : dict of str to object
        Report payload to serialize.

    Returns
    -------
    None
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s PDF audit report to %s", report["language"], output_path)


def merge_llm_forensic_audit_result(
    pdf_report: dict[str, object],
    llm_report: dict[str, object],
) -> dict[str, object]:
    """Merge deterministic and forensic PDF audit results.

    Parameters
    ----------
    pdf_report : dict of str to object
        Deterministic PDF audit report.
    llm_report : dict of str to object
        Advisory LLM forensic audit report.

    Returns
    -------
    dict of str to object
        Combined report with forensic status fields added.
    """

    merged = dict(pdf_report)
    merged["llm_forensic_status"] = llm_report.get("status", "unknown")
    merged["llm_forensic_defect_count"] = int(llm_report.get("defect_count", 0) or 0)
    merged["llm_forensic_blocking_defect_count"] = int(llm_report.get("blocking_defect_count", 0) or 0)
    if llm_report.get("status") == "blocked":
        major_issues = list(merged.get("major_issues", []))
        major_issues.append("LLM forensic audit detected blocklisted defects.")
        merged["major_issues"] = major_issues
        merged["status"] = "failed"
    return merged


def audit_rendered_pdfs(config: AppConfig) -> dict[str, dict[str, object]]:
    """Audit all rendered final PDFs and merge deterministic plus forensic results.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    dict of str to dict of str to object
        Per-language audit reports keyed by language name.
    """

    reports: dict[str, dict[str, object]] = {}
    pdf_paths = {
        "english": config.english_pdf_output_path,
        "spanish": config.spanish_pdf_output_path,
        "mandarin": config.mandarin_pdf_output_path,
    }
    extracted_texts: dict[str, str] = {}
    page_counts: dict[str, int | None] = {}
    for language, pdf_path in pdf_paths.items():
        page_count = extract_pdf_page_count(pdf_path)
        extracted_text = extract_pdf_text(pdf_path)
        report = build_pdf_audit_report(
            language=language,
            pdf_path=pdf_path,
            extracted_text=extracted_text,
            page_count=page_count,
            min_page_count=config.pdf.get(f"{language}_page_count_min"),
            max_page_count=config.pdf.get(f"{language}_page_count_max"),
        )
        write_pdf_audit_report(pdf_audit_report_path(config, language), report)
        reports[language] = report
        extracted_texts[language] = extracted_text
        page_counts[language] = page_count

    for language, pdf_path in pdf_paths.items():
        llm_report = run_llm_forensic_audit(
            config,
            language=language,
            pdf_path=pdf_path,
            extracted_text=extracted_texts[language],
            page_count=page_counts[language],
        )
        reports[language] = merge_llm_forensic_audit_result(reports[language], llm_report)
    return reports


def pdf_audit_reports_are_renderable(reports: dict[str, dict[str, object]]) -> bool:
    """Check whether every per-language PDF audit passed.

    Parameters
    ----------
    reports : dict of str to dict of str to object
        Per-language audit reports.

    Returns
    -------
    bool
        ``True`` when all reports have ``"passed"`` status.
    """

    return all(report.get("status") == "passed" for report in reports.values())
