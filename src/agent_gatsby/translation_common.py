"""
Shared translation helpers for Agent Gatsby.
"""

from __future__ import annotations

import logging
import re

from agent_gatsby.config import AppConfig
from agent_gatsby.llm_client import invoke_text_completion

LOGGER = logging.getLogger(__name__)

BLOCK_SPLIT_RE = re.compile(r"\n\s*\n")
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+.+$")
VISIBLE_CITATION_RE = re.compile(r"\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\]")
STRAIGHT_QUOTE_SPAN_RE = re.compile(r'"[^"\n]+?"')
CURLY_QUOTE_SPAN_RE = re.compile(r"“[^”\n]+?”")
LOW_SINGLE_QUOTE_SPAN_RE = re.compile(r"‘[^’\n]+?’")
CJK_CORNER_QUOTE_SPAN_RE = re.compile(r"「[^」\n]+?」")
CJK_WHITE_CORNER_QUOTE_SPAN_RE = re.compile(r"『[^』\n]+?』")


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


def count_quote_spans(text: str) -> int:
    patterns = (
        STRAIGHT_QUOTE_SPAN_RE,
        CURLY_QUOTE_SPAN_RE,
        LOW_SINGLE_QUOTE_SPAN_RE,
        CJK_CORNER_QUOTE_SPAN_RE,
        CJK_WHITE_CORNER_QUOTE_SPAN_RE,
    )
    return sum(len(pattern.findall(text)) for pattern in patterns)


def freeze_english_master(config: AppConfig) -> str:
    source_path = config.final_draft_output_path
    if not source_path.exists():
        raise FileNotFoundError(f"Final English report not found: {source_path}")

    master_text = source_path.read_text(encoding="utf-8").strip() + "\n"
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
        "Preserve citation markers exactly.",
        "Preserve quotation boundaries.",
        "Return translated markdown only.",
    ]
    return "\n".join(instructions) + "\n\nEnglish markdown chunk:\n\n" + chunk_text


def validate_translation_chunk(source_chunk: str, translated_chunk: str) -> None:
    stripped = translated_chunk.strip()
    if not stripped:
        raise ValueError("Translated chunk is empty")

    if extract_heading_levels(stripped) != extract_heading_levels(source_chunk):
        raise ValueError("Translated chunk changed the markdown heading structure")

    if extract_visible_citation_markers(stripped) != extract_visible_citation_markers(source_chunk):
        raise ValueError("Translated chunk changed the citation marker inventory")


def write_translation_output(output_path, text: str, *, language_name: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text.strip() + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s translation to %s", language_name, output_path)


def translate_document(
    config: AppConfig,
    *,
    stage_name: str,
    prompt_key: str,
    model_key: str,
    output_path,
    language_name: str,
    source_text: str | None = None,
) -> str:
    master_text = source_text or load_english_master(config)
    max_chunk_chars = int(config.translation.get("max_chunk_chars", 5000))
    chunks = split_markdown_into_chunks(master_text, max_chars=max_chunk_chars)
    system_prompt = load_translation_prompt(config, prompt_key)
    transport_override = (
        str(config.translation.get("llm_transport", "")).strip()
        or str(config.drafting.get("llm_transport", "")).strip()
        or None
    )

    translated_chunks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        translated_chunks.append(
            invoke_text_completion(
                config,
                stage_name=stage_name,
                system_prompt=system_prompt,
                user_prompt=build_translation_user_prompt(
                    chunk,
                    chunk_index=index,
                    total_chunks=len(chunks),
                    language_name=language_name,
                ),
                output_path=str(output_path),
                model_name=config.model_name_for(model_key),
                response_validator=lambda text, source_chunk=chunk: validate_translation_chunk(source_chunk, text),
                transport_override=transport_override,
            ).strip()
        )

    translated_text = "\n\n".join(translated_chunks).strip() + "\n"
    write_translation_output(output_path, translated_text, language_name=language_name)
    return translated_text
