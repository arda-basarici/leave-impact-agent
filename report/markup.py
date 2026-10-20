"""The chapter markup: the small subset of Markdown a chapter may use, parsed to typed
blocks, and the inline forms a block's text may carry.

Chapters are committed Markdown so that a fact-checker, a proofreader and an external
reader meet prose rather than paragraph strings in Python. The subset is deliberate and
closed: a heading of up to three levels, a paragraph, a callout (a quoted paragraph set
in a shaded box), a figure directive, a pipe table, a contents directive, and inside
text the two emphases, a code span for an identifier or a path, and a pin reference.
Anything else refuses the chapter by line, so a construct joins the subset by a decision
here and never through a renderer's tolerance. Parsing is pure; what a block becomes on a
page is ``generate``'s.

A pin reference, ``{{pin:name}}``, is how a chapter states a figure: the build resolves
it from the record that holds it (``pins``), and a chapter cannot carry a number the
build did not read. Literal digits remain allowed, since a date or a count of chapters is
a number too; ``unpinned_numbers`` lists them for the fact-checker's review.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

__all__ = [
    "PIN_REFERENCE",
    "Block",
    "Callout",
    "Contents",
    "Figure",
    "Heading",
    "Paragraph",
    "Table",
    "inline_markup",
    "parse_chapter",
    "pin_names",
    "unpinned_numbers",
]


@dataclass(frozen=True, slots=True)
class Heading:
    """A heading at ``level`` 1 to 3; level 1 opens a chapter."""

    level: int
    text: str


@dataclass(frozen=True, slots=True)
class Paragraph:
    """Running text; a chapter's consecutive lines join into one paragraph."""

    text: str


@dataclass(frozen=True, slots=True)
class Callout:
    """A paragraph the page sets apart in a shaded box: the result a skimming reader
    must not miss. Written as a quoted paragraph, every line starting with ``> ``."""

    text: str


@dataclass(frozen=True, slots=True)
class Contents:
    """The place the table of contents is rendered, with page numbers the build fills
    in; written as the directive ``{{contents}}`` on a line of its own."""


@dataclass(frozen=True, slots=True)
class Figure:
    """An image under the report's figures directory, by its file name, with its caption."""

    path: str
    caption: str


@dataclass(frozen=True, slots=True)
class Table:
    """A pipe table: the header row and the body rows, every row the header's width."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


Block = Heading | Paragraph | Callout | Figure | Table | Contents

PIN_REFERENCE = re.compile(r"\{\{pin:([a-z0-9_.]+)\}\}")
"""A pin reference inside text: the pin's name, lower case, dots and underscores."""

_HEADING = re.compile(r"^(#{1,3}) (\S.*)$")
_FIGURE = re.compile(r"^!\[(.*)\]\(([^()\s]+)\)$")
_TABLE_RULE = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"\*(.+?)\*")
_CODE = re.compile(r"`([^`]+)`")
_NUMBER = re.compile(r"\d[\d,.]*\d|\d")
_OUTSIDE = (
    ("- ", "a bulleted list"),
    ("* ", "a bulleted list"),
    ("```", "a fenced block"),
    ("#", "a heading deeper than three levels or without its space"),
)
_NUMBERED = re.compile(r"^\d+\. ")


def parse_chapter(text: str) -> tuple[Block, ...]:
    """The blocks of a chapter, in order; blank lines separate blocks. Refuses, naming the
    line, any construct outside the subset: a list, a quote, a fenced block, a heading
    deeper than three levels, a heading or a figure directive that does not stand alone,
    and a table whose rows differ in width or whose second line is not the rule.

    >>> [type(block).__name__ for block in parse_chapter("# Title\\n\\nOne\\nline.\\n")]
    ['Heading', 'Paragraph']
    >>> parse_chapter("One\\ntwo.")[0].text
    'One two.'
    >>> parse_chapter("{{contents}}")
    (Contents(),)
    """
    return tuple(_block(number, lines) for number, lines in _chunks(text))


def _chunks(text: str) -> Iterator[tuple[int, tuple[str, ...]]]:
    """Groups of consecutive non-blank lines, each with the number of its first line."""
    lines: list[str] = []
    start = 0
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if not lines:
                start = number
            lines.append(line.rstrip())
        elif lines:
            yield start, tuple(lines)
            lines = []
    if lines:
        yield start, tuple(lines)


