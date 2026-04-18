"""
Passage indexing for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re

from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.schemas import PassageIndex, PassageRecord

LOGGER = logging.getLogger(__name__)

BLOCK_RE = re.compile(r"\S(?:.*?\S)?(?=\n{2,}|\Z)", re.DOTALL)


def roman_to_int(value: str) -> int:
    roman_values = {
        "I": 1,
        "V": 5,
        "X": 10,
        "L": 50,
        "C": 100,
        "D": 500,
        "M": 1000,
    }
    total = 0
    previous = 0
    for character in reversed(value.upper()):
        current = roman_values[character]
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total


def chapter_label_to_number(label: str) -> int:
    raw_label = label.strip()
    if raw_label.isdigit():
        return int(raw_label)
    return roman_to_int(raw_label)


def make_passage_id(chapter: int, paragraph: int, template: str) -> str:
    return template.format(chapter=chapter, paragraph=paragraph)


def build_passage_index(
    normalized_text: str,
    *,
    chapter_pattern: str,
    passage_id_format: str = "{chapter}.{paragraph}",
    remove_empty_paragraphs: bool = True,
    normalized_path: str = "",
    source_name: str = "gatsby_locked",
) -> PassageIndex:
    chapter_re = re.compile(chapter_pattern, re.IGNORECASE)
    passages: list[PassageRecord] = []
    chapter_number = 0
    paragraph_number = 0
    seen_ids: set[str] = set()

    for match in BLOCK_RE.finditer(normalized_text):
        block_text = match.group(0).strip()
        if not block_text:
            continue

        if chapter_re.fullmatch(block_text):
            chapter_label = block_text.split(maxsplit=1)[1]
            chapter_number = chapter_label_to_number(chapter_label)
            paragraph_number = 0
            continue

        if chapter_number == 0:
            raise ValueError("Encountered passage text before the first chapter heading")

        if remove_empty_paragraphs and not block_text:
            continue

        paragraph_number += 1
        passage_id = make_passage_id(chapter_number, paragraph_number, passage_id_format)
        if passage_id in seen_ids:
            raise ValueError(f"Duplicate passage ID generated: {passage_id}")

        passage = PassageRecord(
            passage_id=passage_id,
            chapter=chapter_number,
            paragraph=paragraph_number,
            text=block_text,
            char_start=match.start(),
            char_end=match.end(),
        )
        passages.append(passage)
        seen_ids.add(passage_id)

    if not passages:
        raise ValueError("Passage indexing produced no passages")

    chapter_count = max(passage.chapter for passage in passages)
    return PassageIndex(
        source_name=source_name,
        normalized_path=normalized_path,
        chapter_count=chapter_count,
        passage_count=len(passages),
        generated_at=utc_now_iso(),
        passages=passages,
    )


def write_passage_index(config: AppConfig, passage_index: PassageIndex) -> None:
    output_path = config.passage_index_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(passage_index.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote passage index to %s", output_path)


def index_normalized_text(config: AppConfig, normalized_text: str) -> PassageIndex:
    passage_index = build_passage_index(
        normalized_text,
        chapter_pattern=config.indexing.chapter_pattern,
        passage_id_format=config.indexing.passage_id_format,
        remove_empty_paragraphs=config.indexing.remove_empty_paragraphs,
        normalized_path=config.source.normalized_output_path,
        source_name=config.normalized_output_path.stem,
    )
    write_passage_index(config, passage_index)
    return passage_index

