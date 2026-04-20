"""
Editorial refinement for the verified English draft.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from agent_gatsby.citation_registry import (
    build_citation_registry,
    render_citation_text_document,
    render_final_report,
    write_citation_text_document,
)
from agent_gatsby.config import AppConfig
from agent_gatsby.index_text import load_passage_index
from agent_gatsby.llm_client import LLMResponseValidationError, invoke_text_completion
from agent_gatsby.plan_outline import load_evidence_records
from agent_gatsby.verify_citations import (
    extract_citation_markers,
    extract_quoted_strings,
    load_english_draft,
    verify_english_draft,
)

LOGGER = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)
METAPHOR_TEXT_RE = re.compile(r"^Metaphor text:$", re.MULTILINE)
PARAGRAPH_SPLIT_RE = re.compile(r"(\n\s*\n)")
PROTECTED_QUOTE_TOKEN_RE = re.compile(r"AGQPROTECT\d{4}TOKEN")
PROTECTED_CITATION_TOKEN_RE = re.compile(r"AGCPROTECT\d{4}TOKEN")
CANONICAL_CITATION_RE = re.compile(r"\[(\d+)\.(\d+)\]")
DISPLAY_CITATION_RE = re.compile(r"\[#(\d+),\s*Chapter\s+(\d+),\s*Paragraph\s+(\d+)\]")
DOUBLE_QUOTE_RE = re.compile(r"[\"“](.+?)[\"”]", re.DOTALL)
SINGLE_QUOTE_RE = re.compile(r"(?<!\w)['‘]([^'\n]{2,}?)['’](?!\w)")


def load_critic_prompt(config: AppConfig) -> str:
    return config.resolve_prompt_path("critic_prompt_path").read_text(encoding="utf-8")


def load_style_simplifier_prompt(config: AppConfig) -> str | None:
    prompt_path = str(config.prompts.get("style_simplifier_prompt_path", "")).strip()
    if not prompt_path:
        return None
    return config.resolve_repo_path(prompt_path).read_text(encoding="utf-8")


def extract_heading_inventory(text: str) -> list[str]:
    return [match.group(0).strip() for match in HEADING_RE.finditer(text)]


def build_editorial_response_validator(original_text: str):
    original_citations = Counter(extract_citation_markers(original_text))
    original_quotes = Counter(extract_quoted_strings(original_text))
    original_headings = extract_heading_inventory(original_text)
    original_metaphor_block_count = len(METAPHOR_TEXT_RE.findall(original_text))

    def validator(response_text: str) -> None:
        revised_text = response_text.strip()
        if not revised_text:
            raise ValueError("Editorial revision is empty")

        revised_citations = Counter(extract_citation_markers(revised_text))
        if revised_citations != original_citations:
            raise ValueError("Editorial revision changed the citation marker inventory")

        revised_quotes = Counter(extract_quoted_strings(revised_text))
        if revised_quotes != original_quotes:
            raise ValueError("Editorial revision changed the direct-quote inventory")

        revised_headings = extract_heading_inventory(revised_text)
        if revised_headings != original_headings:
            raise ValueError("Editorial revision changed the markdown heading structure")

        revised_metaphor_block_count = len(METAPHOR_TEXT_RE.findall(revised_text))
        if revised_metaphor_block_count != original_metaphor_block_count:
            raise ValueError("Editorial revision changed the metaphor-text block inventory")

    return validator


def build_editorial_user_prompt(draft_text: str) -> str:
    instructions = [
        "Revise the verified markdown draft below for clarity, cohesion, and stronger analytical flow.",
        "Preserve every markdown heading line exactly as written.",
        "You may rewrite the one-sentence thematic lead-in before each `Metaphor text:` block so it reads naturally and grammatically.",
        "Preserve each `Metaphor text:` block exactly where it appears.",
        "Tighten bloated explanation when the draft repeats the same analytical point.",
        "Prefer direct academic prose and a clear claim-evidence-analysis rhythm.",
        "Preserve every direct quotation exactly as written.",
        "Preserve every citation marker exactly as written.",
        "Do not add new evidence, quotations, headings, or citations.",
        "Fix obvious prompt-leak phrasing in section lead-ins, such as leftover instruction words like 'Examine how' or 'Conclude the argument by'.",
        "If you cannot make safe improvements, return the original markdown unchanged.",
        "Never return an empty response.",
        "Return the full revised markdown document only.",
    ]
    return "\n".join(instructions) + "\n\nVerified draft:\n\n" + draft_text


def is_style_rewrite_eligible_block(block_text: str) -> bool:
    stripped = block_text.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return False
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return False
    if "Metaphor text:" in lines:
        return False
    if any(line.lower().startswith("citation note:") for line in lines):
        return False
    if any(line.startswith(">") for line in lines):
        return False
    return True


def protect_pattern(
    text: str,
    pattern: re.Pattern[str],
    *,
    token_prefix: str,
    start_index: int,
) -> tuple[str, dict[str, str], int]:
    token_counter = start_index
    token_lookup: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        nonlocal token_counter
        token_counter += 1
        token = f"{token_prefix}{token_counter:04d}TOKEN"
        token_lookup[token] = match.group(0)
        return token

    return pattern.sub(replace, text), token_lookup, token_counter


def protect_style_tokens(block_text: str) -> tuple[str, dict[str, str]]:
    protected_text, quote_tokens, _ = protect_pattern(
        block_text,
        DOUBLE_QUOTE_RE,
        token_prefix="AGQPROTECT",
        start_index=0,
    )
    protected_text, single_quote_tokens, _ = protect_pattern(
        protected_text,
        SINGLE_QUOTE_RE,
        token_prefix="AGQPROTECT",
        start_index=len(quote_tokens),
    )
    protected_text, canonical_citation_tokens, _ = protect_pattern(
        protected_text,
        CANONICAL_CITATION_RE,
        token_prefix="AGCPROTECT",
        start_index=0,
    )
    protected_text, display_citation_tokens, _ = protect_pattern(
        protected_text,
        DISPLAY_CITATION_RE,
        token_prefix="AGCPROTECT",
        start_index=len(canonical_citation_tokens),
    )
    token_lookup = {
        **quote_tokens,
        **single_quote_tokens,
        **canonical_citation_tokens,
        **display_citation_tokens,
    }
    return protected_text, token_lookup


def restore_style_tokens(block_text: str, token_lookup: dict[str, str]) -> str:
    restored = block_text
    for token, original in token_lookup.items():
        restored = restored.replace(token, original)
    return restored


def build_style_simplifier_user_prompt(block_text: str) -> str:
    instructions = [
        "Rewrite the prose paragraph below in plainspoken modern prose.",
        "Write for a high-agency reader who wants fast signal and no fluff.",
        "Use short sentences, simple structure, and direct topic sentences.",
        "Move in a clear claim-evidence-analysis rhythm when the paragraph contains evidence.",
        "Prefer small, familiar words when they convey the point accurately.",
        "Cut throat-clearing transitions, repeated abstraction, and ornamental phrasing.",
        "Make the logic explicit without sounding stiff.",
        "Preserve every AGQPROTECT token exactly as written.",
        "Preserve every AGCPROTECT token exactly as written.",
        "Do not add or remove any protected tokens.",
        "Return one rewritten paragraph only.",
        "If you cannot improve the paragraph safely, return it unchanged.",
    ]
    return "\n".join(instructions) + "\n\nParagraph:\n\n" + block_text


def build_style_simplifier_response_validator(original_text: str, *, minimum_word_ratio: float):
    original_quote_tokens = Counter(PROTECTED_QUOTE_TOKEN_RE.findall(original_text))
    original_citation_tokens = Counter(PROTECTED_CITATION_TOKEN_RE.findall(original_text))
    original_quotes = Counter(extract_quoted_strings(original_text))
    original_citations = Counter(extract_citation_markers(original_text))
    original_word_count = len(original_text.split())

    def validator(response_text: str) -> None:
        revised_text = response_text.strip()
        if not revised_text:
            raise ValueError("Style simplifier returned empty content")

        revised_quote_tokens = Counter(PROTECTED_QUOTE_TOKEN_RE.findall(revised_text))
        if revised_quote_tokens != original_quote_tokens:
            raise ValueError("Style simplifier changed the protected quote token inventory")

        revised_citation_tokens = Counter(PROTECTED_CITATION_TOKEN_RE.findall(revised_text))
        if revised_citation_tokens != original_citation_tokens:
            raise ValueError("Style simplifier changed the protected citation token inventory")

        revised_quotes = Counter(extract_quoted_strings(revised_text))
        if revised_quotes != original_quotes:
            raise ValueError("Style simplifier introduced or changed direct-quote content")

        revised_citations = Counter(extract_citation_markers(revised_text))
        if revised_citations != original_citations:
            raise ValueError("Style simplifier introduced or changed citation markers")

        if "[" in revised_text or "]" in revised_text:
            raise ValueError("Style simplifier introduced bracketed content outside protected tokens")

        if original_word_count > 0 and minimum_word_ratio > 0:
            revised_word_count = len(revised_text.split())
            if revised_word_count < round(original_word_count * minimum_word_ratio):
                raise ValueError("Style simplifier over-compressed the paragraph")

    return validator


def simplify_style_block(
    config: AppConfig,
    *,
    block_text: str,
    system_prompt: str,
) -> str:
    protected_text, token_lookup = protect_style_tokens(block_text.strip())
    minimum_word_ratio = float(config.editorial.get("style_simplifier_min_word_ratio", 0.88))
    transport_override = (
        str(config.editorial.get("style_simplifier_transport", "")).strip()
        or str(config.editorial.get("llm_transport", "")).strip()
        or str(config.drafting.get("llm_transport", "")).strip()
        or None
    )
    try:
        rewritten_text = invoke_text_completion(
            config,
            stage_name="style_simplify_english",
            system_prompt=system_prompt,
            user_prompt=build_style_simplifier_user_prompt(protected_text),
            output_path=str(config.final_draft_output_path),
            response_validator=build_style_simplifier_response_validator(
                protected_text,
                minimum_word_ratio=minimum_word_ratio,
            ),
            transport_override=transport_override,
        ).strip()
    except LLMResponseValidationError as exc:
        LOGGER.warning(
            "Style simplifier failed validation for one prose block and is falling back unchanged: %s",
            exc,
        )
        return block_text.strip()
    return restore_style_tokens(rewritten_text, token_lookup).strip()


def apply_style_simplifier(config: AppConfig, draft_text: str) -> str:
    if not bool(config.editorial.get("style_simplifier_enabled", False)):
        return draft_text

    system_prompt = load_style_simplifier_prompt(config)
    if system_prompt is None:
        LOGGER.warning("Style simplifier is enabled but no prompt path is configured; skipping rewrite pass")
        return draft_text

    minimum_words = int(config.editorial.get("style_simplifier_min_words", 8))
    rewritten_parts: list[str] = []
    for index, part in enumerate(PARAGRAPH_SPLIT_RE.split(draft_text)):
        if index % 2 == 1:
            rewritten_parts.append(part)
            continue
        if not is_style_rewrite_eligible_block(part) or len(part.split()) < minimum_words:
            rewritten_parts.append(part)
            continue
        rewritten_parts.append(
            simplify_style_block(
                config,
                block_text=part,
                system_prompt=system_prompt,
            )
        )
    return "".join(rewritten_parts).strip()


def write_final_english_draft(config: AppConfig, draft_text: str) -> None:
    output_path = config.final_draft_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(draft_text.strip() + "\n", encoding="utf-8")
    LOGGER.info("Wrote final English draft to %s", output_path)


def critique_and_edit(
    config: AppConfig,
    *,
    draft_text: str | None = None,
) -> str:
    loaded_draft = draft_text or load_english_draft(config)
    loaded_index = load_passage_index(config)
    transport_override = (
        str(config.editorial.get("llm_transport", "")).strip()
        or str(config.drafting.get("llm_transport", "")).strip()
        or None
    )
    try:
        revised_text = invoke_text_completion(
            config,
            stage_name="critique_english",
            system_prompt=load_critic_prompt(config),
            user_prompt=build_editorial_user_prompt(loaded_draft),
            output_path=str(config.final_draft_output_path),
            response_validator=build_editorial_response_validator(loaded_draft),
            transport_override=transport_override,
        ).strip()
    except LLMResponseValidationError as exc:
        LOGGER.warning(
            "Critique stage failed validation and is falling back to the verified draft unchanged: %s",
            exc,
        )
        revised_text = loaded_draft.strip()

    revised_text = apply_style_simplifier(config, revised_text)
    verify_english_draft(
        config,
        draft_text=revised_text,
        evidence_records=load_evidence_records(config),
        passage_index=loaded_index,
    )
    citation_registry = build_citation_registry(
        revised_text,
        loaded_index,
        display_format=str(config.drafting.get("display_citation_format", "[{citation_number}]")),
    )
    final_text = render_final_report(
        revised_text,
        citation_registry,
        title_override=str(config.outline.get("fixed_title", "")).strip() or None,
        appendix_heading=str(config.drafting.get("citation_appendix_heading", "Citations")),
    )
    citation_text = render_citation_text_document(
        citation_registry,
        title=str(config.drafting.get("citation_text_title", "Citation Text")),
    )
    write_final_english_draft(config, final_text)
    write_citation_text_document(config, citation_text)
    LOGGER.info("Wrote citation text document to %s", config.citation_text_output_path)
    return final_text