def _block(number: int, lines: tuple[str, ...]) -> Block:
    first = lines[0]
    if (heading := _HEADING.match(first)) is not None:
        if len(lines) > 1:
            raise ValueError(f"line {number}: a heading stands alone, with a blank line after")
        return Heading(len(heading.group(1)), heading.group(2).strip())
    if (figure := _FIGURE.match(first)) is not None:
        if len(lines) > 1:
            raise ValueError(f"line {number}: a figure directive stands alone")
        return Figure(figure.group(2), figure.group(1).strip())
    if first.startswith("|"):
        return _table(number, lines)
    if first == "{{contents}}":
        if len(lines) > 1:
            raise ValueError(f"line {number}: the contents directive stands alone")
        return Contents()
    if first.startswith("> "):
        for offset, line in enumerate(lines):
            if not line.startswith("> "):
                raise ValueError(
                    f"line {number + offset}: every line of a callout starts with '> '"
                )
        return Callout(" ".join(line[2:].strip() for line in lines))
    for offset, line in enumerate(lines):
        for start, what in _OUTSIDE:
            if line.lstrip().startswith(start):
                raise ValueError(f"line {number + offset}: {what} is outside the chapter subset")
        if _NUMBERED.match(line.lstrip()):
            raise ValueError(
                f"line {number + offset}: a numbered list is outside the chapter subset"
            )
    return Paragraph(" ".join(line.strip() for line in lines))


def _table(number: int, lines: tuple[str, ...]) -> Table:
    if len(lines) < 2 or _TABLE_RULE.match(lines[1]) is None:
        raise ValueError(f"line {number}: a table's second line is the rule, '|---|' per column")
    header = _cells(lines[0])
    rows: list[tuple[str, ...]] = []
    for offset, line in enumerate(lines[2:], start=2):
        if not line.startswith("|"):
            raise ValueError(f"line {number + offset}: a table row starts with '|'")
        row = _cells(line)
        if len(row) != len(header):
            raise ValueError(
                f"line {number + offset}: {len(row)} cells in a table of {len(header)} columns"
            )
        rows.append(row)
    return Table(header, tuple(rows))


def _cells(line: str) -> tuple[str, ...]:
    inner = line.strip()
    if not inner.endswith("|"):
        raise ValueError(f"a table row ends with '|': {line!r}")
    return tuple(cell.strip() for cell in inner[1:-1].split("|"))


def inline_markup(text: str, pins: Mapping[str, str]) -> str:
    """The page markup for ``text``: every pin reference replaced by its rendered text
    from ``pins`` (name to text), the characters the page markup reserves escaped, and
    ``**strong**`` and ``*emphasis*`` turned into their tags, a backticked span set in
    the monospace face. Refuses an unknown pin by name, and an asterisk or a backtick
    left over after the substitutions, since a stray mark beside a figure is a wrong
    figure's neighbour.

    >>> inline_markup("The loop passed {{pin:n}} of **30** & *more*", {"n": "24"})
    'The loop passed 24 of <b>30</b> &amp; <i>more</i>'
    """

    def pin(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in pins:
            raise ValueError(f"unknown pin {name!r}")
        return pins[name]

    resolved = PIN_REFERENCE.sub(pin, text)
    escaped = resolved.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    marked = _ITALIC.sub(r"<i>\1</i>", _BOLD.sub(r"<b>\1</b>", escaped))
    marked = _CODE.sub(r'<font face="Courier">\1</font>', marked)
    if "*" in marked or "`" in marked:
        raise ValueError(f"unbalanced emphasis in {text!r}")
    return marked


def pin_names(blocks: tuple[Block, ...]) -> frozenset[str]:
    """Every pin the blocks reference, by name."""
    return frozenset(name for text in _texts(blocks) for name in PIN_REFERENCE.findall(text))


def unpinned_numbers(blocks: tuple[Block, ...]) -> tuple[tuple[str, str], ...]:
    """Every literal number the blocks state outside a pin reference, each with the text
    around it, in order of appearance: the fact-checker's review list, never a refusal.

    >>> unpinned_numbers((Paragraph("thirty scenarios, 30 runs, {{pin:whole}} passed"),))
    (('30', 'thirty scenarios, 30 runs,  passed'),)
    """
    found: list[tuple[str, str]] = []
    for text in _texts(blocks):
        bare = PIN_REFERENCE.sub("", text)
        for match in _NUMBER.finditer(bare):
            start, end = max(0, match.start() - 30), min(len(bare), match.end() + 30)
            found.append((match.group(0), bare[start:end].strip()))
    return tuple(found)


def _texts(blocks: tuple[Block, ...]) -> Iterator[str]:
    for block in blocks:
        match block:
            case Heading(_, text) | Paragraph(text) | Callout(text) | Figure(_, text):
                yield text
            case Contents():
                pass
            case Table(header, rows):
                yield from header
                for row in rows:
                    yield from row
