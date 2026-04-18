from __future__ import annotations

from agent_gatsby.config import load_config
from agent_gatsby.index_text import build_passage_index, index_normalized_text


def test_build_passage_index_assigns_deterministic_ids_and_offsets() -> None:
    normalized_text = (
        "Chapter I\n\n"
        "Gatsby reached toward the green light at the end of the dock.\n\n"
        "The water between him and the light looked like a dark promise.\n\n"
        "Chapter II\n\n"
        "The valley of ashes lay under the gray morning like a ruined field."
    )

    first_passage_index = build_passage_index(
        normalized_text,
        chapter_pattern=r"^Chapter\s+[IVXLC0-9]+$",
    )
    second_passage_index = build_passage_index(
        normalized_text,
        chapter_pattern=r"^Chapter\s+[IVXLC0-9]+$",
    )

    assert [passage.passage_id for passage in first_passage_index.passages] == ["1.1", "1.2", "2.1"]
    assert [passage.passage_id for passage in first_passage_index.passages] == [
        passage.passage_id for passage in second_passage_index.passages
    ]
    assert len({passage.passage_id for passage in first_passage_index.passages}) == len(
        first_passage_index.passages
    )
    assert [passage.chapter for passage in first_passage_index.passages] == [1, 1, 2]
    assert all(isinstance(passage.chapter, int) for passage in first_passage_index.passages)
    assert all(passage.text for passage in first_passage_index.passages)
    assert normalized_text[
        first_passage_index.passages[1].char_start : first_passage_index.passages[1].char_end
    ] == first_passage_index.passages[1].text


def test_index_normalized_text_writes_output_file(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "data/normalized").mkdir(parents=True)

    normalized_text = (
        "Chapter I\n\n"
        "Gatsby reached toward the green light at the end of the dock.\n\n"
        "The water between him and the light looked like a dark promise.\n\n"
        "Chapter II\n\n"
        "The valley of ashes lay under the gray morning like a ruined field.\n\n"
        "Her voice was full of money, and everyone in the room leaned toward it."
    )
    normalized_path = repo_root / "data/normalized/gatsby_locked.txt"
    normalized_path.write_text(normalized_text, encoding="utf-8")

    config_text = """
paths:
  repo_root: "."
  config_dir: "config"
  source_dir: "data/source"
  normalized_dir: "data/normalized"
  artifacts_dir: "artifacts"
  manifests_dir: "artifacts/manifests"
  evidence_dir: "artifacts/evidence"
  drafts_dir: "artifacts/drafts"
  final_dir: "artifacts/final"
  translations_dir: "artifacts/translations"
  qa_dir: "artifacts/qa"
  logs_dir: "artifacts/logs"
  outputs_dir: "outputs"
  fonts_dir: "fonts"
source:
  file_path: "data/source/gatsby_source.txt"
  normalized_output_path: "data/normalized/gatsby_locked.txt"
  manifest_output_path: "artifacts/manifests/source_manifest.json"
  encoding: "utf-8"
  preserve_chapter_markers: true
  collapse_excessive_blank_lines: true
  strip_leading_trailing_whitespace: true
indexing:
  output_path: "artifacts/manifests/passage_index.json"
  chapter_pattern: "^Chapter\\\\s+[IVXLC0-9]+$"
  paragraph_split_strategy: "blank_line"
  remove_empty_paragraphs: true
  passage_id_format: "{chapter}.{paragraph}"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")

    config = load_config(config_path)
    passage_index = index_normalized_text(config, normalized_text)

    output_path = repo_root / "artifacts/manifests/passage_index.json"
    assert output_path.exists()
    assert passage_index.chapter_count == 2
    assert passage_index.passage_count == 4
    assert '"passage_id": "2.2"' in output_path.read_text(encoding="utf-8")
