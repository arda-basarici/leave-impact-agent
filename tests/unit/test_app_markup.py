"""The quote marking: the source text and every quotation are escaped as text, the mark is the
one trusted tag, a quotation is matched as plain text through characters escaping changes, a
quotation the text does not hold marks nothing, and an overlapping second quotation never
splits a span already marked."""

from __future__ import annotations

from markupsafe import Markup

from leaveimpact.app.markup import mark_quotes


def test_the_text_and_the_quotation_are_both_escaped_and_the_mark_is_the_only_tag() -> None:
    marked = mark_quotes("before <b>bold</b> & after", ["<b>bold</b> &"])
    assert isinstance(marked, Markup)
    assert str(marked) == "before <mark>&lt;b&gt;bold&lt;/b&gt; &amp;</mark> after"


def test_a_quotation_carrying_markup_is_never_rendered_as_markup() -> None:
    marked = mark_quotes("plain text", ["<script>alert(1)</script>"])
    assert str(marked) == "plain text"
    marked = mark_quotes("say <i>hi</i> twice, <i>hi</i>.", ["<i>hi</i>"])
    assert str(marked) == (
        "say <mark>&lt;i&gt;hi&lt;/i&gt;</mark> twice, <mark>&lt;i&gt;hi&lt;/i&gt;</mark>."
    )


def test_a_second_quotation_inside_a_marked_span_leaves_the_span_whole() -> None:
    marked = mark_quotes("the Kafka migration last year", ["Kafka migration", "migration"])
    assert str(marked) == "the <mark>Kafka migration</mark> last year"
    marked = mark_quotes("the Kafka migration last year", ["migration", "Kafka migration"])
    assert str(marked) == "the Kafka <mark>migration</mark> last year"


def test_an_empty_quotation_marks_nothing() -> None:
    assert str(mark_quotes("a & b", [""])) == "a &amp; b"
