"""World time: the run's ``now``, and the two interval conventions every date in the world obeys.

Time is world state, never the machine's clock (DESIGN, "Time is world state"). A run
receives a ``RunContext`` — which scenario, which world version, which leave is under
investigation, and ``now`` as an aware instant with the timezone a human reading it
would use — and that is the reproducibility boundary: same context gives the same
evidence on any machine, months later. Nothing in ``core`` reads a clock; the
composition root reads it once and builds a context, and the import law checks that
by scanning for clock reads.

Two interval conventions are stated here once and used everywhere. Calendar-day facts
(a leave, a ticket's dates, a scenario's slice) are inclusive at both ends, the way a
human reads "10 to 12 September". Instants (a meeting) are half-open, ``[start,
end)``, so back-to-back meetings never overlap. Instants are stored as given, zone and
all, because the zone is provenance for how a human read the time — which is what a
timezone-boundary distractor turns on (an event late on one calendar day in London
falls on the next in Istanbul). Ordering and duration are computed in UTC, never on
the stored values: Python compares and subtracts two datetimes that share a tzinfo
object by wall clock, ignoring offset and fold, and ``ZoneInfo`` caches instances, so
two London meetings across a DST change would otherwise misorder or misreport an hour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion
from leaveimpact.core.refs import require_id


def require_aware(instant: datetime, what: str) -> datetime:
    """``instant`` itself, or a ``ValueError`` naming ``what`` if it carries no timezone.

    A naive datetime has no place in the world: it is a programming error at the
    boundary that built it, so it fails here, named, rather than comparing wrongly later.

    >>> from datetime import UTC
    >>> require_aware(datetime(2026, 9, 14, 9, 0, tzinfo=UTC), "now").isoformat()
    '2026-09-14T09:00:00+00:00'
    >>> require_aware(datetime(2026, 9, 14, 9, 0), "now")
    Traceback (most recent call last):
    ...
    ValueError: now must be timezone-aware, got naive 2026-09-14 09:00:00
    """
    if instant.tzinfo is None or instant.tzinfo.utcoffset(instant) is None:
        raise ValueError(f"{what} must be timezone-aware, got naive {instant}")
    return instant


def as_utc(instant: datetime, what: str = "instant") -> datetime:
    """``instant`` on the UTC clock — the form every ordering and duration is computed in.

    A fall-back hour is two instants with one wall-clock reading; ``fold`` tells them
    apart, and the conversion honours it.

    >>> from zoneinfo import ZoneInfo
    >>> london = ZoneInfo("Europe/London")
    >>> as_utc(datetime(2026, 10, 25, 1, 30, tzinfo=london, fold=0)).isoformat()
    '2026-10-25T00:30:00+00:00'
    >>> as_utc(datetime(2026, 10, 25, 1, 30, tzinfo=london, fold=1)).isoformat()
    '2026-10-25T01:30:00+00:00'
    """
    return require_aware(instant, what).astimezone(UTC)


def zone(key: str) -> ZoneInfo:
    """The IANA zone for ``key``, or a ``ValueError`` naming the key that is not one."""
    try:
        return ZoneInfo(key)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"not an IANA timezone key: {key!r}") from error


def instant_at(text: str, zone_key: str | None, what: str) -> datetime:
    """The aware instant ``text`` reads as, in the zone ``zone_key`` names when it names one.

    The one rule for every codec that stores an instant as an offset-bearing timestamp
    with its IANA zone beside it. The offset must be the zone's own at that instant: a
    pair that disagrees was not written by an encoder of this project, and decoding it
    by conversion would produce a value whose re-encoding differs from the bytes read,
    so it is refused rather than normalized. A naive timestamp and an unknown zone key
    are refused naming ``what``; without a zone the instant keeps its bare offset.

    >>> instant_at("2026-10-25T01:30:00+00:00", "Europe/London", "start").fold
    1
    >>> instant_at("2026-01-05T09:00:00+00:00", "UTC", "now").isoformat()
    '2026-01-05T09:00:00+00:00'
    >>> instant_at("2026-01-05T09:00:00+03:00", "UTC", "now")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    ValueError: now reads '2026-01-05T09:00:00+03:00', which UTC writes as '2026-01-05T06:...'
    >>> instant_at("2026-01-05T09:00:00", None, "now")
    Traceback (most recent call last):
    ...
    ValueError: now carries its offset, got '2026-01-05T09:00:00'
    """
    instant = datetime.fromisoformat(text)
    if instant.tzinfo is None:
        raise ValueError(f"{what} carries its offset, got {text!r}")
    if zone_key is None:
        return instant
    in_zone = instant.astimezone(zone(zone_key))
    if in_zone.utcoffset() != instant.utcoffset():
        raise ValueError(
            f"{what} reads {text!r}, which {zone_key} writes as {in_zone.isoformat()!r}"
        )
    return in_zone


def local_date(instant: datetime, timezone: str) -> date:
    """The calendar day on which a human in ``timezone`` reads ``instant``.

    >>> from datetime import UTC
    >>> local_date(datetime(2026, 9, 14, 22, 30, tzinfo=UTC), "Europe/Istanbul")
    datetime.date(2026, 9, 15)
    """
    return require_aware(instant, "instant").astimezone(zone(timezone)).date()


@dataclass(frozen=True, slots=True)
class DateSpan:
    """A run of calendar days, inclusive at both ends — a leave, a slice, a ticket's life.

    >>> span = DateSpan(date(2026, 9, 10), date(2026, 9, 12))
    >>> span.contains(date(2026, 9, 12)), span.contains(date(2026, 9, 13))
    (True, False)
    >>> span.days
    3
    """

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(
                f"a date span ends on or after it starts, got {self.start}..{self.end}"
            )

    @property
    def days(self) -> int:
        """How many calendar days the span covers, both ends counted."""
        return (self.end - self.start).days + 1

    def contains(self, day: date) -> bool:
        """Whether ``day`` falls inside the span, ends included."""
        return self.start <= day <= self.end

    def overlaps(self, other: DateSpan) -> bool:
        """Whether the two spans share at least one day.

        >>> a = DateSpan(date(2026, 9, 10), date(2026, 9, 12))
        >>> a.overlaps(DateSpan(date(2026, 9, 12), date(2026, 9, 14)))
        True
        >>> a.overlaps(DateSpan(date(2026, 9, 13), date(2026, 9, 14)))
        False
        """
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True, slots=True)
class InstantSpan:
    """A half-open run of time, ``[start, end)`` — a meeting; both ends aware.

    >>> from datetime import UTC
    >>> span = InstantSpan(
    ...     datetime(2026, 9, 14, 9, 0, tzinfo=UTC), datetime(2026, 9, 14, 10, 0, tzinfo=UTC)
    ... )
    >>> span.contains(datetime(2026, 9, 14, 10, 0, tzinfo=UTC))
    False
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if as_utc(self.end, "span end") <= as_utc(self.start, "span start"):
            raise ValueError(f"an instant span ends after it starts, got {self.start}..{self.end}")

    @property
    def duration(self) -> timedelta:
        """Elapsed time, not wall-clock difference: one hour across a spring-forward is one hour."""
        return as_utc(self.end) - as_utc(self.start)

    def contains(self, instant: datetime) -> bool:
        """Whether ``instant`` falls inside the span; the end instant does not."""
        return as_utc(self.start) <= as_utc(instant) < as_utc(self.end)

    def overlaps(self, other: InstantSpan) -> bool:
        """Whether the two spans share any time; touching at an end is not overlap."""
        return as_utc(self.start) < as_utc(other.end) and as_utc(other.start) < as_utc(self.end)

    def local_dates(self, timezone: str) -> DateSpan:
        """The calendar days a human in ``timezone`` sees the span on.

        The last instant inside the span is just before ``end``, so a span ending exactly
        at midnight stays on the earlier day.

        >>> from datetime import UTC
        >>> span = InstantSpan(
        ...     datetime(2026, 9, 14, 22, 0, tzinfo=UTC), datetime(2026, 9, 14, 23, 0, tzinfo=UTC)
        ... )
        >>> span.local_dates("Europe/London")
        DateSpan(start=datetime.date(2026, 9, 14), end=datetime.date(2026, 9, 14))
        >>> span.local_dates("Europe/Istanbul")
        DateSpan(start=datetime.date(2026, 9, 15), end=datetime.date(2026, 9, 15))
        """
        last_inside = as_utc(self.end) - timedelta(microseconds=1)
        return DateSpan(local_date(self.start, timezone), local_date(last_inside, timezone))


