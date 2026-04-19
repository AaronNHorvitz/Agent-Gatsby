from __future__ import annotations

import json
from pathlib import Path

from agent_gatsby.config import load_config
from agent_gatsby.manifest_writer import write_manifest


def write_manifest_repo(repo_root: Path) -> Path:
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "artifacts/manifests").mkdir(parents=True)
    (repo_root / "artifacts/final").mkdir(parents=True)
    (repo_root / "artifacts/translations").mkdir(parents=True)
    (repo_root / "artifacts/qa").mkdir(parents=True)
    (repo_root / "outputs").mkdir(parents=True)

    (repo_root / "artifacts/manifests/source_manifest.json").write_text(
        json.dumps({"sha256": "abc123"}, indent=2),
        encoding="utf-8",
    )
    for path in (
        repo_root / "artifacts/final/analysis_english_master.md",
        repo_root / "artifacts/final/citation_text.md",
        repo_root / "artifacts/translations/analysis_spanish_draft.md",
        repo_root / "artifacts/translations/analysis_mandarin_draft.md",
        repo_root / "artifacts/qa/english_verification_report.json",
        repo_root / "artifacts/qa/spanish_qa_report.json",
        repo_root / "artifacts/qa/mandarin_qa_report.json",
        repo_root / "outputs/Gatsby_Analysis_English.pdf",
    ):
        path.write_text("artifact\n", encoding="utf-8")

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
indexing:
  output_path: "artifacts/manifests/passage_index.json"
  chapter_pattern: "^Chapter\\\\s+[IVXLC0-9]+$"
  paragraph_split_strategy: "blank_line"
drafting:
  final_output_path: "artifacts/drafts/analysis_english_final.md"
  master_output_path: "artifacts/final/analysis_english_master.md"
  citation_text_output_path: "artifacts/final/citation_text.md"
translation_outputs:
  spanish_output_path: "artifacts/translations/analysis_spanish_draft.md"
  mandarin_output_path: "artifacts/translations/analysis_mandarin_draft.md"
  spanish_qa_report_path: "artifacts/qa/spanish_qa_report.json"
  mandarin_qa_report_path: "artifacts/qa/mandarin_qa_report.json"
verification:
  output_path: "artifacts/qa/english_verification_report.json"
  citation_registry_output_path: "artifacts/qa/citation_registry.json"
pdf:
  english_pdf_path: "outputs/Gatsby_Analysis_English.pdf"
  spanish_pdf_path: "outputs/Gatsby_Analysis_Spanish.pdf"
  mandarin_pdf_path: "outputs/Gatsby_Analysis_Mandarin.pdf"
manifest:
  output_path: "outputs/final_manifest.json"
models:
  primary_reasoner: "gemma4:26b"
  final_critic: "gemma4:26b"
  translator_es: "gemma4:26b"
  translator_zh: "gemma4:26b"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_write_manifest_records_existing_outputs(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_manifest_repo(repo_root))

    manifest = write_manifest(config)

    assert config.final_manifest_output_path.exists()
    payload = json.loads(config.final_manifest_output_path.read_text(encoding="utf-8"))
    assert payload["source_hash"] == "abc123"
    assert str(config.english_master_output_path) in payload["output_files"]
    assert str(config.english_verification_report_path) in payload["qa_reports"]
    assert manifest.models["translator_es"] == "gemma4:26b"
