"""Incidents: the scenarios on which some run met a source that contradicted itself, and
the attempts that ran on more than one harness commit.

Two complete reads of one structured source that cannot both be true end an attempt by
defect (``core.contradictions``). The run that met it is one run of one system, and the
fault is not that system's: it is evidence about the world or the execution, and a system
that reads more is the one likelier to find it. So the incident is reported for the whole
measurement, by scenario, and not left as one arm's failed run (the contract step's ruling
on a source that contradicts itself).

Per scenario with at least one contradiction: the shapes found, each a source and the way
its reads disagree, and for every arm the attempts on that scenario that met a
contradiction, the ones that did not, and how many counted runs the arm rests on there. An
incident at a scenario is no statement that every arm observed it, which is why the arms
are listed apart.

Every trace of the world is read, and not only the ones in the tables. An export that is
out of them, for its settings, for another registration or for a dirty tree, was still a
run against this world, and a contradiction its reads met touches every arm that rests on
the scenario. Such an export is in no arm, so it is named by its key in the store, under
``outside``; its shapes join the incident's, and a scenario only it met is an incident
all the same.

Nothing is excluded here or because of this. Every attempt is read, counted or not, an
attempt no scenario of the world could place included, and no run and no scenario leaves a
table: a set is invalid because a stated condition of the measurement was breached, never
because of what was found, and the repair for a compromised world is a rerun under an
amended registration, a person's decision this section exists to inform.

The contradictions are recomputed from each trace when the run is evaluated and are not
read from a failure's reason, so a run that met one and did not fail shows here too.

*A provenance incident* is another kind and is kept apart. An attempt whose segments ran
on more than one harness commit is one export of two programs (the contract step's ruling
on segments and commits: a finding and an incident, the run not silently removed). It is
about that attempt and nothing else: no source and no scenario is implicated, no other run
is touched, and so it sets no scenario flag and enters no comparison's count. It is listed
once per attempt, with the identity its export carries and the commits, read from every
evaluated export of the world like a contradiction and for the same reason: what removes a
run from the tables, a dirty tree or differing settings as much as the two commits, must
not also remove it from the report of what went wrong.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from leaveimpact.core.contradictions import ContradictionKind
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.refs import SOURCE_BY_TARGET_KIND
from leaveimpact.evaluator.cells import Arm
from leaveimpact.evaluator.trace_metrics import Evaluation


@dataclass(frozen=True, slots=True)
class Shape:
    """One way a source contradicted itself: the source, and how its reads disagree."""

    source: Source
    kind: ContradictionKind


@dataclass(frozen=True, slots=True)
class RunRef:
    """One attempt of one run, by the identity its export carries."""

    run_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class IncidentArm:
    """One arm at an incident's scenario: the attempts there that met a contradiction, the
    ones that did not, and how many counted runs the arm's estimates rest on there."""

    arm: str
    met: tuple[RunRef, ...]
    not_met: tuple[RunRef, ...]
    counted: int


@dataclass(frozen=True, slots=True)
class Incident:
    """A scenario on which at least one attempt met a contradiction: the shapes found, in
    source and kind order, every arm, in the arms' order, and the exports outside the
    tables that met one there, by their keys in the store, in key order."""

    scenario_id: ScenarioId
    shapes: tuple[Shape, ...]
    arms: tuple[IncidentArm, ...]
    outside: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProvenanceIncident:
    """One attempt whose segments ran on more than one harness commit: the scenario and the
    identity its export carries, its key in the store when the export is out of the tables
    (``None`` for one in them, which an arm holds), and the commits in the order the
    segments first ran on them."""

    scenario_id: ScenarioId
    run_id: str
    attempt: int
    outside: str | None
    commits: tuple[str, ...]


