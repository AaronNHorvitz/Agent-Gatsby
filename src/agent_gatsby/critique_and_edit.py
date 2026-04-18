"""
Editorial refinement for the verified English draft.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from agent_gatsby.citation_registry import build_citation_registry, render_report_with_citation_appendix
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


def load_critic_prompt(config: AppConfig) -> str:
    return config.resolve_prompt_path("critic_prompt_path").read_text(encoding="utf-8")


def extract_heading_inventory(text: str) -> list[str]:
    return [match.group(0).strip() for match in HEADING_RE.finditer(text)]


def build_editorial_response_validator(original_text: str):
    original_citations = Counter(extract_citation_markers(original_text))
    original_quotes = Counter(extract_quoted_strings(original_text))
    original_headings = extract_heading_inventory(original_text)

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

    return validator


def build_editorial_user_prompt(draft_text: str) -> str:
    instructions = [
        "Revise the verified markdown draft below for clarity, cohesion, and stronger analytical flow.",
        "Preserve every markdown heading line exactly as written.",
        "Preserve every direct quotation exactly as written.",
        "Preserve every citation marker exactly as written.",
        "Do not add new evidence, quotations, headings, or citations.",
        "If you cannot make safe improvements, return the original markdown unchanged.",
        "Never return an empty response.",
        "Return the full revised markdown document only.",
    ]
    return "\n".join(instructions) + "\n\nVerified draft:\n\n" + draft_text


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
    try:
        revised_text = invoke_text_completion(
            config,
            stage_name="critique_english",
            system_prompt=load_critic_prompt(config),
            user_prompt=build_editorial_user_prompt(loaded_draft),
            output_path=str(config.final_draft_output_path),
            response_validator=build_editorial_response_validator(loaded_draft),
        ).strip()
    except LLMResponseValidationError as exc:
        LOGGER.warning(
            "Critique stage failed validation and is falling back to the verified draft unchanged: %s",
            exc,
        )
        revised_text = loaded_draft.strip()

    verify_english_draft(
        config,
        draft_text=revised_text,
        evidence_records=load_evidence_records(config),
        passage_index=loaded_index,
    )
    citation_registry = build_citation_registry(
        revised_text,
        loaded_index,
        display_format=str(config.drafting.get("display_citation_format", "[#{citation_number}, Chapter {chapter}, Paragraph {paragraph}]")),
    )
    final_text = render_report_with_citation_appendix(
        revised_text,
        citation_registry,
        appendix_heading=str(config.drafting.get("citation_appendix_heading", "Citations")),
    )
    write_final_english_draft(config, final_text)
    return final_text