@dataclass(frozen=True, slots=True)
class RunContext:
    """What a run is: the scenario, the world version, the leave under investigation, and ``now``.

    The reproducibility boundary: same scenario, same world version, same leave, same
    ``now`` gives the same evidence on any machine. ``now`` is an aware instant;
    ``reference_timezone`` is the IANA zone a human reads it in — the organization's,
    unless a scenario says otherwise — and ``today`` is the calendar day that reading
    gives. Run provenance (which harness commit, which model, which truth digest) is a
    separate record the evaluator milestone owns; this context holds only what changes
    the evidence.

    ``leave_id`` is an identifier and nothing more: run inputs identify what to
    investigate, and ports establish the facts about it. The leave record, its
    employee and its span are read through the people port, so they are evidence the
    run established and a scenario can contradict, never a truth the harness told it.
    The investigator may not learn the leave from ``world``, which is why it travels
    here (ruled at step 5 of the world milestone's build).

    >>> from datetime import UTC
    >>> from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion
    >>> context = RunContext(
    ...     ScenarioId("scenario_003"),
    ...     WorldVersion("4f2c"),
    ...     LeaveId("leave_005"),
    ...     datetime(2026, 9, 14, 22, 30, tzinfo=UTC),
    ...     "Europe/Istanbul",
    ... )
    >>> context.today
    datetime.date(2026, 9, 15)
    """

    scenario_id: ScenarioId
    world_version: WorldVersion
    leave_id: LeaveId
    now: datetime
    reference_timezone: str

    def __post_init__(self) -> None:
        require_id(EntityKind.LEAVE, self.leave_id)
        require_aware(self.now, "now")
        zone(self.reference_timezone)

    @property
    def today(self) -> date:
        """The calendar day ``now`` falls on in the reference timezone."""
        return local_date(self.now, self.reference_timezone)
