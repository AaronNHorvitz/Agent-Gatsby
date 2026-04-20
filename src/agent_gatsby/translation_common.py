"""
Shared translation helpers for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re

from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.llm_client import LLMResponseValidationError, invoke_text_completion

LOGGER = logging.getLogger(__name__)

BLOCK_SPLIT_RE = re.compile(r"\n\s*\n")
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+.+$")
HEADING_LINE_RE = re.compile(r"^(#{1,6}\s+)(.*)$")
BLOCKQUOTE_LINE_RE = re.compile(r"^(\s*>\s?)(.*)$")
NUMBERED_LIST_LINE_RE = re.compile(r"^\d+\.\s+")
NUMBERED_CITATION_ENTRY_RE = re.compile(r"(?m)^\d+\.\s+")
VISIBLE_CITATION_RE = re.compile(r"\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\]")
TRANSLATION_CITATION_PLACEHOLDER_RE = re.compile(r"AGCITTOKEN(\d{4})XYZ")
STRAIGHT_QUOTE_SPAN_RE = re.compile(r'"[^"\n]+?"')
CURLY_QUOTE_SPAN_RE = re.compile(r"“[^”\n]+?”")
LOW_SINGLE_QUOTE_SPAN_RE = re.compile(r"‘[^’\n]+?’")
CJK_CORNER_QUOTE_SPAN_RE = re.compile(r"「[^」\n]+?」")
CJK_WHITE_CORNER_QUOTE_SPAN_RE = re.compile(r"『[^』\n]+?』")
CITATIONS_SECTION_RE = re.compile(r"(?m)^## Citations\s*$")
TRANSLATED_CITATIONS_SECTION_RE = re.compile(r"(?m)^##\s+(?:Citations|Citas|引文)\s*$")
ENGLISH_MULTIWORD_RE = re.compile(r"[A-Za-z][A-Za-z'’.-]*(?:\s+[a-z][A-Za-z'’.-]*){2,}")
CITATION_GLUE_RE = re.compile(r"(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])(?=[A-Za-zÁ-ÿ一-龯])")
MANDARIN_NORMALIZATION_MAP = {
    "菲茨平": "菲茨杰拉德",
    "菲茨格拉德": "菲茨杰拉德",
    "《了了不起的盖茨比》": "《了不起的盖茨比》",
    "T·J·艾克堡医生": "T. J. 艾克尔堡医生",
    "T·J·艾克堡": "T. J. 艾克尔堡",
    "盖失比": "盖茨比",
    "盖茨模": "盖茨比",
}
ENGLISH_MASTER_REGRESSION_FIXES = {
    "Valley of West": "Valley of Ashes",
    "punctiliously manner": "punctilious manner",
}
DEFAULT_REQUIRED_ENGLISH_MASTER_TERMS: tuple[str, ...] = ()
DEFAULT_FORBIDDEN_ENGLISH_MASTER_PHRASES = ("Valley of West", "punctiliously manner")
SPANISH_INTERNAL_TOKEN_RE = re.compile(r"\bAGCIT\w*(?:\s+[\u0400-\u04FF]+)?")
SPANISH_ESCAPE_SEQUENCE_RE = re.compile(r"\$\\\\\w+\b|\\[A-Za-z]+\b")
MANDARIN_ELLIPSIS_BEFORE_CITATION_RE = re.compile(
    r"[.…]{2,}\s*(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])"
)


def paragraph_blocks(text: str) -> list[str]:
    return [block.strip() for block in BLOCK_SPLIT_RE.split(text) if block.strip()]


def split_markdown_into_chunks(text: str, *, max_chars: int) -> list[str]:
    if max_chars <= 0:
        return [text.strip()]

    blocks = paragraph_blocks(text)
    if not blocks:
        return [text.strip()]

    chunks: list[str] = []
    current_blocks: list[str] = []
    current_chars = 0

    for block in blocks:
        block_length = len(block) + (2 if current_blocks else 0)
        if current_blocks and current_chars + block_length > max_chars:
            chunks.append("\n\n".join(current_blocks).strip())
            current_blocks = []
            current_chars = 0

        if not current_blocks and len(block) > max_chars:
            chunks.append(block.strip())
            continue

        current_blocks.append(block)
        current_chars += block_length

    if current_blocks:
        chunks.append("\n\n".join(current_blocks).strip())

    return chunks


def extract_heading_levels(text: str) -> list[int]:
    return [len(match.group(1)) for match in HEADING_RE.finditer(text)]


def extract_visible_citation_markers(text: str) -> list[str]:
    return [match.group(0) for match in VISIBLE_CITATION_RE.finditer(text)]


def mask_visible_citation_markers(text: str) -> tuple[str, list[str]]:
    original_markers: list[str] = []

    def replace(match: re.Match[str]) -> str:
        original_markers.append(match.group(0))
        return f"AGCITTOKEN{len(original_markers):04d}XYZ"

    return VISIBLE_CITATION_RE.sub(replace, text), original_markers


def extract_translation_placeholders(text: str) -> list[str]:
    return [match.group(0) for match in TRANSLATION_CITATION_PLACEHOLDER_RE.finditer(text)]


def restore_visible_citation_markers(text: str, original_markers: list[str]) -> str:
    expected_placeholders = [f"AGCITTOKEN{index:04d}XYZ" for index in range(1, len(original_markers) + 1)]
    observed_placeholders = extract_translation_placeholders(text)
    if observed_placeholders != expected_placeholders:
        raise ValueError("Translated chunk changed the citation placeholder inventory")

    restored_text = text
    for index, marker in enumerate(original_markers, start=1):
        restored_text = restored_text.replace(f"AGCITTOKEN{index:04d}XYZ", marker)
    return restored_text


def count_quote_spans(text: str) -> int:
    patterns = (
        STRAIGHT_QUOTE_SPAN_RE,
        CURLY_QUOTE_SPAN_RE,
        LOW_SINGLE_QUOTE_SPAN_RE,
        CJK_CORNER_QUOTE_SPAN_RE,
        CJK_WHITE_CORNER_QUOTE_SPAN_RE,
    )
    return sum(len(pattern.findall(text)) for pattern in patterns)


def extract_quote_spans(text: str) -> list[str]:
    patterns = (
        STRAIGHT_QUOTE_SPAN_RE,
        CURLY_QUOTE_SPAN_RE,
        LOW_SINGLE_QUOTE_SPAN_RE,
        CJK_CORNER_QUOTE_SPAN_RE,
        CJK_WHITE_CORNER_QUOTE_SPAN_RE,
    )
    spans: list[str] = []
    for pattern in patterns:
        spans.extend(match.group(0) for match in pattern.finditer(text))
    return spans


def count_protected_quote_spans(text: str) -> int:
    total = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">") or NUMBERED_LIST_LINE_RE.match(stripped):
            total += count_quote_spans(line)
    return total


def split_body_and_citations(text: str) -> tuple[str, str]:
    match = CITATIONS_SECTION_RE.search(text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.start() :].strip()


def split_translated_output_and_citations(text: str) -> tuple[str, str]:
    match = TRANSLATED_CITATIONS_SECTION_RE.search(text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), text[match.start() :].strip()


def count_numbered_citation_entries(text: str) -> int:
    return len(NUMBERED_CITATION_ENTRY_RE.findall(text))


def render_translated_citations_section(citations_text: str, *, language_name: str) -> str:
    if not citations_text.strip():
        return ""

    heading = "## Citations"
    if language_name == "Spanish":
        heading = "## Citas"
    elif language_name == "Simplified Chinese":
        heading = "## 引文"

    rendered_lines = [heading]
    for line in citations_text.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        rendered_lines.append(stripped)
    return "\n".join(rendered_lines).strip()


def validate_citations_section_parity(english_master: str, translated_text: str) -> None:
    _, english_citations_section = split_body_and_citations(english_master)
    _, translated_citations_section = split_translated_output_and_citations(translated_text)

    english_entries = count_numbered_citation_entries(english_citations_section)
    translated_entries = count_numbered_citation_entries(translated_citations_section)

    if bool(english_citations_section.strip()) != bool(translated_citations_section.strip()):
        raise ValueError("Translated output changed citations section presence")
    if translated_citations_section.strip() and translated_entries == 0:
        raise ValueError("Translated output kept the citations heading but dropped the citation entries")
    if english_entries != translated_entries:
        raise ValueError("Translated output changed the citation entry count")


def english_master_regression_report_path(config: AppConfig):
    return config.resolve_repo_path(
        str(
            config.verification.get(
                "english_master_regression_output_path",
                "artifacts/qa/english_master_regression_report.json",
            )
        )
    )


def normalize_english_master_regressions(text: str) -> tuple[str, list[dict[str, str]]]:
    normalized = text
    applied_fixes: list[dict[str, str]] = []
    for source, target in ENGLISH_MASTER_REGRESSION_FIXES.items():
        if source not in normalized:
            continue
        normalized = normalized.replace(source, target)
        applied_fixes.append({"from": source, "to": target})
    return normalized, applied_fixes


def build_english_master_regression_report(config: AppConfig, text: str, *, applied_fixes: list[dict[str, str]] | None = None):
    required_terms = tuple(
        str(term)
        for term in config.verification.get("english_master_required_terms", DEFAULT_REQUIRED_ENGLISH_MASTER_TERMS)
        if str(term).strip()
    )
    forbidden_phrases = tuple(
        str(phrase)
        for phrase in config.verification.get(
            "english_master_forbidden_phrases",
            DEFAULT_FORBIDDEN_ENGLISH_MASTER_PHRASES,
        )
        if str(phrase).strip()
    )
    missing_required_terms = [term for term in required_terms if term not in text]
    forbidden_phrase_hits = [phrase for phrase in forbidden_phrases if phrase in text]
    major_issues: list[str] = []
    if missing_required_terms:
        major_issues.append("English master is missing required terminology.")
    if forbidden_phrase_hits:
        major_issues.append("English master still contains forbidden regression phrases.")
    return {
        "stage": "freeze_english",
        "generated_at": utc_now_iso(),
        "status": "passed" if not major_issues else "failed",
        "required_terms": list(required_terms),
        "missing_required_terms": missing_required_terms,
        "forbidden_phrases": list(forbidden_phrases),
        "forbidden_phrase_hits": forbidden_phrase_hits,
        "applied_fixes": applied_fixes or [],
        "major_issues": major_issues,
    }


def write_english_master_regression_report(config: AppConfig, report: dict[str, object]) -> None:
    output_path = english_master_regression_report_path(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOGGER.info("Wrote English master regression report to %s", output_path)


def validate_english_master_regressions(config: AppConfig, text: str) -> str:
    normalized_text, applied_fixes = normalize_english_master_regressions(text)
    report = build_english_master_regression_report(config, normalized_text, applied_fixes=applied_fixes)
    write_english_master_regression_report(config, report)
    if report["major_issues"]:
        raise ValueError("English master failed terminology/regression validation")
    return normalized_text


def freeze_english_master(config: AppConfig) -> str:
    source_path = config.final_draft_output_path
    if not source_path.exists():
        raise FileNotFoundError(f"Final English report not found: {source_path}")

    raw_text = source_path.read_text(encoding="utf-8").strip() + "\n"
    master_text = validate_english_master_regressions(config, raw_text).strip() + "\n"
    if master_text != raw_text:
        source_path.write_text(master_text, encoding="utf-8")
        LOGGER.info("Applied deterministic English regression fixes to %s", source_path)
    output_path = config.english_master_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(master_text, encoding="utf-8")
    LOGGER.info("Froze English master to %s", output_path)
    return master_text


def load_english_master(config: AppConfig, *, freeze_if_missing: bool = True) -> str:
    output_path = config.english_master_output_path
    if output_path.exists():
        return output_path.read_text(encoding="utf-8")
    if freeze_if_missing:
        return freeze_english_master(config)
    raise FileNotFoundError(f"Frozen English master not found: {output_path}")


def load_translation_prompt(config: AppConfig, prompt_key: str) -> str:
    return config.resolve_prompt_path(prompt_key).read_text(encoding="utf-8")


def build_translation_user_prompt(chunk_text: str, *, chunk_index: int, total_chunks: int, language_name: str) -> str:
    instructions = [
        f"Chunk {chunk_index} of {total_chunks}.",
        f"Translate this markdown chunk into {language_name}.",
        "Preserve markdown heading markers exactly.",
        "Preserve immutable machine tokens like AGCITTOKEN0001XYZ exactly and do not translate, retype, split, or alter them.",
        "Preserve quotation boundaries.",
        "Return translated markdown only.",
    ]
    return "\n".join(instructions) + "\n\nEnglish markdown chunk:\n\n" + chunk_text


def build_fragment_user_prompt(fragment_text: str, *, language_name: str) -> str:
    instructions = [
        f"Translate this markdown fragment into {language_name}.",
        "Do not add commentary or extra lines.",
        "Preserve any inline markdown emphasis markers like * and _ when they appear in the fragment.",
        "Return the translated fragment only.",
    ]
    return "\n".join(instructions) + "\n\nEnglish markdown fragment:\n\n" + fragment_text


def build_translation_cleanup_user_prompt(chunk_text: str, *, chunk_index: int, total_chunks: int, language_name: str) -> str:
    instructions = [
        f"Chunk {chunk_index} of {total_chunks}.",
        f"Revise this existing {language_name} markdown chunk into polished academic {language_name}.",
        "The text is already translated, but it may contain leftover English, literal phrasing, inconsistent proper nouns, or awkward citation punctuation.",
        "Preserve markdown heading markers exactly.",
        "Preserve immutable machine tokens like AGCITTOKEN0001XYZ exactly and do not translate, retype, split, or alter them.",
        "Preserve quotation boundaries.",
        "Keep all direct quotations consistently translated into the target language unless the content is only a proper noun.",
        "Return revised markdown only.",
    ]
    return "\n".join(instructions) + "\n\nExisting translated markdown chunk:\n\n" + chunk_text


def build_cleanup_fragment_user_prompt(fragment_text: str, *, language_name: str) -> str:
    instructions = [
        f"Revise this existing {language_name} markdown fragment into polished academic {language_name}.",
        "Do not add commentary or extra lines.",
        "Preserve any inline markdown emphasis markers like * and _ when they appear in the fragment.",
        "Keep any direct quotations in the target language.",
        "Return the revised fragment only.",
    ]
    return "\n".join(instructions) + "\n\nExisting translated markdown fragment:\n\n" + fragment_text


def validate_translation_chunk(source_chunk: str, translated_chunk: str) -> None:
    stripped = translated_chunk.strip()
    if not stripped:
        raise ValueError("Translated chunk is empty")

    if extract_heading_levels(stripped) != extract_heading_levels(source_chunk):
        raise ValueError("Translated chunk changed the markdown heading structure")

    if extract_visible_citation_markers(stripped) != extract_visible_citation_markers(source_chunk):
        raise ValueError("Translated chunk changed the citation marker inventory")


def validate_placeholder_chunk(source_chunk: str, translated_chunk: str) -> None:
    stripped = translated_chunk.strip()
    if not stripped:
        raise ValueError("Translated chunk is empty")

    if extract_heading_levels(stripped) != extract_heading_levels(source_chunk):
        raise ValueError("Translated chunk changed the markdown heading structure")

    if extract_translation_placeholders(stripped) != extract_translation_placeholders(source_chunk):
        raise ValueError("Translated chunk changed the citation placeholder inventory")


def validate_translated_fragment(translated_text: str) -> None:
    if not translated_text.strip():
        raise ValueError("Translated fragment is empty")

    if extract_visible_citation_markers(translated_text):
        raise ValueError("Translated fragment unexpectedly introduced citation markers")

    if extract_translation_placeholders(translated_text):
        raise ValueError("Translated fragment unexpectedly introduced citation placeholders")


def normalize_translated_body(text: str, *, language_name: str) -> str:
    normalized = CITATION_GLUE_RE.sub(r"\1 ", text)
    if language_name == "Spanish":
        normalized = SPANISH_INTERNAL_TOKEN_RE.sub("", normalized)
        normalized = SPANISH_ESCAPE_SEQUENCE_RE.sub(" ", normalized)
        normalized = normalized.replace("esporádíamos", "esporádicos")
    if language_name == "Simplified Chinese":
        normalized = MANDARIN_ELLIPSIS_BEFORE_CITATION_RE.sub(r" \1", normalized)
        for source, target in MANDARIN_NORMALIZATION_MAP.items():
            normalized = normalized.replace(source, target)
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized


def write_translation_output(output_path, text: str, *, language_name: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text.strip() + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s translation to %s", language_name, output_path)


def post_edit_translated_body(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    translated_body: str,
    transport_override: str | None,
) -> str:
    chunks = split_markdown_into_chunks(
        translated_body,
        max_chars=int(config.translation.get("max_chunk_chars", 5000)),
    )
    revised_chunks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        masked_chunk, original_markers = mask_visible_citation_markers(chunk)
        try:
            revised_chunk = invoke_text_completion(
                config,
                stage_name=f"{stage_name}_cleanup",
                system_prompt=system_prompt,
                user_prompt=build_translation_cleanup_user_prompt(
                    masked_chunk,
                    chunk_index=index,
                    total_chunks=len(chunks),
                    language_name=language_name,
                ),
                output_path=str(output_path),
                model_name=model_name,
                response_validator=lambda text, source_chunk=masked_chunk: validate_placeholder_chunk(source_chunk, text),
                transport_override=transport_override,
            ).strip()
            revised_chunks.append(restore_visible_citation_markers(revised_chunk, original_markers))
        except LLMResponseValidationError as exc:
            if "citation placeholder inventory" not in str(exc):
                raise
            LOGGER.warning(
                "Post-edit cleanup failed placeholder preservation for %s chunk %d/%d; falling back to fragment-safe cleanup",
                stage_name,
                index,
                len(chunks),
            )
            revised_chunks.append(
                cleanup_chunk_with_marker_stitching(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=model_name,
                    language_name=language_name,
                    chunk_text=chunk,
                    transport_override=transport_override,
                )
            )

    return normalize_translated_body("\n\n".join(revised_chunks).strip(), language_name=language_name)


def translate_fragment(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    fragment_text: str,
    transport_override: str | None,
) -> str:
    if not fragment_text.strip():
        return fragment_text

    leading = fragment_text[: len(fragment_text) - len(fragment_text.lstrip())]
    trailing = fragment_text[len(fragment_text.rstrip()) :]
    core = fragment_text.strip()
    if not core:
        return fragment_text

    translated_core = invoke_text_completion(
        config,
        stage_name=stage_name,
        system_prompt=system_prompt,
        user_prompt=build_fragment_user_prompt(core, language_name=language_name),
        output_path=str(output_path),
        model_name=model_name,
        response_validator=validate_translated_fragment,
        transport_override=transport_override,
    ).strip()
    return leading + translated_core + trailing


def cleanup_fragment(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    fragment_text: str,
    transport_override: str | None,
) -> str:
    if not fragment_text.strip():
        return fragment_text

    leading = fragment_text[: len(fragment_text) - len(fragment_text.lstrip())]
    trailing = fragment_text[len(fragment_text.rstrip()) :]
    core = fragment_text.strip()
    if not core:
        return fragment_text

    cleaned_core = invoke_text_completion(
        config,
        stage_name=f"{stage_name}_cleanup",
        system_prompt=system_prompt,
        user_prompt=build_cleanup_fragment_user_prompt(core, language_name=language_name),
        output_path=str(output_path),
        model_name=model_name,
        response_validator=validate_translated_fragment,
        transport_override=transport_override,
    ).strip()
    return leading + cleaned_core + trailing


def translate_text_preserving_citations(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    text: str,
    transport_override: str | None,
) -> str:
    if not text:
        return text

    parts = re.split(f"({VISIBLE_CITATION_RE.pattern})", text)
    translated_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if VISIBLE_CITATION_RE.fullmatch(part):
            translated_parts.append(part)
            continue
        translated_parts.append(
            translate_fragment(
                config,
                stage_name=stage_name,
                system_prompt=system_prompt,
                output_path=output_path,
                model_name=model_name,
                language_name=language_name,
                fragment_text=part,
                transport_override=transport_override,
            )
        )
    return "".join(translated_parts)


def cleanup_text_preserving_citations(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    text: str,
    transport_override: str | None,
) -> str:
    if not text:
        return text

    parts = re.split(f"({VISIBLE_CITATION_RE.pattern})", text)
    cleaned_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if VISIBLE_CITATION_RE.fullmatch(part):
            cleaned_parts.append(part)
            continue
        cleaned_parts.append(
            cleanup_fragment(
                config,
                stage_name=stage_name,
                system_prompt=system_prompt,
                output_path=output_path,
                model_name=model_name,
                language_name=language_name,
                fragment_text=part,
                transport_override=transport_override,
            )
        )
    return "".join(cleaned_parts)


def translate_chunk_with_marker_stitching(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    chunk_text: str,
    transport_override: str | None,
) -> str:
    translated_blocks: list[str] = []
    for block in paragraph_blocks(chunk_text):
        translated_lines: list[str] = []
        for line in block.splitlines():
            if not line.strip():
                translated_lines.append(line)
                continue

            prefix = ""
            body = line
            heading_match = HEADING_LINE_RE.match(line)
            if heading_match:
                prefix = heading_match.group(1)
                body = heading_match.group(2)
            else:
                blockquote_match = BLOCKQUOTE_LINE_RE.match(line)
                if blockquote_match:
                    prefix = blockquote_match.group(1)
                    body = blockquote_match.group(2)

            translated_lines.append(
                prefix
                + translate_text_preserving_citations(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=model_name,
                    language_name=language_name,
                    text=body,
                    transport_override=transport_override,
                )
            )
        translated_blocks.append("\n".join(translated_lines))
    return "\n\n".join(translated_blocks).strip()


def cleanup_chunk_with_marker_stitching(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    output_path,
    model_name: str,
    language_name: str,
    chunk_text: str,
    transport_override: str | None,
) -> str:
    cleaned_blocks: list[str] = []
    for block in paragraph_blocks(chunk_text):
        cleaned_lines: list[str] = []
        for line in block.splitlines():
            if not line.strip():
                cleaned_lines.append(line)
                continue

            prefix = ""
            body = line
            heading_match = HEADING_LINE_RE.match(line)
            if heading_match:
                prefix = heading_match.group(1)
                body = heading_match.group(2)
            else:
                blockquote_match = BLOCKQUOTE_LINE_RE.match(line)
                if blockquote_match:
                    prefix = blockquote_match.group(1)
                    body = blockquote_match.group(2)

            cleaned_lines.append(
                prefix
                + cleanup_text_preserving_citations(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=model_name,
                    language_name=language_name,
                    text=body,
                    transport_override=transport_override,
                )
            )
        cleaned_blocks.append("\n".join(cleaned_lines))
    return "\n\n".join(cleaned_blocks).strip()


def translate_document(
    config: AppConfig,
    *,
    stage_name: str,
    prompt_key: str,
    cleanup_prompt_key: str | None,
    model_key: str,
    output_path,
    language_name: str,
    source_text: str | None = None,
) -> str:
    master_text = source_text or load_english_master(config)
    body_text, citations_text = split_body_and_citations(master_text)
    max_chunk_chars = int(config.translation.get("max_chunk_chars", 5000))
    chunks = split_markdown_into_chunks(body_text, max_chars=max_chunk_chars)
    system_prompt = load_translation_prompt(config, prompt_key)
    cleanup_prompt = load_translation_prompt(config, cleanup_prompt_key) if cleanup_prompt_key else system_prompt
    transport_override = (
        str(config.translation.get("llm_transport", "")).strip()
        or str(config.drafting.get("llm_transport", "")).strip()
        or None
    )

    translated_chunks: list[str] = []
    target_model_name = config.model_name_for(model_key)
    for index, chunk in enumerate(chunks, start=1):
        masked_chunk, original_markers = mask_visible_citation_markers(chunk)
        try:
            translated_chunk = invoke_text_completion(
                config,
                stage_name=stage_name,
                system_prompt=system_prompt,
                user_prompt=build_translation_user_prompt(
                    masked_chunk,
                    chunk_index=index,
                    total_chunks=len(chunks),
                    language_name=language_name,
                ),
                output_path=str(output_path),
                model_name=target_model_name,
                response_validator=lambda text, source_chunk=masked_chunk: validate_placeholder_chunk(source_chunk, text),
                transport_override=transport_override,
            ).strip()
            translated_chunks.append(restore_visible_citation_markers(translated_chunk, original_markers))
        except LLMResponseValidationError as exc:
            if "citation placeholder inventory" not in str(exc):
                raise
            LOGGER.warning(
                "Chunk-level translation failed placeholder preservation for %s chunk %d/%d; falling back to citation-safe fragment stitching",
                stage_name,
                index,
                len(chunks),
            )
            translated_chunks.append(
                translate_chunk_with_marker_stitching(
                    config,
                    stage_name=stage_name,
                    system_prompt=system_prompt,
                    output_path=output_path,
                    model_name=target_model_name,
                    language_name=language_name,
                    chunk_text=chunk,
                    transport_override=transport_override,
                )
            )

    translated_body = "\n\n".join(translated_chunks).strip()
    if bool(config.translation.get("post_edit_body", True)):
        translated_body = post_edit_translated_body(
            config,
            stage_name=stage_name,
            system_prompt=cleanup_prompt,
            output_path=output_path,
            model_name=target_model_name,
            language_name=language_name,
            translated_body=translated_body,
            transport_override=transport_override,
        )
    else:
        translated_body = normalize_translated_body(translated_body, language_name=language_name)

    translated_citations = render_translated_citations_section(citations_text, language_name=language_name)
    translated_text = translated_body
    if translated_citations:
        translated_text = translated_text + "\n\n" + translated_citations
    translated_text = translated_text.strip() + "\n"
    validate_translation_chunk(master_text, translated_text)
    validate_citations_section_parity(master_text, translated_text)
    write_translation_output(output_path, translated_text, language_name=language_name)
    return translated_text