def provenance_incidents_of(
    arms: Sequence[Arm], outside: Sequence[tuple[str, Evaluation]] = ()
) -> tuple[ProvenanceIncident, ...]:
    """The attempts among those ``arms`` hold and the evaluated exports ``outside`` the
    tables that ran on more than one harness commit, in scenario, run and attempt order;
    empty when every attempt ran on one."""
    held: list[tuple[str | None, Evaluation]] = [
        (None, attempt)
        for arm in arms
        for attempts in _attempts_by_scenario(arm).values()
        for attempt in attempts
    ]
    found = [
        ProvenanceIncident(
            evaluation.outcome.header.scenario_id,
            evaluation.outcome.header.run_id,
            evaluation.outcome.header.attempt,
            key,
            evaluation.metrics.ending.commits,
        )
        for key, evaluation in (*held, *outside)
        if len(evaluation.metrics.ending.commits) > 1
    ]
    return tuple(
        sorted(
            found,
            key=lambda each: (each.scenario_id, each.run_id, each.attempt, each.outside or ""),
        )
    )


def incidents_of(
    arms: Sequence[Arm], outside: Sequence[tuple[str, Evaluation]] = ()
) -> tuple[Incident, ...]:
    """The incidents among the attempts ``arms`` hold and the evaluated exports ``outside``
    the tables, each with its key in the store, in scenario id order; empty when no read
    contradicted another."""
    by_arm = [(arm, _attempts_by_scenario(arm)) for arm in arms]
    met_outside: dict[ScenarioId, list[tuple[str, Evaluation]]] = {}
    for key, evaluation in outside:
        if evaluation.contradictions:
            scenario = evaluation.outcome.header.scenario_id
            met_outside.setdefault(scenario, []).append((key, evaluation))
    touched = sorted(
        {
            scenario
            for _, held in by_arm
            for scenario, attempts in held.items()
            if any(attempt.contradictions for attempt in attempts)
        }
        | set(met_outside)
    )
    found: list[Incident] = []
    for scenario in touched:
        elsewhere = met_outside.get(scenario, [])
        shapes = {
            Shape(SOURCE_BY_TARGET_KIND[contradiction.record.kind], contradiction.kind)
            for attempt in (
                *(each for _, held in by_arm for each in held.get(scenario, ())),
                *(evaluation for _, evaluation in elsewhere),
            )
            for contradiction in attempt.contradictions
        }
        found.append(
            Incident(
                scenario,
                tuple(sorted(shapes, key=lambda shape: (shape.source.value, shape.kind.value))),
                tuple(_at(arm, scenario, held.get(scenario, ())) for arm, held in by_arm),
                tuple(sorted(key for key, _ in elsewhere)),
            )
        )
    return tuple(found)


def incident_scenarios(incidents: Sequence[Incident]) -> frozenset[ScenarioId]:
    """The scenarios that carry an incident."""
    return frozenset(incident.scenario_id for incident in incidents)


def _attempts_by_scenario(arm: Arm) -> dict[ScenarioId, tuple[Evaluation, ...]]:
    """Every attempt ``arm`` holds by the scenario its export names, placed or not."""
    held: dict[ScenarioId, list[Evaluation]] = {
        runs.scenario_id: list(runs.attempts) for runs in arm.scenarios
    }
    for attempt in arm.unplaced:
        held.setdefault(attempt.outcome.header.scenario_id, []).append(attempt)
    return {scenario: tuple(attempts) for scenario, attempts in held.items()}


def _at(arm: Arm, scenario: ScenarioId, attempts: Sequence[Evaluation]) -> IncidentArm:
    refs = [
        (RunRef(attempt.outcome.header.run_id, attempt.outcome.header.attempt), attempt)
        for attempt in attempts
    ]
    counted = sum(len(runs.counted) for runs in arm.scenarios if runs.scenario_id == scenario)
    return IncidentArm(
        arm.name,
        tuple(ref for ref, attempt in refs if attempt.contradictions),
        tuple(ref for ref, attempt in refs if not attempt.contradictions),
        counted,
    )


__all__ = [
    "Incident",
    "IncidentArm",
    "ProvenanceIncident",
    "RunRef",
    "Shape",
    "incident_scenarios",
    "incidents_of",
    "provenance_incidents_of",
]
