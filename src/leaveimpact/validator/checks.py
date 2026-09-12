"""The validator's three checks as pure comparisons: identities, records, the view at an instant.

Each check is a function over plain values — identity sets, records by id, derived facts —
so it is proven against data and never against a system; the composition root reads the
live systems and feeds these (the three-layer ruling at the validator step). They are
layered because each depends on the one before it. *Identity exactness*: per closed
enumeration, the observed identity set equals the planted one, missing and foreign both
named, since a missing record is a projection that did not land and a foreign one is
contamination the investigator would read as world. *Record fidelity*: each observed
record equals its planted record field for field — plain equality, because the adapters'
round trips are proven exact for every generator-controlled field, so a looser equivalence
would name a looseness the record says does not exist. *View agreement*: at an instant,
the facts a run could observe, derived through ``core``'s one derivation from what the
readers return the way the investigator reads (leaves and events by window, the rest by
enumeration), equal the facts derived from the plantings under the same window rule; this
is the layer that exercises an adapter's window query and its timezone handling, which
equality of records cannot.

A live record knows nothing of when the world made it observable — the entity types keep
vendor timestamps out — so its facts are stamped with the planting's date, found by
identity. That is why the layers are ordered: stamping a foreign record would invent a
date, so the view runs only over a kind whose identities were exact, and a kind that
failed exactness has its view recorded as not run, never silently skipped.

The instants are the two ends of a scenario's stable interval, at the wall-clock time of
the scenario's ``now`` in its reference zone rather than midnight, because a boundary
fact shows at an end first and the interval is stored as dates. Every planting's date
bounds the interval by construction, so the observable facts are the same at both ends;
the two views agreeing with each other is that property proven from the live side.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta
from enum import StrEnum

from leaveimpact.core.derivation import Derived, derive
from leaveimpact.core.entities import CalendarEvent, Leave
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.worldtime import DateSpan, InstantSpan, local_date, zone
from leaveimpact.world.artifacts import ScenarioPlanting
from leaveimpact.world.scenario import OwnedEntities, Planted, ScenarioSpec
from leaveimpact.world.truth_facts import observed


class CheckStatus(StrEnum):
    """What a check concluded; ``NOT_RUN`` carries its reason and never counts as passed."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


# --- Identity exactness -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityExactness:
    """One kind's enumeration compared: what the plantings expect against what was observed.

    ``missing`` are planted identities the system did not return, ``foreign`` identities it
    returned that no planting made; both sorted, so a verdict reads the same twice.
    """

    kind: EntityKind
    missing: tuple[str, ...]
    foreign: tuple[str, ...]

    @property
    def status(self) -> CheckStatus:
        return CheckStatus.PASSED if not (self.missing or self.foreign) else CheckStatus.FAILED


def compare_identities(
    kind: EntityKind, expected: Iterable[str], observed_ids: Iterable[str]
) -> IdentityExactness:
    """Both directions of the set difference, reported whole rather than at the first miss.

    >>> check = compare_identities(EntityKind.LEAVE, ["leave_001", "leave_002"], ["leave_002"])
    >>> check.missing, check.foreign, check.status.value
    (('leave_001',), (), 'failed')
    """
    planted, seen = frozenset(expected), frozenset(observed_ids)
    return IdentityExactness(kind, tuple(sorted(planted - seen)), tuple(sorted(seen - planted)))


# --- Record fidelity ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecordMismatch:
    """A record the system holds under a planted identity with other content; the fields named."""

    ref: EntityRef
    differing_fields: tuple[str, ...]


def compare_records[K: str, T: Entity](
    expected: Mapping[K, T], observed_records: Mapping[K, T]
) -> tuple[RecordMismatch, ...]:
    """Every identity present on both sides whose records differ, with the differing fields.

    Identities on one side only are exactness findings and are not repeated here; the
    comparison is plain equality per field, the adapters' proven round trip being the
    reason no looser rule is named.
    """
    mismatches: list[RecordMismatch] = []
    for id in sorted(expected.keys() & observed_records.keys()):
        planted, seen = expected[id], observed_records[id]
        differing = tuple(
            item.name
            for item in fields(planted)
            if getattr(planted, item.name) != getattr(seen, item.name)
        )
        if differing:
            mismatches.append(RecordMismatch(observed(planted).ref, differing))
    return tuple(mismatches)


# --- View agreement -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ViewDisagreement:
    """The facts a live read yields at an instant against those the plantings yield; both gaps."""

    scenario_id: str
    instant: datetime
    missing: tuple[Derived, ...]
    surplus: tuple[Derived, ...]


