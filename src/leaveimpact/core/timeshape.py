"""The canonical JSON shapes of ``core``'s time values: a date, a zoned instant, a span of days.

Three codecs write the same three shapes — the entity codec for an event's instants and
a leave's days, the sealed world codecs for a scenario's ``now`` and its windows, and
the tool argument validation for a span the model chooses — so the shapes are defined
once, here, rather than once per codec where they could drift by a key name. A date is
the one spelling ``isoformat`` writes; an instant is an object of the offset-bearing
timestamp and the IANA zone it was read in, ``null`` when it has none, because the zone
is provenance for how a human read the time and the offset alone would flatten it; a
span of days is an object of its two inclusive ends. Decoding is strict in the sealed
codecs' manner: the spelling must be the canonical one (``date_at`` and ``instant_at``
state the rule and why), the object must hold exactly its fields, so the encoding of a
decoding reproduces the bytes for every value this accepts.

The fact-value codec writes an instant *span* in its own shape, start and end with one
zone beside them, under a predicate's spec; that is a value's shape, not an instant's,
and stays where its spec lives.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from leaveimpact.core.jsonshape import (
    JsonObject,
    as_object,
    expect_fields,
    optional_string_field,
    string_field,
)
from leaveimpact.core.worldtime import DateSpan, date_at, instant_at


def encode_date(day: date) -> str:
    """``day`` in the one canonical spelling.

    >>> encode_date(date(2026, 9, 14))
    '2026-09-14'
    """
    return day.isoformat()


def decode_date(text: str, what: str) -> date:
    """The day ``text`` spells canonically; ``ValueError`` names ``what`` otherwise."""
    return date_at(text, what)


def encode_optional_date(day: date | None) -> str | None:
    """``day`` spelled, or ``null`` for an absent date (a ticket not yet resolved)."""
    return None if day is None else encode_date(day)


def decode_optional_date(data: Mapping[str, object], key: str) -> date | None:
    """The optional date at ``key``: ``None`` when the field is ``null``."""
    text = optional_string_field(data, key)
    return None if text is None else decode_date(text, key)


def encode_instant(instant: datetime) -> JsonObject:
    """An aware instant with its IANA zone beside the offset-bearing timestamp, when it has one.

    >>> from zoneinfo import ZoneInfo
    >>> encode_instant(datetime(2026, 9, 14, 9, 0, tzinfo=ZoneInfo("Europe/Istanbul")))
    {'at': '2026-09-14T09:00:00+03:00', 'timezone': 'Europe/Istanbul'}
    """
    return {"at": instant.isoformat(), "timezone": getattr(instant.tzinfo, "key", None)}


def decode_instant(value: object, what: str) -> datetime:
    """The instant ``value`` encodes, in its zone when it names one (``instant_at``'s rule)."""
    data = as_object(value, what)
    expect_fields(data, ("at", "timezone"), what)
    return instant_at(string_field(data, "at"), optional_string_field(data, "timezone"), what)


def encode_date_span(span: DateSpan) -> JsonObject:
    """A span of days as its two inclusive ends.

    >>> encode_date_span(DateSpan(date(2026, 9, 10), date(2026, 9, 12)))
    {'start': '2026-09-10', 'end': '2026-09-12'}
    """
    return {"start": encode_date(span.start), "end": encode_date(span.end)}


def decode_date_span(value: object, what: str) -> DateSpan:
    """The span ``value`` encodes; a reversed pair fails in the constructor, naming nothing else."""
    data = as_object(value, what)
    expect_fields(data, ("start", "end"), what)
    return DateSpan(
        decode_date(string_field(data, "start"), "a date"),
        decode_date(string_field(data, "end"), "a date"),
    )
