"""
Source normalization for Agent Gatsby.
"""

from __future__ import annotations

import logging
import re

from agent_gatsby.config import AppConfig

LOGGER = logging.getLogger(__name__)

START_MARKER_RE = re.compile(r"^\*\*\* START OF THE PROJECT GUTENBERG EBOOK .* \*\*\*$", re.MULTILINE)
END_MARKER_RE = re.compile(r"^\*\*\* END OF THE PROJECT GUTENBERG EBOOK .* \*\*\*$", re.MULTILINE)
ROMAN_NUMERAL_RE = re.compile(r"^[IVXLCM]+$", re.IGNORECASE)
CHAPTER_LINE_RE = re.compile(r"^Chapter\s+([IVXLC0-9]+)$", re.IGNORECASE)
HORIZONTAL_RULE_RE = re.compile(r"^-{5,}$")
WHITESPACE_RE = re.compile(r"[ \t]+")


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_utf8_bom(text: str) -> str:
    return text.lstrip("\ufeff")


def extract_gutenberg_body(text: str) -> str:
    start_match = START_MARKER_RE.search(text)
    if start_match:
        text = text[start_match.end():]

    end_match = END_MARKER_RE.search(text)
    if end_match:
        text = text[: end_match.start()]

    return text


def is_chapter_heading(line: str) -> bool:
    stripped = line.strip()
    return bool(CHAPTER_LINE_RE.fullmatch(stripped) or ROMAN_NUMERAL_RE.fullmatch(stripped))


def canonicalize_chapter_heading(line: str) -> str:
    stripped = line.strip()
    chapter_match = CHAPTER_LINE_RE.fullmatch(stripped)
    if chapter_match:
        return f"Chapter {chapter_match.group(1).upper()}"

    if ROMAN_NUMERAL_RE.fullmatch(stripped):
        return f"Chapter {stripped.upper()}"

    raise ValueError(f"Line is not a recognized chapter heading: {line!r}")


def looks_like_prose(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if is_chapter_heading(stripped):
        return False
    return any(character.islower() for character in stripped) or stripped.endswith((".", "!", "?", "”", "\""))


def next_nonempty_block(lines: list[str], start_index: int) -> tuple[list[str], int]:
    index = start_index
    while index < len(lines) and not lines[index].strip():
        index += 1

    block: list[str] = []
    while index < len(lines) and lines[index].strip():
        block.append(lines[index].strip())
        index += 1

    return block, index


def looks_like_opening_paragraph(block_lines: list[str]) -> bool:
    if not block_lines:
        return False

    collapsed = collapse_block_lines(block_lines)
    if is_chapter_heading(collapsed):
        return False

    return len(collapsed) >= 60 and "." in collapsed and looks_like_prose(collapsed)


def find_first_chapter_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if not is_chapter_heading(line):
            continue

        block_lines, _ = next_nonempty_block(lines, index + 1)
        if looks_like_opening_paragraph(block_lines):
            return index

    raise ValueError("Could not find the beginning of chapter text in the source")


def collapse_block_lines(block_lines: list[str]) -> str:
    joined = " ".join(line.strip() for line in block_lines if line.strip())
    return WHITESPACE_RE.sub(" ", joined).strip()


def build_normalized_blocks(lines: list[str]) -> list[str]:
    first_chapter_index = find_first_chapter_index(lines)
    blocks: list[str] = []
    current_block: list[str] = []

    def flush_current_block() -> None:
        if not current_block:
            return

        if len(current_block) == 1 and is_chapter_heading(current_block[0]):
            blocks.append(canonicalize_chapter_heading(current_block[0]))
        else:
            collapsed = collapse_block_lines(current_block)
            if collapsed:
                blocks.append(collapsed)
        current_block.clear()

    for raw_line in lines[first_chapter_index:]:
        stripped = raw_line.strip()
        if not stripped or HORIZONTAL_RULE_RE.fullmatch(stripped):
            flush_current_block()
            continue

        if is_chapter_heading(stripped):
            flush_current_block()
            current_block.append(stripped)
            flush_current_block()
            continue

        current_block.append(stripped)

    flush_current_block()
    return blocks


def normalize_source_text(
    raw_text: str,
    *,
    preserve_chapter_markers: bool = True,
    collapse_excessive_blank_lines: bool = True,
    strip_leading_trailing_whitespace: bool = True,
) -> str:
    if not preserve_chapter_markers:
        raise ValueError("Agent Gatsby normalization requires preserved chapter markers")

    text = strip_utf8_bom(raw_text)
    text = normalize_line_endings(text)
    text = extract_gutenberg_body(text)

    lines = text.split("\n")
    blocks = build_normalized_blocks(lines)
    normalized = "\n\n".join(blocks)

    if collapse_excessive_blank_lines:
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    if strip_leading_trailing_whitespace:
        normalized = normalized.strip()

    if not normalized:
        raise ValueError("Normalized text is empty")

    return normalized


def write_normalized_text(config: AppConfig, normalized_text: str) -> None:
    output_path = config.normalized_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(normalized_text, encoding="utf-8")
    LOGGER.info("Wrote normalized source text to %s", output_path)


def normalize_source(config: AppConfig, raw_text: str) -> str:
    normalized = normalize_source_text(
        raw_text,
        preserve_chapter_markers=config.source.preserve_chapter_markers,
        collapse_excessive_blank_lines=config.source.collapse_excessive_blank_lines,
        strip_leading_trailing_whitespace=config.source.strip_leading_trailing_whitespace,
    )
    write_normalized_text(config, normalized)
    return normalized
