from __future__ import annotations

from pathlib import Path

from agent_gatsby.normalize import normalize_source_text


def test_normalize_source_text_skips_full_source_front_matter() -> None:
    source_path = Path(__file__).resolve().parents[1] / "data/source/gatsby_source.txt"
    raw_text = source_path.read_text(encoding="utf-8")

    normalized = normalize_source_text(raw_text)

    assert normalized.startswith("Chapter I\n\nIn my younger and more vulnerable years")
    assert not normalized.startswith("Chapter IX\n\nOnce again to Zelda")
