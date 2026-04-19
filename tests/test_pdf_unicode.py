from __future__ import annotations

from pathlib import Path

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.pdf_compiler import render_pdfs, resolve_font_path


def write_pdf_repo(repo_root: Path) -> Path:
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "artifacts/final").mkdir(parents=True)
    (repo_root / "artifacts/translations").mkdir(parents=True)
    (repo_root / "outputs").mkdir(parents=True)

    (repo_root / "artifacts/final/analysis_english_master.md").write_text(
        "# Title\n\n### Introduction\n\nGatsby reaches for the light [1].\n",
        encoding="utf-8",
    )
    (repo_root / "artifacts/translations/analysis_spanish_draft.md").write_text(
        "# Titulo\n\n### Introduccion\n\nGatsby alcanza la luz [1].\n",
        encoding="utf-8",
    )
    (repo_root / "artifacts/translations/analysis_mandarin_draft.md").write_text(
        "# 标题\n\n### 引言\n\n盖茨比伸手去够那盏灯 [1]。\n",
        encoding="utf-8",
    )

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
translation_outputs:
  spanish_output_path: "artifacts/translations/analysis_spanish_draft.md"
  mandarin_output_path: "artifacts/translations/analysis_mandarin_draft.md"
pdf:
  english_pdf_path: "outputs/Gatsby_Analysis_English.pdf"
  spanish_pdf_path: "outputs/Gatsby_Analysis_Spanish.pdf"
  mandarin_pdf_path: "outputs/Gatsby_Analysis_Mandarin.pdf"
  page_size: "A4"
  margin_left_mm: 25
  margin_right_mm: 25
  margin_top_mm: 25
  margin_bottom_mm: 25
  default_font_size: 12
  heading_font_size: 16
  title_font_size: 18
  line_height: 7
  english_font_regular: "NotoSerif-Regular.ttf"
  english_font_bold: "NotoSerif-Bold.ttf"
  spanish_font_regular: "NotoSerif-Regular.ttf"
  spanish_font_bold: "NotoSerif-Bold.ttf"
  mandarin_font_regular: "NotoSansCJK-VF.ttc"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_render_pdfs_creates_three_outputs(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_pdf_repo(repo_root))

    try:
        resolve_font_path(config, "NotoSerif-Regular.ttf")
        resolve_font_path(config, "NotoSerif-Bold.ttf")
        resolve_font_path(config, "NotoSansCJK-VF.ttc")
    except FileNotFoundError as exc:
        pytest.skip(str(exc))

    output_paths = render_pdfs(config)

    assert len(output_paths) == 3
    for path in output_paths:
        assert path.exists()
        assert path.stat().st_size > 0
