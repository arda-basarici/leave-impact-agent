"""The report's build: the chapters under ``report/chapters`` rendered in file order to
one PDF, every pin resolved from the records, a DRAFT footer until the freeze.

Usage, from the repository root with the ``report`` dependency group installed::

    uv run --group report python -m report.generate [--output PATH] [--final]

The build refuses a chapter outside the markup subset, an unknown pin and a figure file
that does not exist, each by name. It prints the literal numbers the chapters state
without a pin as the fact-checker's review list and does not refuse them, since a date
or a count of chapters is a number too. The first heading of the first chapter is the
report's title and opens no new page; every later top-level heading opens a chapter on a
fresh page. The typeface is the page engine's built-in Helvetica until the first viewable
render settles the styling.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from report.markup import (
    Block,
    Figure,
    Heading,
    inline_markup,
    parse_chapter,
    unpinned_numbers,
)
from report.markup import (
    Paragraph as Prose,
)
from report.markup import (
    Table as Grid,
)
from report.pins import Pin, load_pins

__all__ = ["BuildReport", "REPOSITORY", "TITLE", "build", "main"]

REPOSITORY = Path(__file__).resolve().parents[1]
TITLE = "Where the Single Call Stops"
CHAPTERS = REPOSITORY / "report" / "chapters"
FIGURES = REPOSITORY / "report" / "figures"
OUTPUT = REPOSITORY / "report" / "where-the-single-call-stops.pdf"

_PAGE_WIDTH, _PAGE_HEIGHT = A4
_MARGIN = 22 * mm
_TEXT_WIDTH = _PAGE_WIDTH - 2 * _MARGIN

_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=14.5, spaceAfter=7)
_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=22, leading=27, spaceAfter=10)
_CHAPTER = ParagraphStyle(
    "chapter", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=10, keepWithNext=1
)
_SECTION = ParagraphStyle(
    "section",
    fontName="Helvetica-Bold",
    fontSize=12.5,
    leading=16,
    spaceBefore=8,
    spaceAfter=5,
    keepWithNext=1,
)
_SUBSECTION = ParagraphStyle(
    "subsection",
    fontName="Helvetica-BoldOblique",
    fontSize=11,
    leading=14,
    spaceBefore=6,
    spaceAfter=4,
    keepWithNext=1,
)
_CAPTION = ParagraphStyle(
    "caption", fontName="Helvetica-Oblique", fontSize=9, leading=12, spaceBefore=3, spaceAfter=10
)
_CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9.5, leading=12)
_HEADER_CELL = ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=9.5, leading=12)
_HEADINGS = {1: _CHAPTER, 2: _SECTION, 3: _SUBSECTION}


@dataclass(frozen=True, slots=True)
class BuildReport:
    """What a build produced: the PDF's path, the chapters rendered in order, and every
    literal number the chapters state without a pin, with the text around it."""

    output: Path
    chapters: tuple[str, ...]
    unpinned: tuple[tuple[str, str, str], ...]


def build(
    chapters_dir: Path,
    figures_dir: Path,
    output: Path,
    pins: Mapping[str, Pin],
    *,
    draft: bool = True,
) -> BuildReport:
    """Render every ``*.md`` under ``chapters_dir``, in file order, to ``output``; figures
    resolve under ``figures_dir``; pins by name from ``pins``. Refuses an empty chapters
    directory, and lets a chapter's own refusal (a construct outside the subset, an
    unknown pin, a missing figure) propagate with the chapter's name prepended."""
    paths = sorted(chapters_dir.glob("*.md"))
    if not paths:
        raise ValueError(f"no chapters under {chapters_dir}")
    texts = {name: pin.text for name, pin in pins.items()}
    story: list[Flowable] = []
    unpinned: list[tuple[str, str, str]] = []
    for index, path in enumerate(paths):
        try:
            blocks = parse_chapter(path.read_text(encoding="utf-8"))
            story.extend(_flowables(blocks, texts, figures_dir, first_chapter=index == 0))
        except (ValueError, FileNotFoundError) as fault:
            raise type(fault)(f"{path.name}: {fault}") from None
        unpinned.extend((path.name, number, around) for number, around in unpinned_numbers(blocks))
    _render(output, story, draft=draft)
    return BuildReport(output, tuple(path.name for path in paths), tuple(unpinned))


def _flowables(
    blocks: Sequence[Block], pins: Mapping[str, str], figures_dir: Path, *, first_chapter: bool
) -> list[Flowable]:
    flowables: list[Flowable] = []
    for position, block in enumerate(blocks):
        match block:
            case Heading(1, text) if first_chapter and position == 0:
                flowables.append(Paragraph(inline_markup(text, pins), _TITLE))
            case Heading(1, text):
                flowables.append(PageBreak())
                flowables.append(Paragraph(inline_markup(text, pins), _CHAPTER))
            case Heading(level, text):
                flowables.append(Paragraph(inline_markup(text, pins), _HEADINGS[level]))
            case Prose(text):
                flowables.append(Paragraph(inline_markup(text, pins), _BODY))
            case Figure(name, caption):
                flowables.append(_figure(figures_dir / name, inline_markup(caption, pins)))
            case Grid(header, rows):
                flowables.append(_table(header, rows, pins))
    return flowables


def _figure(path: Path, caption: str) -> Flowable:
    if not path.is_file():
        raise FileNotFoundError(f"figure {path.name} is not under {path.parent}")
    width, height = ImageReader(str(path)).getSize()
    scale = min(1.0, _TEXT_WIDTH / width)
    image = Image(str(path), width=width * scale, height=height * scale)
    return KeepTogether([Spacer(1, 4), image, Paragraph(caption, _CAPTION)])


def _table(
    header: Sequence[str], rows: Sequence[Sequence[str]], pins: Mapping[str, str]
) -> Flowable:
    cells = [[Paragraph(inline_markup(cell, pins), _HEADER_CELL) for cell in header]]
    cells.extend([Paragraph(inline_markup(cell, pins), _CELL) for cell in row] for row in rows)
    columns = len(header)
    first = _TEXT_WIDTH * (0.3 if columns > 2 else 0.4)
    rest = (_TEXT_WIDTH - first) / max(columns - 1, 1)
    table = Table(cells, hAlign="LEFT", colWidths=[first, *([rest] * (columns - 1))])
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                ("LINEBELOW", (0, -1), (-1, -1), 0.3, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return KeepTogether([table, Spacer(1, 8)])


def _render(output: Path, story: Sequence[Flowable], *, draft: bool) -> None:
    def footer(canvas: Canvas, document: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(_MARGIN, 12 * mm, TITLE)
        canvas.drawRightString(_PAGE_WIDTH - _MARGIN, 12 * mm, str(document.page))
        if draft:
            canvas.drawCentredString(_PAGE_WIDTH / 2, 12 * mm, "DRAFT")
        canvas.restoreState()

    document = BaseDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
        title=TITLE,
    )
    frame = Frame(_MARGIN, _MARGIN, _TEXT_WIDTH, _PAGE_HEIGHT - 2 * _MARGIN, id="body")
    document.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=footer)])
    document.build(list(story))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the report PDF from its chapters.")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--final", action="store_true", help="drop the DRAFT footer")
    arguments = parser.parse_args(argv)
    report = build(
        CHAPTERS, FIGURES, arguments.output, load_pins(REPOSITORY), draft=not arguments.final
    )
    print(f"built {report.output} from {len(report.chapters)} chapters")
    if report.unpinned:
        print(f"{len(report.unpinned)} literal numbers without a pin, for review:")
        for chapter, number, around in report.unpinned:
            print(f"  {chapter}: {number}  in  {around!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
