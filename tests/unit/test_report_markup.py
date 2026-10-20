"""The chapter markup subset: what parses, what refuses by line, and how inline text
becomes page markup with its pins resolved."""

from __future__ import annotations

import pytest

from report.markup import (
    Callout,
    Contents,
    Figure,
    Heading,
    List,
    Paragraph,
    Table,
    inline_markup,
    parse_chapter,
    pin_names,
    unpinned_numbers,
)

CHAPTER = """\
# A chapter

{{contents}}

> The result,
> set apart.

- one item
- a second item
  that continues

Two lines
of one paragraph with {{pin:whole.agent.base}}.

## A section

![The caption, with {{pin:runs.total}}.](headline.png)

| System | Base |
|---|---|
| Investigator | {{pin:whole.agent.base}} of 30 |
"""


def test_the_subset_parses_to_its_block_kinds_in_order() -> None:
    assert parse_chapter(CHAPTER) == (
        Heading(1, "A chapter"),
        Contents(),
        Callout("The result, set apart."),
        List(("one item", "a second item that continues")),
        Paragraph("Two lines of one paragraph with {{pin:whole.agent.base}}."),
        Heading(2, "A section"),
        Figure("headline.png", "The caption, with {{pin:runs.total}}."),
        Table(("System", "Base"), (("Investigator", "{{pin:whole.agent.base}} of 30"),)),
    )


@pytest.mark.parametrize(
    ("text", "line", "what"),
    [
        ("Fine.\n\n* a list item\n", 3, "a bulleted list with asterisks"),
        ("- an item\nnot continued\n", 2, "a list item starts with"),
        ("> a callout\nwithout its mark\n", 2, "every line of a callout"),
        ("{{contents}}\nand more\n", 1, "the contents directive stands alone"),
        ("```\ncode\n```\n", 1, "a fenced block"),
        ("#### Too deep\n", 1, "a heading deeper than three levels"),
        ("1. a numbered item\n", 1, "a numbered list"),
        ("# Heading\nwith a line after it\n", 1, "a heading stands alone"),
        ("| a | b |\n| 1 | 2 |\n", 1, "the rule"),
        ("| a | b |\n|---|---|\n| 1 |\n", 3, "1 cells in a table of 2 columns"),
    ],
)
def test_a_construct_outside_the_subset_refuses_by_line(text: str, line: int, what: str) -> None:
    with pytest.raises(ValueError, match=f"line {line}: .*{what}"):
        parse_chapter(text)


def test_inline_markup_resolves_pins_escapes_and_marks_emphasis() -> None:
    marked = inline_markup("**{{pin:n}}** of *30* & <all>", {"n": "24"})
    assert marked == "<b>24</b> of <i>30</i> &amp; &lt;all&gt;"


def test_a_link_becomes_an_anchor() -> None:
    assert inline_markup("see [the site](https://example.org/x) now", {}) == (
        'see <a href="https://example.org/x" color="#2a78d6">the site</a> now'
    )


def test_a_code_span_is_set_in_the_monospace_face() -> None:
    assert inline_markup("read `a/b.json` once", {}) == (
        'read <font face="Courier">a/b.json</font> once'
    )
    with pytest.raises(ValueError, match="unbalanced emphasis"):
        inline_markup("a ` stray", {})


def test_an_unknown_pin_and_an_unbalanced_emphasis_refuse() -> None:
    with pytest.raises(ValueError, match="unknown pin 'nope'"):
        inline_markup("{{pin:nope}}", {})
    with pytest.raises(ValueError, match="unbalanced emphasis"):
        inline_markup("a * stray", {})


def test_pin_names_and_unpinned_numbers_are_read_over_every_block_kind() -> None:
    blocks = parse_chapter(CHAPTER)
    assert pin_names(blocks) == frozenset({"whole.agent.base", "runs.total"})
    assert unpinned_numbers(blocks) == (("30", "of 30"),)