def boundary_instants(planting: ScenarioPlanting, spec: ScenarioSpec) -> tuple[datetime, datetime]:
    """The two ends of the stable interval at ``now``'s wall-clock time in the reference zone."""
    at = spec.now.astimezone(zone(spec.reference_timezone)).timetz()
    interval = planting.stable_interval
    return (
        datetime.combine(interval.start, at),
        datetime.combine(interval.end, at),
    )


def window_instants(window: DateSpan, reference_timezone: str) -> InstantSpan:
    """``window`` as the half-open run of instants it covers in ``reference_timezone``.

    The events an investigator reads for a window are those overlapping the days of the
    window as a human in the reference zone reads them: from the first day's midnight to
    the midnight after the last day.
    """
    tz = zone(reference_timezone)
    return InstantSpan(
        datetime.combine(window.start, datetime.min.time(), tzinfo=tz),
        datetime.combine(window.end + timedelta(days=1), datetime.min.time(), tzinfo=tz),
    )


def world_horizon(specs: Iterable[ScenarioSpec]) -> tuple[DateSpan, InstantSpan]:
    """The bound of what any run can observe: every window's union, as days and as instants.

    One bounding interval rather than the exact union, so a foreign record in a gap
    between windows is inside the horizon and fails exactness rather than hiding in the
    gap. Each window contributes its instants in its own reference zone, since the
    scenarios need not share one.
    """
    rows = list(specs)
    if not rows:
        raise ValueError("the horizon of no scenarios is undefined")
    days = DateSpan(min(s.window.start for s in rows), max(s.window.end for s in rows))
    spans = [window_instants(s.window, s.reference_timezone) for s in rows]
    return days, InstantSpan(min(span.start for span in spans), max(span.end for span in spans))


def leaves_overlapping(
    plantings: Iterable[Planted[Leave]], span: DateSpan
) -> tuple[Planted[Leave], ...]:
    """The planted leaves a ``leaves_within(span)`` read is expected to return: the port's rule."""
    return tuple(
        planted
        for planted in plantings
        if DateSpan(planted.entity.start, planted.entity.end).overlaps(span)
    )


def events_overlapping(
    plantings: Iterable[Planted[CalendarEvent]], span: InstantSpan
) -> tuple[Planted[CalendarEvent], ...]:
    """The planted events an ``events_within(span)`` read is expected to return: the port's rule."""
    return tuple(
        planted
        for planted in plantings
        if InstantSpan(planted.entity.start, planted.entity.end).overlaps(span)
    )


def observable_dates(
    org_refs: Iterable[EntityRef], world_start: date, owned: Iterable[OwnedEntities]
) -> dict[EntityRef, date]:
    """When the world made each record observable, by reference: the stamp a live record borrows.

    The organization's static records from the world's start, each owned record from the
    day it was planted — the same dates the truth base derives against.
    """
    dates = dict.fromkeys(org_refs, world_start)
    for entities in owned:
        for group in (entities.leaves, entities.work_items, entities.events, entities.documents):
            for planted in group:
                dates[observed(planted.entity).ref] = planted.observable_from
    return dates


def derive_stamped[T: Entity](
    records: Iterable[Observed[T]], dates: Mapping[EntityRef, date]
) -> tuple[Derived, ...]:
    """The facts and gaps of live ``records`` of one kind, each dated as the world planted it.

    One kind per call, as the readers return them; the caller concatenates. A record with
    no planting date is a foreign one exactness should have refused; it is a
    ``LookupError`` here rather than a guessed date.
    """
    derived: list[Derived] = []
    for record in records:
        if record.ref not in dates:
            raise LookupError(f"{record.ref.id} has no planting to date its facts from")
        derived.extend(derive(record, dates[record.ref]))
    return tuple(derived)


def view_at(
    derived: Iterable[Derived], instant: datetime, reference_timezone: str
) -> frozenset[Derived]:
    """What a run at ``instant`` could observe: every fact and gap dated on or before its day."""
    today = local_date(instant, reference_timezone)
    return frozenset(item for item in derived if item.observable_from <= today)


def compare_views(
    scenario_id: str,
    instant: datetime,
    expected: frozenset[Derived],
    live: frozenset[Derived],
) -> ViewDisagreement | None:
    """``None`` when the two views agree; otherwise both differences, in a stable order."""
    if expected == live:
        return None
    return ViewDisagreement(
        scenario_id,
        instant,
        missing=tuple(sorted(expected - live, key=repr)),
        surplus=tuple(sorted(live - expected, key=repr)),
    )
