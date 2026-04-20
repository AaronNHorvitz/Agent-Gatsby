from __future__ import annotations

from pathlib import Path

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.pdf_compiler import render_markdown_blocks, render_pdfs, resolve_font_path


def normalize_rendered_test_text(text: str) -> str:
    return text


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
  default_font_size: 9
  heading_font_size: 13
  title_font_size: 15
  line_height: 5.5
  paragraph_spacing: 3
  title_spacing_after: 6
  heading_spacing_before: 6
  heading_spacing_after: 6
  citation_entry_spacing: 0
  section_min_following_sentences: 5
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


class FakePDF:
    def __init__(self) -> None:
        self.page_font_family = "Body"
        self.heading_font_family = "BodyBold"
        self.l_margin = 25
        self.r_margin = 25
        self.w = 210
        self.page_break_trigger = 272
        self.page_count = 1
        self.current_y = 25.0
        self.font_calls: list[tuple[str, float]] = []
        self.multi_cell_calls: list[str] = []
        self.ln_calls: list[float] = []
        self.x_positions: list[float] = []
        self.add_page_calls = 0

    def set_font(self, family: str, size: float, style: str = "") -> None:
        self.font_calls.append((family or style, size))

    def multi_cell(
        self,
        w: float,
        h: float,
        text: str,
        align: str = "J",
        dry_run: bool = False,
        output: str | None = None,
        **_: object,
    ):
        lines = [line for line in text.split("\n") if line] or [text]
        if dry_run and output == "LINES":
            return lines
        self.multi_cell_calls.append(text)
        self.current_y += max(len(lines), 1) * h

    def ln(self, h: float | None = None) -> None:
        delta = 0.0 if h is None else float(h)
        self.ln_calls.append(delta)
        self.current_y += delta

    def set_x(self, value: float) -> None:
        self.x_positions.append(value)

    def add_page(self) -> None:
        self.add_page_calls += 1
        self.page_count += 1
        self.current_y = 25.0

    def page_no(self) -> int:
        return self.page_count

    def get_y(self) -> float:
        return self.current_y


def test_render_markdown_blocks_keeps_citations_on_separate_lines_and_adds_spacing(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_pdf_repo(repo_root))
    pdf = FakePDF()
    text = """# Title

### Introduction

Metaphor text:
> *"Quoted one"* [1]
> *"Quoted two"* [2]

First paragraph.

Second paragraph.

## Citations

1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "Alpha".
2. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 2, cited passage beginning "Beta".
"""

    render_markdown_blocks(pdf, config, text, language="english")

    normalized_calls = [normalize_rendered_test_text(call) for call in pdf.multi_cell_calls]

    assert "Metaphor text:" in normalized_calls
    assert '"Quoted one" [1]\n"Quoted two" [2]' in normalized_calls
    assert "1. F. Scott Fitzgerald, The Great Gatsby, ch. 1, para. 1, cited passage beginning \"Alpha\"." in normalized_calls
    assert "2. F. Scott Fitzgerald, The Great Gatsby, ch. 1, para. 2, cited passage beginning \"Beta\"." in normalized_calls
    assert all(
        "1. F. Scott Fitzgerald, The Great Gatsby, ch. 1, para. 1, cited passage beginning \"Alpha\". 2." not in call
        for call in normalized_calls
    )
    assert 3.0 in pdf.ln_calls
    assert 6.0 in pdf.ln_calls
    assert 0.0 in pdf.ln_calls
    assert pdf.add_page_calls == 1
    assert all("\u2060" not in call and "\u202f" not in call for call in pdf.multi_cell_calls)


def test_render_markdown_blocks_keeps_heading_followed_immediately_by_citation_entries(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_pdf_repo(repo_root))
    pdf = FakePDF()
    text = """# Title

Body paragraph.

## Citas
1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "Alpha".
2. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 2, cited passage beginning "Beta".
"""

    render_markdown_blocks(pdf, config, text, language="spanish")

    normalized_calls = [normalize_rendered_test_text(call) for call in pdf.multi_cell_calls]

    assert "Citas" in normalized_calls
    assert "1. F. Scott Fitzgerald, The Great Gatsby, ch. 1, para. 1, cited passage beginning \"Alpha\"." in normalized_calls
    assert "2. F. Scott Fitzgerald, The Great Gatsby, ch. 1, para. 2, cited passage beginning \"Beta\"." in normalized_calls


def test_render_markdown_blocks_strips_hidden_zero_width_characters(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_pdf_repo(repo_root))
    pdf = FakePDF()
    text = "# Title\n\nGatsby reaches for the light [1]\u2060.\n"

    render_markdown_blocks(pdf, config, text, language="english")

    assert all("\u2060" not in call and "\ufeff" not in call for call in pdf.multi_cell_calls)
    assert "Gatsby reaches for the light [1]." in pdf.multi_cell_calls


def test_render_markdown_blocks_moves_section_to_new_page_when_space_is_too_tight(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_pdf_repo(repo_root))
    pdf = FakePDF()
    pdf.current_y = pdf.page_break_trigger - 8
    text = """### Tight Section

Sentence one. Sentence two. Sentence three. Sentence four. Sentence five.
"""

    render_markdown_blocks(pdf, config, text, language="english")

    assert pdf.add_page_calls == 1
    assert "Tight Section" in pdf.multi_cell_calls
