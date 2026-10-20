"""Marking a model-supplied quotation inside the text it was read from, with every piece of
both escaped before the one trusted tag is added.

The world's prose and a model's quotation are both untrusted text on a page that renders
them as text (the scaffold step's autoescape rule), and a highlight is markup added
around a substring of one. Marking after escaping would miss a quotation whose characters
escaping changed; marking before escaping would let the quotation's own markup through.
So the source text is split on each quotation as plain text, every piece is escaped, and
the pieces are joined with the trusted ``<mark>`` tag (the report step's external read).
A quotation the text does not contain marks nothing; the page says so beside it.
"""

from __future__ import annotations

from collections.abc import Iterable

from markupsafe import Markup, escape


def mark_quotes(text: str, quotes: Iterable[str]) -> Markup:
    """``text`` escaped, with every occurrence of each non-empty quotation it contains
    wrapped in ``<mark>``; the quotations are matched as plain text and never rendered as
    markup, and a quotation inside an already marked span is left as marked.

    >>> str(mark_quotes("a <b> c", ["<b>"]))
    'a <mark>&lt;b&gt;</mark> c'
    >>> str(mark_quotes("plain", ["absent", ""]))
    'plain'
    """
    pieces: list[tuple[str, bool]] = [(text, False)]
    for quote in quotes:
        if not quote:
            continue
        split: list[tuple[str, bool]] = []
        for piece, marked in pieces:
            if marked:
                split.append((piece, True))
                continue
            parts = piece.split(quote)
            for index, part in enumerate(parts):
                if index:
                    split.append((quote, True))
                if part:
                    split.append((part, False))
        pieces = split
    return Markup("").join(
        Markup("<mark>") + escape(piece) + Markup("</mark>") if marked else escape(piece)
        for piece, marked in pieces
    )


__all__ = ["mark_quotes"]
