"""The report's build: the chapters under ``report/chapters`` rendered in file order to
one PDF, every pin resolved from the records, a DRAFT footer until the freeze.

Usage, from the repository root with the ``report`` dependency group installed::

    uv run --group report python -m report.generate [--output PATH] [--final]

The build refuses a chapter outside the markup subset, an unknown pin and a figure file
that does not exist, each by name. It prints the literal numbers the chapters state
without a pin as the fact-checker's review list and does not refuse them, since a date
or a count of chapters is a number too. The PDF opens on a cover the build draws from the
constants below; the first heading of the first chapter is the report's title on the
page after it, and every later top-level heading opens a chapter on a fresh page with a
bookmark. The contents directive renders the chapters with their page numbers, which
needs the page engine's second pass. The typeface is Source Sans 3, committed under
``report/fonts`` with its license, so the PDF renders the same on any machine.
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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from report.markup import (
    Block,
    Callout,
    Contents,
    Figure,
    Heading,
    inline_markup,
    parse_chapter,
    unpinned_numbers,
)
from report.markup import (
    List as Bullets,
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
SUBTITLE_LINES = (
    "An LLM leave-impact investigator against one-call readers",
    "under a fixed output budget, on a constructed organization",
)
SUBTITLE = " ".join(SUBTITLE_LINES)
PROJECT = "Leave Impact Agent, the investigator milestone"
PROMISE = "Every number pinned to its record at build time"
AUTHOR = "Arda Başarıcı"
DATE = "October 2026"
SITE = "ardabasarici.dev"
REPOSITORY_URL = "github.com/arda-basarici/leave-impact-agent"
CHAPTERS = REPOSITORY / "report" / "chapters"
FIGURES = REPOSITORY / "report" / "figures"
FONTS = REPOSITORY / "report" / "fonts"
OUTPUT = REPOSITORY / "report" / "where-the-single-call-stops.pdf"

_PAGE_WIDTH, _PAGE_HEIGHT = A4
_MARGIN = 22 * mm
_TEXT_WIDTH = _PAGE_WIDTH - 2 * _MARGIN

NAVY = colors.HexColor("#14263f")
ACCENT = colors.HexColor("#2a78d6")
SHADE = colors.HexColor("#eef3fa")
INK = colors.HexColor("#2b2b2b")
MUTED = colors.HexColor("#6f6f6f")

_FAMILY = "SourceSans3"
_REGULAR, _BOLD, _ITALIC, _BOLD_ITALIC = (
    "SourceSans3",
    "SourceSans3-Bold",
    "SourceSans3-It",
    "SourceSans3-BoldIt",
)
_MONO = "Courier"

_BODY = ParagraphStyle(
    "body",
    fontName=_REGULAR,
    fontSize=10.5,
    leading=14.5,
    spaceAfter=7,
    textColor=INK,
    allowWidows=0,
    allowOrphans=0,
)
_ITEM = ParagraphStyle("item", parent=_BODY, spaceAfter=3)
_TITLE = ParagraphStyle(
    "title", fontName=_BOLD, fontSize=24, leading=29, spaceAfter=6, textColor=NAVY
)
_CHAPTER = ParagraphStyle(
    "chapter", fontName=_BOLD, fontSize=18, leading=22, spaceAfter=2, textColor=NAVY
)
_SECTION = ParagraphStyle(
    "section",
    fontName=_BOLD,
    fontSize=12.5,
    leading=16,
    spaceBefore=9,
    spaceAfter=4,
    keepWithNext=1,
    textColor=NAVY,
)
_SUBSECTION = ParagraphStyle(
    "subsection",
    fontName=_BOLD_ITALIC,
    fontSize=11,
    leading=14,
    spaceBefore=6,
    spaceAfter=4,
    keepWithNext=1,
    textColor=INK,
)
_CAPTION = ParagraphStyle(
    "caption",
    fontName=_ITALIC,
    fontSize=9,
    leading=12,
    spaceBefore=3,
    spaceAfter=10,
    textColor=MUTED,
)
_CALLOUT = ParagraphStyle(
    "callout", fontName=_REGULAR, fontSize=10.5, leading=14.5, textColor=INK
)
_CELL = ParagraphStyle("cell", fontName=_REGULAR, fontSize=9.5, leading=12, textColor=INK)
_HEADER_CELL = ParagraphStyle(
    "header", fontName=_BOLD, fontSize=9.5, leading=12, textColor=colors.white
)
_TOC_ENTRY = ParagraphStyle(
    "toc", fontName=_REGULAR, fontSize=10.5, leading=16, textColor=INK
)
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
    """Render every ``*.md`` under ``chapters_dir``, in file order, to ``output`` behind
    the cover; figures resolve under ``figures_dir``; pins by name from ``pins``. Refuses
    an empty chapters directory, and lets a chapter's own refusal (a construct outside
    the subset, an unknown pin, a missing figure) propagate with the chapter's name
    prepended."""
    paths = sorted(chapters_dir.glob("*.md"))
    if not paths:
        raise ValueError(f"no chapters under {chapters_dir}")
    _register_fonts()
    texts = {name: pin.text for name, pin in pins.items()}
    story: list[Flowable] = [NextPageTemplate("page"), PageBreak()]
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


def _register_fonts() -> None:
    """Register the committed typeface once; the names above are the family's."""
    if _REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    for name, file in (
        (_REGULAR, "SourceSans3-Regular.ttf"),
        (_BOLD, "SourceSans3-Bold.ttf"),
        (_ITALIC, "SourceSans3-It.ttf"),
        (_BOLD_ITALIC, "SourceSans3-BoldIt.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
    pdfmetrics.registerFontFamily(
        _FAMILY, normal=_REGULAR, bold=_BOLD, italic=_ITALIC, boldItalic=_BOLD_ITALIC
    )


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
                flowables.append(
                    HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceAfter=10)
                )
            case Heading(level, text):
                flowables.append(Paragraph(inline_markup(text, pins), _HEADINGS[level]))
            case Prose(text):
                flowables.append(Paragraph(inline_markup(text, pins), _BODY))
            case Callout(text):
                flowables.append(_callout(inline_markup(text, pins)))
            case Bullets(items):
                flowables.append(_bullets([inline_markup(item, pins) for item in items]))
            case Figure(name, caption):
                flowables.append(_figure(figures_dir / name, inline_markup(caption, pins)))
            case Grid(header, rows):
                flowables.append(_table(header, rows, pins))
            case Contents():
                flowables.append(_contents())
            case _:
                raise ValueError(f"no rendering for a {type(block).__name__} block")
    return flowables


def _bullets(items: Sequence[str]) -> Flowable:
    return ListFlowable(
        [ListItem(Paragraph(item, _ITEM), leftIndent=14) for item in items],
        bulletType="bullet",
        bulletFontSize=7,
        bulletOffsetY=-1,
        leftIndent=14,
        spaceAfter=6,
    )


def _callout(markup: str) -> Flowable:
    box = Table([[Paragraph(markup, _CALLOUT)]], colWidths=[_TEXT_WIDTH], hAlign="LEFT")
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SHADE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return KeepTogether([box, Spacer(1, 8)])


def _contents() -> Flowable:
    contents = TableOfContents()
    contents.levelStyles = [_TOC_ENTRY]
    contents.dotsMinLevel = 0
    return contents


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
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("LINEBELOW", (0, -1), (-1, -1), 0.4, MUTED),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return KeepTogether([table, Spacer(1, 8)])


class _Document(BaseDocTemplate):
    """The page engine's document with the two page templates, the running furniture,
    and the hooks that turn chapter and section headings into bookmarks and contents
    entries."""

    def __init__(self, output: str, *, draft: bool) -> None:
        super().__init__(
            output,
            pagesize=A4,
            leftMargin=_MARGIN,
            rightMargin=_MARGIN,
            topMargin=_MARGIN,
            bottomMargin=_MARGIN,
            title=TITLE,
            author=AUTHOR,
            subject=f"{PROJECT}: {SUBTITLE}",
        )
        self.draft = draft
        self.headings = 0
        self.chapters = 0
        frame = Frame(_MARGIN, _MARGIN, _TEXT_WIDTH, _PAGE_HEIGHT - 2 * _MARGIN, id="body")
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[frame], onPage=self._cover),
                PageTemplate(id="page", frames=[frame], onPage=self._furniture),
            ]
        )

    def beforeDocument(self) -> None:
        self.headings = 0
        self.chapters = 0

    def afterFlowable(self, flowable: Flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return
        style = flowable.style.name
        if style not in ("chapter", "section"):
            return
        if style == "section" and not self.chapters:
            return  # the front matter's sections sit under no chapter
        self.headings += 1
        key = f"heading-{self.headings}"
        text = flowable.getPlainText()
        self.canv.bookmarkPage(key)
        level = 0 if style == "chapter" else 1
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        if style == "chapter":
            self.chapters += 1
            self.notify("TOCEntry", (0, text, self.page, key))

    def _cover(self, canvas: Canvas, document: BaseDocTemplate) -> None:
        canvas.saveState()
        top, bottom = _PAGE_HEIGHT * 0.78, _PAGE_HEIGHT * 0.40
        canvas.setFillColor(NAVY)
        canvas.rect(_MARGIN, bottom, _TEXT_WIDTH, top - bottom, stroke=0, fill=1)
        centre = _PAGE_WIDTH / 2
        canvas.setFillColor(colors.white)
        canvas.setFont(_BOLD, 26)
        canvas.drawCentredString(centre, top - 70, TITLE)
        canvas.setFont(_REGULAR, 13)
        for offset, line in enumerate(SUBTITLE_LINES):
            canvas.drawCentredString(centre, top - 96 - 18 * offset, line)
        canvas.setFont(_REGULAR, 11)
        canvas.drawCentredString(centre, top - 148, PROJECT)
        canvas.drawCentredString(centre, top - 166, PROMISE)
        canvas.setFillColor(colors.HexColor("#9cc0ee"))
        canvas.setFont(_REGULAR, 10.5)
        links = f"{SITE}  ·  {REPOSITORY_URL}"
        canvas.drawCentredString(centre, bottom + 58, links)
        width = canvas.stringWidth(links, _REGULAR, 10.5)
        left = centre - width / 2
        site_width = canvas.stringWidth(SITE, _REGULAR, 10.5)
        repository_width = canvas.stringWidth(REPOSITORY_URL, _REGULAR, 10.5)
        canvas.linkURL(
            f"https://{SITE}/", (left, bottom + 54, left + site_width, bottom + 70), relative=0
        )
        canvas.linkURL(
            f"https://{REPOSITORY_URL}",
            (left + width - repository_width, bottom + 54, left + width, bottom + 70),
            relative=0,
        )
        canvas.setFillColor(colors.white)
        canvas.drawCentredString(centre, bottom + 36, f"{AUTHOR}  ·  {DATE}")
        if self.draft:
            canvas.setFillColor(MUTED)
            canvas.setFont(_REGULAR, 9)
            canvas.drawCentredString(centre, bottom - 24, "DRAFT")
        canvas.restoreState()

    def _furniture(self, canvas: Canvas, document: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont(_BOLD, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(_MARGIN, _PAGE_HEIGHT - 14 * mm, TITLE.upper())
        canvas.setFont(_REGULAR, 8)
        canvas.drawRightString(_PAGE_WIDTH - _MARGIN, _PAGE_HEIGHT - 14 * mm, AUTHOR)
        canvas.setFont(_REGULAR, 8)
        canvas.drawString(_MARGIN, 12 * mm, PROJECT)
        canvas.drawRightString(_PAGE_WIDTH - _MARGIN, 12 * mm, str(self.page))
        if self.draft:
            canvas.drawCentredString(_PAGE_WIDTH / 2, 12 * mm, "DRAFT")
        canvas.restoreState()


def _render(output: Path, story: Sequence[Flowable], *, draft: bool) -> None:
    document = _Document(str(output), draft=draft)
    document.multiBuild(list(story))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the report PDF from its chapters.")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--final", action="store_true", help="drop the DRAFT marks")
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
