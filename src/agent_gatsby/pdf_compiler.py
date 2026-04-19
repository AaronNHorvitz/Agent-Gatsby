"""
Deterministic PDF rendering for Agent Gatsby.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from fpdf import FPDF

from agent_gatsby.config import AppConfig
from agent_gatsby.translation_common import load_english_master

LOGGER = logging.getLogger(__name__)

FONT_HINTS = {
    "NotoSerif-Regular.ttf": "Noto Serif",
    "NotoSerif-Bold.ttf": "Noto Serif:style=Bold",
    "NotoSansSC-Regular.ttf": "Noto Sans CJK SC",
    "NotoSansCJK-VF.ttc": "Noto Sans CJK SC",
}


class NumberedPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font(self.page_font_family, size=10)
        self.cell(0, 10, f"{self.page_no()}", align="C")


def strip_markdown_formatting(text: str) -> str:
    cleaned = text.replace("**", "").replace("__", "")
    cleaned = cleaned.replace("*", "").replace("_", "")
    return cleaned.strip()


def resolve_font_path(config: AppConfig, font_name: str) -> Path:
    local_path = config.resolve_repo_path(Path(config.paths.fonts_dir) / font_name)
    if local_path.exists():
        return local_path

    for root in (Path("/usr/share/fonts"), Path("/usr/local/share/fonts")):
        if not root.exists():
            continue
        match = next(root.rglob(font_name), None)
        if match is not None:
            return match

    if shutil.which("fc-match"):
        pattern = FONT_HINTS.get(font_name, Path(font_name).stem.replace("-", " "))
        result = subprocess.run(
            ["fc-match", "-f", "%{file}\n", pattern],
            check=False,
            capture_output=True,
            text=True,
        )
        candidate = result.stdout.strip()
        if candidate:
            path = Path(candidate)
            if path.exists():
                return path

    raise FileNotFoundError(f"Could not resolve font file: {font_name}")


def configure_pdf_fonts(pdf: NumberedPDF, config: AppConfig, *, language: str) -> None:
    if language == "mandarin":
        regular_path = resolve_font_path(config, str(config.pdf.get("mandarin_font_regular", "NotoSansCJK-VF.ttc")))
        pdf.add_font("Body", style="", fname=str(regular_path))
        pdf.page_font_family = "Body"
        pdf.heading_font_family = "Body"
        return

    regular_key = "english_font_regular" if language == "english" else "spanish_font_regular"
    bold_key = "english_font_bold" if language == "english" else "spanish_font_bold"
    regular_path = resolve_font_path(config, str(config.pdf.get(regular_key, "NotoSerif-Regular.ttf")))
    bold_path = resolve_font_path(config, str(config.pdf.get(bold_key, "NotoSerif-Bold.ttf")))
    pdf.add_font("Body", style="", fname=str(regular_path))
    pdf.add_font("BodyBold", style="", fname=str(bold_path))
    pdf.page_font_family = "Body"
    pdf.heading_font_family = "BodyBold"


def render_markdown_blocks(pdf: NumberedPDF, config: AppConfig, text: str) -> None:
    line_height = float(config.pdf.get("line_height", 7))
    body_font_size = float(config.pdf.get("default_font_size", 12))
    heading_font_size = float(config.pdf.get("heading_font_size", 16))
    title_font_size = float(config.pdf.get("title_font_size", 18))
    blockquote_indent = 8

    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    for block in blocks:
        lines = block.splitlines()
        first_line = lines[0].strip()

        if first_line.startswith("# "):
            pdf.set_font(pdf.heading_font_family, size=title_font_size)
            pdf.multi_cell(0, line_height + 1, strip_markdown_formatting(first_line[2:].strip()))
            pdf.ln(1)
            continue

        if first_line.startswith("## ") or first_line.startswith("### "):
            heading_text = first_line.lstrip("#").strip()
            pdf.set_font(pdf.heading_font_family, size=heading_font_size)
            pdf.multi_cell(0, line_height, strip_markdown_formatting(heading_text))
            pdf.ln(1)
            continue

        if all(line.lstrip().startswith(">") for line in lines):
            quote_lines = [strip_markdown_formatting(line.lstrip()[1:].strip()) for line in lines]
            quote_text = "\n".join(quote_lines)
            pdf.set_font("Body", size=body_font_size)
            pdf.set_x(pdf.l_margin + blockquote_indent)
            pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - blockquote_indent, line_height, quote_text)
            pdf.ln(1)
            continue

        paragraph_text = strip_markdown_formatting(" ".join(line.strip() for line in lines))
        pdf.set_font("Body", size=body_font_size)
        pdf.multi_cell(0, line_height, paragraph_text)
        pdf.ln(1)


def render_pdf_document(
    config: AppConfig,
    *,
    source_path: Path,
    output_path: Path,
    language: str,
) -> None:
    text = source_path.read_text(encoding="utf-8")
    pdf = NumberedPDF(format=str(config.pdf.get("page_size", "A4")))
    pdf.set_auto_page_break(auto=True, margin=float(config.pdf.get("margin_bottom_mm", 25)))
    pdf.set_margins(
        float(config.pdf.get("margin_left_mm", 25)),
        float(config.pdf.get("margin_top_mm", 25)),
        float(config.pdf.get("margin_right_mm", 25)),
    )
    configure_pdf_fonts(pdf, config, language=language)
    pdf.add_page()
    render_markdown_blocks(pdf, config, text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    LOGGER.info("Rendered %s PDF to %s", language, output_path)


def render_pdfs(config: AppConfig) -> list[Path]:
    english_source = config.english_master_output_path
    if not english_source.exists():
        load_english_master(config)

    render_pdf_document(
        config,
        source_path=config.english_master_output_path,
        output_path=config.english_pdf_output_path,
        language="english",
    )
    render_pdf_document(
        config,
        source_path=config.spanish_translation_output_path,
        output_path=config.spanish_pdf_output_path,
        language="spanish",
    )
    render_pdf_document(
        config,
        source_path=config.mandarin_translation_output_path,
        output_path=config.mandarin_pdf_output_path,
        language="mandarin",
    )
    return [
        config.english_pdf_output_path,
        config.spanish_pdf_output_path,
        config.mandarin_pdf_output_path,
    ]
