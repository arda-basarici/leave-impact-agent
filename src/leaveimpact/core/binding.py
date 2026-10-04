"""The span binding: which artifact a stated requirement applies to, from the words that name it.

A clause says what covering something requires and names that thing by its title, in
prose. A model states the requirement and quotes the title as the *target span*; it gives
no id. This module turns the span into an artifact, once, at composition, over everything
the run had read by then (the contract step's first ruling).

The rule is exact string equality between the span and the titles of the distinct tickets,
meetings and documents the run read. Equal to one title, the span is *placed* on that
artifact; to none, *unplaced*; to several, *ambiguous*. Nothing is searched for inside the
clause's text: where a title ends is not in the text, it is known only from a record that
holds the title, and a resolver that looks for read titles in the text binds a qualified
title the run never read to the plain one it did.

One guard sits on top, and it is conservative. When a longer read title contains the span
and that longer title stands in the carrier's text, the span may be the longer title cut
short, so the result is ambiguous and nothing is bound. The guard catches a shortened span
whenever the longer title was read. Its cost is stated: it also blocks a rightful
short-title reference in a passage that mentions the longer title on its own.

What it cannot catch stays the model's error. A shortened span whose longer title the run
never read is equal to the plain title and binds the plain-titled artifact. That is a wrong
binding, graded as the model's; equality establishes where a scope came from, never that it
is the right one. And a span that runs a word past its title equals nothing and is
unplaced even when its target was read: the diagnostic shows the loss and does not restore
the constraint.

A span bound to a document says nothing here about which of the document's sections a
constraint applies to; that step is the composer's.
"""

from __future__ import annotations

from collections.abc import Iterable

from leaveimpact.core.entities import CalendarEvent, Document, WorkItem
from leaveimpact.core.read_projection import StructuredReads
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.stated import PlacementState, SpanPlacement

Titled = tuple[EntityRef, str]
"""A read artifact that prose can name, with the title it is named by."""


def titled_artifacts(reads: StructuredReads) -> tuple[Titled, ...]:
    """The distinct tickets, meetings and documents ``reads`` returned and can be concluded
    from, each with its title, in the order first returned.

    An artifact read twice is one artifact. A record the run's own reads returned two ways
    is left out, as it is from every other conclusion: nothing says which title is its.
    """
    return tuple(
        (record.ref, record.value.title)
        for record in reads.returned
        if isinstance(record.value, WorkItem | CalendarEvent | Document)
        and record.ref not in reads.reads.unobserved
    )


def bind_span(span: str, carrier_text: str, titled: Iterable[Titled]) -> SpanPlacement:
    """Where ``span`` binds among ``titled``, the span being quoted from ``carrier_text``.

    >>> from leaveimpact.core.ids import work_item_id
    >>> from leaveimpact.core.refs import work_item_ref
    >>> plain = (work_item_ref(work_item_id(1)), "Auth: rotate the keys")
    >>> regional = (work_item_ref(work_item_id(2)), "Auth: rotate the keys for the EU region")
    >>> text = "The Auth: rotate the keys for the EU region release needs a Go engineer."
    >>> bind_span("Auth: rotate the keys for the EU region", text, (plain, regional)).artifact.id
    'ticket_002'
    >>> bind_span("Auth: rotate the keys", text, (plain, regional)).state
    <PlacementState.AMBIGUOUS: 'ambiguous'>
    >>> bind_span("Auth: rotate the keys", text, (plain,)).artifact.id
    'ticket_001'
    """
    if not span:
        raise ValueError("a target span is not empty")
    distinct: dict[EntityRef, str] = {}
    for artifact, title in titled:
        if distinct.setdefault(artifact, title) != title:
            # The caller's error: ``titled_artifacts`` leaves out a record returned two ways.
            raise ValueError(f"{artifact.id} is given two titles; one artifact has one title")
    longer = [
        artifact
        for artifact, title in distinct.items()
        if title != span and span in title and title in carrier_text
    ]
    if longer:
        return SpanPlacement(PlacementState.AMBIGUOUS, among=_ordered(longer))
    equal = [artifact for artifact, title in distinct.items() if title == span]
    if not equal:
        return SpanPlacement(PlacementState.UNPLACED)
    if len(equal) > 1:
        return SpanPlacement(PlacementState.AMBIGUOUS, among=_ordered(equal))
    return SpanPlacement(PlacementState.PLACED, artifact=equal[0])


def _ordered(artifacts: Iterable[EntityRef]) -> tuple[EntityRef, ...]:
    return tuple(sorted(artifacts, key=lambda artifact: (artifact.kind.value, artifact.id)))


__all__ = ["Titled", "bind_span", "titled_artifacts"]
