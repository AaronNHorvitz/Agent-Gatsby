"""
Deterministic PDF rendering for Agent Gatsby.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from fpdf import FPDF

from agent_gatsby.config import AppConfig
from agent_gatsby.translation_common import load_english_master

LOGGER = logging.getLogger(__name__)

NUMBERED_LIST_LINE_RE = re.compile(r"^\d+\.\s+")
CITATION_SECTION_HEADINGS = {"Citations", "Citas", "引文"}
SENTENCE_END_RE = re.compile(r'[.!?](?:["”’)\]]+)?|[。！？]')
VISIBLE_CITATION_RE = re.compile(r"\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\]")
CITATION_SPACE_RE = re.compile(r"(?<=\S)\s+(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])")
CITATION_PUNCTUATION_RE = re.compile(
    r"(\[(?:\d+|\d+\.\d+|#\d+,\s*Chapter\s+\d+,\s*Paragraph\s+\d+)\])([,.;:!?，。；：！？、])"
)

FONT_HINTS = {
    "NotoSerif-Regular.ttf": "Noto Serif",
    "NotoSerif-Bold.ttf": "Noto Serif:style=Bold",
    "NotoSans-Regular.ttf": "Noto Sans",
    "NotoSans-Bold.ttf": "Noto Sans:style=Bold",
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


def normalize_render_text(text: str, *, language: str) -> str:
    normalized = re.sub(r"[ \t]{2,}", " ", text.strip())
    if language == "mandarin":
        return normalized
    normalized = CITATION_SPACE_RE.sub(lambda match: "\u202f" + match.group(1), normalized)
    normalized = CITATION_PUNCTUATION_RE.sub(lambda match: match.group(1) + "\u2060" + match.group(2), normalized)
    return normalized


def is_numbered_list_block(lines: list[str]) -> bool:
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    return bool(non_empty_lines) and all(NUMBERED_LIST_LINE_RE.match(line) for line in non_empty_lines)


def is_label_plus_blockquote_block(lines: list[str]) -> bool:
    if len(lines) < 2:
        return False
    if lines[0].lstrip().startswith(">"):
        return False
    trailing_lines = [line for line in lines[1:] if line.strip()]
    return bool(trailing_lines) and all(line.lstrip().startswith(">") for line in trailing_lines)


def count_sentences(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    count = len(SENTENCE_END_RE.findall(stripped))
    return count if count > 0 else 1


def flatten_block_text(lines: list[str]) -> str:
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            stripped = stripped.lstrip(">").strip()
        cleaned_lines.append(strip_markdown_formatting(stripped))
    return " ".join(cleaned_lines).strip()


def collect_section_preview_text(
    blocks: list[str],
    *,
    start_index: int,
    current_lines: list[str],
    min_sentences: int,
) -> str:
    preview_parts: list[str] = []
    sentence_count = 0

    def append_preview(lines: list[str]) -> None:
        nonlocal sentence_count
        text = flatten_block_text(lines)
        if not text:
            return
        preview_parts.append(text)
        sentence_count += count_sentences(text)

    append_preview(current_lines)
    if sentence_count >= min_sentences:
        return " ".join(preview_parts).strip()

    for block in blocks[start_index + 1 :]:
        lines = block.splitlines()
        first_line = lines[0].strip()
        if first_line.startswith("# "):
            break
        if first_line.startswith("## ") or first_line.startswith("### "):
            break
        append_preview(lines)
        if sentence_count >= min_sentences:
            break

    return " ".join(preview_parts).strip()


def usable_page_width(pdf: NumberedPDF, *, indent: float = 0) -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin - indent


def estimate_rendered_height(
    pdf: NumberedPDF,
    *,
    text: str,
    width: float,
    line_height: float,
    align: str,
) -> float:
    if not text.strip():
        return 0.0
    try:
        lines = pdf.multi_cell(
            width,
            line_height,
            text,
            align=align,
            dry_run=True,
            output="LINES",
        )
        if isinstance(lines, tuple):
            lines = next((item for item in lines if isinstance(item, list)), [text])
        if isinstance(lines, list):
            return max(len(lines), 1) * line_height
    except TypeError:
        pass
    return max(len(text.splitlines()), 1) * line_height


def remaining_page_space(pdf: NumberedPDF) -> float:
    if hasattr(pdf, "get_y") and hasattr(pdf, "page_break_trigger"):
        return float(pdf.page_break_trigger - pdf.get_y())
    return float("inf")


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


def render_markdown_blocks(pdf: NumberedPDF, config: AppConfig, text: str, *, language: str) -> None:
    line_height = float(config.pdf.get("line_height", 7))
    body_font_size = float(config.pdf.get("default_font_size", 12))
    heading_font_size = float(config.pdf.get("heading_font_size", 16))
    title_font_size = float(config.pdf.get("title_font_size", 18))
    paragraph_spacing = float(config.pdf.get("paragraph_spacing", line_height))
    title_spacing_after = float(config.pdf.get("title_spacing_after", line_height * 2))
    heading_spacing_before = float(config.pdf.get("heading_spacing_before", line_height * 2))
    heading_spacing_after = float(config.pdf.get("heading_spacing_after", line_height * 2))
    citation_entry_spacing = float(config.pdf.get("citation_entry_spacing", 0))
    blockquote_indent = 8
    section_min_following_sentences = int(config.pdf.get("section_min_following_sentences", 5))
    paragraph_keep_together_max_sentences = int(config.pdf.get("paragraph_keep_together_max_sentences", 3))

    def maybe_start_new_page_for_text(
        content_text: str,
        *,
        width: float,
        spacing_after: float,
        align: str = "L",
        keep_together: bool = False,
    ) -> None:
        if not keep_together:
            return
        required_height = estimate_rendered_height(
            pdf,
            text=content_text,
            width=width,
            line_height=line_height,
            align=align,
        ) + spacing_after
        if remaining_page_space(pdf) < required_height:
            pdf.add_page()

    def paragraph_should_stay_together(paragraph_text: str) -> bool:
        sentence_count = count_sentences(paragraph_text)
        return sentence_count <= paragraph_keep_together_max_sentences or bool(VISIBLE_CITATION_RE.search(paragraph_text))

    def render_paragraph(paragraph_text: str) -> None:
        normalized_text = normalize_render_text(paragraph_text, language=language)
        pdf.set_font("Body", size=body_font_size)
        maybe_start_new_page_for_text(
            normalized_text,
            width=usable_page_width(pdf),
            spacing_after=paragraph_spacing,
            align="L",
            keep_together=paragraph_should_stay_together(normalized_text),
        )
        pdf.multi_cell(0, line_height, normalized_text, align="L")
        pdf.ln(paragraph_spacing)

    def render_blockquote(quote_lines: list[str]) -> None:
        quote_text = "\n".join(normalize_render_text(line, language=language) for line in quote_lines)
        pdf.set_font("Body", size=body_font_size)
        maybe_start_new_page_for_text(
            quote_text,
            width=pdf.w - pdf.l_margin - pdf.r_margin - blockquote_indent,
            spacing_after=paragraph_spacing,
            align="L",
            keep_together=True,
        )
        pdf.set_x(pdf.l_margin + blockquote_indent)
        pdf.multi_cell(
            pdf.w - pdf.l_margin - pdf.r_margin - blockquote_indent,
            line_height,
            quote_text,
            align="L",
        )
        pdf.ln(paragraph_spacing)

    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    for index, block in enumerate(blocks):
        lines = block.splitlines()
        first_line = lines[0].strip()

        if first_line.startswith("# "):
            pdf.set_font(pdf.heading_font_family, size=title_font_size)
            pdf.multi_cell(0, line_height + 1, strip_markdown_formatting(first_line[2:].strip()), align="L")
            pdf.ln(title_spacing_after)
            lines = lines[1:]
            if not lines:
                continue
            first_line = lines[0].strip()

        if first_line.startswith("## ") or first_line.startswith("### "):
            heading_text = first_line.lstrip("#").strip()
            if heading_text in CITATION_SECTION_HEADINGS and pdf.page_no() > 0:
                pdf.add_page()
            else:
                preview_text = collect_section_preview_text(
                    blocks,
                    start_index=index,
                    current_lines=lines[1:],
                    min_sentences=section_min_following_sentences,
                )
                pdf.set_font(pdf.heading_font_family, size=heading_font_size)
                heading_height = estimate_rendered_height(
                    pdf,
                    text=strip_markdown_formatting(heading_text),
                    width=usable_page_width(pdf),
                    line_height=line_height,
                    align="L",
                )
                pdf.set_font("Body", size=body_font_size)
                preview_height = estimate_rendered_height(
                    pdf,
                    text=preview_text,
                    width=usable_page_width(pdf),
                    line_height=line_height,
                    align="L",
                )
                required_height = heading_spacing_before + heading_height + heading_spacing_after + preview_height
                if remaining_page_space(pdf) < required_height:
                    pdf.add_page()
                else:
                    pdf.ln(heading_spacing_before)
            pdf.set_font(pdf.heading_font_family, size=heading_font_size)
            pdf.multi_cell(0, line_height, strip_markdown_formatting(heading_text), align="L")
            pdf.ln(heading_spacing_after)
            lines = lines[1:]
            if not lines:
                continue
            first_line = lines[0].strip()

        if all(line.lstrip().startswith(">") for line in lines):
            quote_lines = [strip_markdown_formatting(line.lstrip()[1:].strip()) for line in lines]
            render_blockquote(quote_lines)
            continue

        if is_label_plus_blockquote_block(lines):
            render_paragraph(strip_markdown_formatting(lines[0].strip()))
            quote_lines = [strip_markdown_formatting(line.lstrip()[1:].strip()) for line in lines[1:] if line.strip()]
            render_blockquote(quote_lines)
            continue

        if is_numbered_list_block(lines):
            pdf.set_font("Body", size=body_font_size)
            for line in lines:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                normalized_line = normalize_render_text(strip_markdown_formatting(stripped_line), language=language)
                maybe_start_new_page_for_text(
                    normalized_line,
                    width=usable_page_width(pdf),
                    spacing_after=citation_entry_spacing,
                    align="L",
                    keep_together=True,
                )
                pdf.multi_cell(0, line_height, normalized_line, align="L")
                pdf.ln(citation_entry_spacing)
            continue

        paragraph_text = strip_markdown_formatting(" ".join(line.strip() for line in lines))
        render_paragraph(paragraph_text)


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
    render_markdown_blocks(pdf, config, text, language=language)

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
