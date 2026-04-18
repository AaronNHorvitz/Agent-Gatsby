from __future__ import annotations

import hashlib

from agent_gatsby.config import load_config
from agent_gatsby.data_ingest import compute_sha256, ingest_source


def test_compute_sha256_is_stable_and_non_empty() -> None:
    data = b"Gatsby reached toward the green light."

    first_hash = compute_sha256(data)
    second_hash = compute_sha256(data)

    assert first_hash == second_hash
    assert first_hash
    assert len(first_hash) == 64


def test_ingest_source_writes_manifest(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "data/source").mkdir(parents=True)

    source_text = "Chapter I\n\nA green light trembled in the dark.\n"
    source_path = repo_root / "data/source/gatsby_source.txt"
    source_path.write_text(source_text, encoding="utf-8")

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
    loaded_text, manifest = ingest_source(config)

    assert loaded_text == source_text
    assert manifest.sha256 == hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    assert manifest.source_name == "gatsby_locked"

    manifest_path = repo_root / "artifacts/manifests/source_manifest.json"
    assert manifest_path.exists()
    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert '"source_path": "data/source/gatsby_source.txt"' in manifest_text
    assert f'"sha256": "{manifest.sha256}"' in manifest_text
