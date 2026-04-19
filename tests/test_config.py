from __future__ import annotations

from pathlib import Path

import pytest

from agent_gatsby.config import load_config


def write_config_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "config/prompts/draft.md").write_text("Draft prompt.\n", encoding="utf-8")

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
prompts:
  draft_prompt_path: "config/prompts/draft.md"
extraction:
  output_path: "artifacts/evidence/metaphor_candidates.json"
  raw_debug_output_path: "artifacts/evidence/metaphor_candidates_raw.txt"
evidence_ledger:
  output_path: "artifacts/evidence/evidence_ledger.json"
  rejected_output_path: "artifacts/evidence/rejected_candidates.json"
outline:
  output_path: "artifacts/drafts/outline.json"
drafting:
  output_path: "artifacts/drafts/analysis_english_draft.md"
  section_drafts_dir: "artifacts/drafts/sections"
  final_output_path: "artifacts/drafts/analysis_english_final.md"
  master_output_path: "artifacts/final/analysis_english_master.md"
  citation_text_output_path: "artifacts/final/citation_text.md"
translation_outputs:
  spanish_output_path: "artifacts/translations/analysis_spanish_draft.md"
  mandarin_output_path: "artifacts/translations/analysis_mandarin_draft.md"
  spanish_qa_report_path: "artifacts/qa/spanish_qa_report.json"
  mandarin_qa_report_path: "artifacts/qa/mandarin_qa_report.json"
pdf:
  english_pdf_path: "outputs/Gatsby_Analysis_English.pdf"
  spanish_pdf_path: "outputs/Gatsby_Analysis_Spanish.pdf"
  mandarin_pdf_path: "outputs/Gatsby_Analysis_Mandarin.pdf"
manifest:
  output_path: "outputs/final_manifest.json"
verification:
  output_path: "artifacts/qa/english_verification_report.json"
  citation_registry_output_path: "artifacts/qa/citation_registry.json"
models:
  primary_reasoner: "gemma4:26b"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_load_config_resolves_repo_and_output_paths(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_config_repo(repo_root))

    assert config.repo_root_path == repo_root.resolve()
    assert config.source_file_path == repo_root / "data/source/gatsby_source.txt"
    assert config.metaphor_candidates_path == repo_root / "artifacts/evidence/metaphor_candidates.json"
    assert config.final_draft_output_path == repo_root / "artifacts/drafts/analysis_english_final.md"
    assert config.english_master_output_path == repo_root / "artifacts/final/analysis_english_master.md"
    assert config.citation_text_output_path == repo_root / "artifacts/final/citation_text.md"
    assert config.spanish_translation_output_path == repo_root / "artifacts/translations/analysis_spanish_draft.md"
    assert config.mandarin_translation_output_path == repo_root / "artifacts/translations/analysis_mandarin_draft.md"
    assert config.spanish_qa_report_path == repo_root / "artifacts/qa/spanish_qa_report.json"
    assert config.mandarin_qa_report_path == repo_root / "artifacts/qa/mandarin_qa_report.json"
    assert config.english_pdf_output_path == repo_root / "outputs/Gatsby_Analysis_English.pdf"
    assert config.spanish_pdf_output_path == repo_root / "outputs/Gatsby_Analysis_Spanish.pdf"
    assert config.mandarin_pdf_output_path == repo_root / "outputs/Gatsby_Analysis_Mandarin.pdf"
    assert config.final_manifest_output_path == repo_root / "outputs/final_manifest.json"
    assert config.english_verification_report_path == repo_root / "artifacts/qa/english_verification_report.json"
    assert config.citation_registry_output_path == repo_root / "artifacts/qa/citation_registry.json"
    assert config.resolve_prompt_path("draft_prompt_path") == repo_root / "config/prompts/draft.md"
    assert config.model_name_for("primary_reasoner") == "gemma4:26b"


def test_require_mapping_value_raises_for_missing_or_blank_keys(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_config_repo(repo_root))

    config.drafting["final_output_path"] = ""
    with pytest.raises(ValueError, match="Missing required config value: drafting.final_output_path"):
        _ = config.final_draft_output_path

    with pytest.raises(ValueError, match="Missing required config value: prompts.missing_prompt_path"):
        config.resolve_prompt_path("missing_prompt_path")
