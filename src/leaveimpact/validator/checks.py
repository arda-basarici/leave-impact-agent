"""The validator's three checks as pure comparisons: identities, records, the view of a run.

Each check is a function over plain values — identity sets, records by id, derived facts —
so it is proven against data and never against a system; the composition root reads the
live systems and feeds these (the three-layer ruling at the validator step). They are
layered because each depends on the one before it. *Identity exactness*: per closed
enumeration, the observed identity set equals the planted one, missing and foreign both
named, since a missing record is a projection that did not land and a foreign one is
contamination the investigator would read as world. *Record fidelity*: each observed
record equals its planted record field for field — plain equality, because the adapters'
round trips are proven exact for every generator-controlled field, so a looser equivalence
would name a looseness the record says does not exist. *View agreement*: the facts a run
of a scenario derives from what the readers return, read the way the investigator reads
(leaves and events by the scenario's window, the rest by enumeration), equal the facts the
plantings yield under the same runtime rule; this is the layer that exercises an adapter's
window query and its timezone handling, which equality of records cannot.

Both sides of the view obey the runtime rule and nothing else (the runtime-view ruling at
the validator step): a read returns what the system holds, and every returned record is
observable on the run's day. The plantings' dates are benchmark-private and never enter
here — a first cut stamped live records with them by identity and so produced a dated
history the investigator cannot obtain, hiding what the runtime would see; ``world``
states the runtime record set once and the expected side is built from it, so the
validator and the pre-seal realizability proof agree on what a run sees by construction.
Under that rule the observable facts do not depend on the instant inside the stable
interval, so the two-instant check of the earlier design proved nothing a single read
does not, and the view is taken once per scenario at its ``now``; the interval remains
the evaluator's, a run anywhere in it grading against one key, proven before sealing.

The layers are ordered because a foreign record has no planting to compare against: the
view runs only over a kind whose identities were exact, and a kind that failed exactness
has its view recorded as not run, never silently skipped.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from datetime import date
from enum import StrEnum

from leaveimpact.core.derivation import Derived, derive
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.worldtime import DateSpan, InstantSpan
from leaveimpact.world.artifacts import PlantedWorldSpec
from leaveimpact.world.runtime_view import runtime_facts, runtime_records, window_instants
from leaveimpact.world.scenario import ScenarioSpec
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


def world_horizon(specs: Iterable[ScenarioSpec]) -> tuple[DateSpan, InstantSpan]:
    """The bound of what any run can observe: every window's union, as days and as instants.

    The scope of exactness for the windowed kinds. One bounding interval rather than the
    exact union, so a foreign record in a gap between windows is inside the horizon and
    fails exactness rather than hiding in the gap. Each window contributes its instants in
    its own reference zone, since the scenarios need not share one.
    """
    rows = list(specs)
    if not rows:
        raise ValueError("the horizon of no scenarios is undefined")
    days = DateSpan(min(s.window.start for s in rows), max(s.window.end for s in rows))
    spans = [window_instants(s.window, s.reference_timezone) for s in rows]
    return days, InstantSpan(min(span.start for span in spans), max(span.end for span in spans))


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
    """The facts a run's reads yield against those the plantings yield; both differences."""

    scenario_id: str
    run_day: date
    missing: tuple[Derived, ...]
    surplus: tuple[Derived, ...]


def derive_live[T: Entity](records: Iterable[Observed[T]], run_day: date) -> tuple[Derived, ...]:
    """The facts and gaps of live ``records`` of one kind, every one observable on ``run_day``.

    One kind per call, as the readers return them; the caller concatenates. The date is
    the run's and nothing else, the runtime rule for a live harness.
    """
    return tuple(item for record in records for item in derive(record, run_day))


def expected_view(planted: PlantedWorldSpec, spec: ScenarioSpec) -> frozenset[Derived]:
    """What a run of ``spec`` should derive from a faithful projection of ``planted``.

    The runtime record set ``world`` states, dated to the scenario's ``today``: what the
    pre-seal realizability proof verified the key under, and so what the live reads must
    reproduce.
    """
    owned = [row.owned for row in planted.scenarios]
    base = runtime_facts(runtime_records(planted.org, owned, spec), spec.today)
    return frozenset([*base.facts, *base.gaps])


def compare_views(
    scenario_id: str,
    run_day: date,
    expected: frozenset[Derived],
    live: frozenset[Derived],
) -> ViewDisagreement | None:
    """``None`` when the two views agree; otherwise both differences, in a stable order."""
    if expected == live:
        return None
    return ViewDisagreement(
        scenario_id,
        run_day,
        missing=tuple(sorted(expected - live, key=repr)),
        surplus=tuple(sorted(live - expected, key=repr)),
    )
