"""Deterministic PDF rendering for Agent Gatsby artifacts.

This module converts the finalized English master and localized markdown
documents into plain, professional PDFs. Rendering is intentionally
deterministic: the model supplies markdown, while this renderer handles page
layout, fonts, spacing, section pagination, and Unicode-safe output.
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
ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\u2060\ufeff]")

FONT_HINTS = {
    "NotoSerif-Regular.ttf": "Noto Serif",
    "NotoSerif-Bold.ttf": "Noto Serif:style=Bold",
    "NotoSans-Regular.ttf": "Noto Sans",
    "NotoSans-Bold.ttf": "Noto Sans:style=Bold",
    "NotoSansSC-Regular.ttf": "Noto Sans CJK SC",
    "NotoSansCJK-VF.ttc": "Noto Sans CJK SC",
}


class NumberedPDF(FPDF):
    """FPDF subclass that adds centered page numbers.

    Notes
    -----
    The renderer stores the active page font family on the instance so the
    footer can reuse the same body font that was configured for the document's
    language.
    """

    def footer(self) -> None:
        """Render the page-number footer on each page.

        Returns
        -------
        None
        """

        self.set_y(-15)
        self.set_font(self.page_font_family, size=10)
        self.cell(0, 10, f"{self.page_no()}", align="C")


def strip_markdown_formatting(text: str) -> str:
    """Remove lightweight markdown emphasis markers from visible text.

    Parameters
    ----------
    text : str
        Raw markdown text fragment.

    Returns
    -------
    str
        Plain text with simple emphasis markers removed.
    """

    cleaned = text.replace("**", "").replace("__", "")
    cleaned = cleaned.replace("*", "").replace("_", "")
    return cleaned.strip()


def normalize_render_text(text: str, *, language: str) -> str:
    """Normalize text immediately before PDF rendering.

    Parameters
    ----------
    text : str
        Text about to be written into the PDF.
    language : str
        Language identifier for the document being rendered.

    Returns
    -------
    str
        Render-safe text with zero-width characters removed and excessive
        horizontal spacing collapsed.
    """

    normalized = ZERO_WIDTH_RE.sub("", text.strip())
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized


def language_pdf_setting(config: AppConfig, *, language: str, key: str, default: float) -> float:
    """Resolve a PDF configuration value with language override support.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.
    language : str
        Document language key such as ``"english"`` or ``"mandarin"``.
    key : str
        Base PDF configuration key.
    default : float
        Fallback value when neither a language-specific nor a global setting is
        present.

    Returns
    -------
    float
        Resolved numeric PDF setting.
    """

    language_key = f"{language}_{key}"
    if language_key in config.pdf:
        return float(config.pdf.get(language_key, default))
    return float(config.pdf.get(key, default))


def is_numbered_list_block(lines: list[str]) -> bool:
    """Determine whether a block contains only numbered-list lines.

    Parameters
    ----------
    lines : list of str
        Raw block lines.

    Returns
    -------
    bool
        ``True`` when every non-empty line begins with a numbered-list marker.
    """

    non_empty_lines = [line.strip() for line in lines if line.strip()]
    return bool(non_empty_lines) and all(NUMBERED_LIST_LINE_RE.match(line) for line in non_empty_lines)


def is_label_plus_blockquote_block(lines: list[str]) -> bool:
    """Detect a label paragraph followed by one or more blockquote lines.

    Parameters
    ----------
    lines : list of str
        Raw block lines.

    Returns
    -------
    bool
        ``True`` when the first line is prose and all remaining non-empty lines
        are blockquotes.
    """

    if len(lines) < 2:
        return False
    if lines[0].lstrip().startswith(">"):
        return False
    trailing_lines = [line for line in lines[1:] if line.strip()]
    return bool(trailing_lines) and all(line.lstrip().startswith(">") for line in trailing_lines)


def count_sentences(text: str) -> int:
    """Estimate sentence count for layout heuristics.

    Parameters
    ----------
    text : str
        Plain-text paragraph or section preview.

    Returns
    -------
    int
        Estimated sentence count, with a minimum of one for non-empty text.
    """

    stripped = text.strip()
    if not stripped:
        return 0
    count = len(SENTENCE_END_RE.findall(stripped))
    return count if count > 0 else 1


def flatten_block_text(lines: list[str]) -> str:
    """Flatten a markdown block into a single plain-text preview line.

    Parameters
    ----------
    lines : list of str
        Markdown block lines.

    Returns
    -------
    str
        Concatenated plain text suitable for preview-height estimation.
    """

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
    """Collect enough following prose to estimate heading keep-together space.

    Parameters
    ----------
    blocks : list of str
        Markdown blocks for the whole document.
    start_index : int
        Index of the current section block in ``blocks``.
    current_lines : list of str
        Lines belonging to the current heading block after the heading itself.
    min_sentences : int
        Minimum preview sentence count to accumulate.

    Returns
    -------
    str
        Plain-text preview built from the current section and nearby prose.
    """

    preview_parts: list[str] = []
    sentence_count = 0

    def append_preview(lines: list[str]) -> None:
        """Append block text into the preview accumulator.

        Parameters
        ----------
        lines : list of str
            Source lines to flatten and append.

        Returns
        -------
        None
        """

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
    """Compute usable horizontal space for the current page.

    Parameters
    ----------
    pdf : NumberedPDF
        Active PDF document.
    indent : float, default=0
        Additional indentation to subtract from the available width.

    Returns
    -------
    float
        Available width in the current page box.
    """

    return pdf.w - pdf.l_margin - pdf.r_margin - indent


def estimate_rendered_height(
    pdf: NumberedPDF,
    *,
    text: str,
    width: float,
    line_height: float,
    align: str,
) -> float:
    """Estimate how much vertical space a text block will consume.

    Parameters
    ----------
    pdf : NumberedPDF
        Active PDF document.
    text : str
        Text to be rendered.
    width : float
        Rendering width available to the block.
    line_height : float
        Configured line height.
    align : str
        Alignment mode passed to ``multi_cell``.

    Returns
    -------
    float
        Estimated rendered height in PDF units.
    """

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
    """Return the remaining vertical space on the current PDF page.

    Parameters
    ----------
    pdf : NumberedPDF
        Active PDF document.

    Returns
    -------
    float
        Remaining height before the page-break trigger.
    """

    if hasattr(pdf, "get_y") and hasattr(pdf, "page_break_trigger"):
        return float(pdf.page_break_trigger - pdf.get_y())
    return float("inf")


def resolve_font_path(config: AppConfig, font_name: str) -> Path:
    """Resolve a font file from repo assets or system font locations.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.
    font_name : str
        Font filename or configured font asset name.

    Returns
    -------
    Path
        Resolved filesystem path to the font file.

    Raises
    ------
    FileNotFoundError
        If the font cannot be found in the repository, common system font
        locations, or via ``fc-match``.
    """

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
    """Register body and heading fonts for a target language.

    Parameters
    ----------
    pdf : NumberedPDF
        Active PDF document.
    config : AppConfig
        Loaded application configuration.
    language : str
        Target language being rendered.

    Returns
    -------
    None
    """

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
    """Render markdown text into the PDF body using deterministic layout rules.

    Parameters
    ----------
    pdf : NumberedPDF
        Active PDF document.
    config : AppConfig
        Loaded application configuration.
    text : str
        Markdown document content to render.
    language : str
        Target language being rendered.

    Returns
    -------
    None
    """

    line_height = language_pdf_setting(config, language=language, key="line_height", default=7)
    body_font_size = language_pdf_setting(config, language=language, key="default_font_size", default=12)
    heading_font_size = language_pdf_setting(config, language=language, key="heading_font_size", default=16)
    title_font_size = language_pdf_setting(config, language=language, key="title_font_size", default=18)
    paragraph_spacing = language_pdf_setting(config, language=language, key="paragraph_spacing", default=line_height)
    title_spacing_after = language_pdf_setting(
        config,
        language=language,
        key="title_spacing_after",
        default=line_height * 2,
    )
    heading_spacing_before = language_pdf_setting(
        config,
        language=language,
        key="heading_spacing_before",
        default=line_height * 2,
    )
    heading_spacing_after = language_pdf_setting(
        config,
        language=language,
        key="heading_spacing_after",
        default=line_height * 2,
    )
    citation_entry_spacing = language_pdf_setting(
        config,
        language=language,
        key="citation_entry_spacing",
        default=0,
    )
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
        """Force a new page when a keep-together block would overflow.

        Parameters
        ----------
        content_text : str
            Text that may need to stay together.
        width : float
            Width available for the block.
        spacing_after : float
            Vertical spacing added after the block.
        align : str, default="L"
            Alignment mode used for estimation.
        keep_together : bool, default=False
            Whether the block should be kept on a single page.

        Returns
        -------
        None
        """

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
        """Determine whether a paragraph should avoid mid-block page breaks.

        Parameters
        ----------
        paragraph_text : str
            Paragraph text after markdown stripping.

        Returns
        -------
        bool
            ``True`` when the paragraph is short or contains visible citations.
        """

        sentence_count = count_sentences(paragraph_text)
        return sentence_count <= paragraph_keep_together_max_sentences or bool(VISIBLE_CITATION_RE.search(paragraph_text))

    def render_paragraph(paragraph_text: str) -> None:
        """Render a normal prose paragraph.

        Parameters
        ----------
        paragraph_text : str
            Plain-text paragraph content.

        Returns
        -------
        None
        """

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
        """Render an indented blockquote section.

        Parameters
        ----------
        quote_lines : list of str
            Quote lines without the leading blockquote marker.

        Returns
        -------
        None
        """

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
    """Render one markdown source file into a PDF artifact.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.
    source_path : Path
        Markdown source file to render.
    output_path : Path
        Destination PDF path.
    language : str
        Language key used to select fonts and layout settings.

    Returns
    -------
    None
    """

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
    """Render the English, Spanish, and Mandarin PDFs.

    Parameters
    ----------
    config : AppConfig
        Loaded application configuration.

    Returns
    -------
    list of Path
        Output paths for the rendered PDFs.
    """

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
