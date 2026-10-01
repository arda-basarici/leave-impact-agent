"""Grading one run: an export and the sealed world in, exactly one outcome out.

Every export that decodes gets an outcome, and nothing a run did raises here (the edges
ruling of the investigator milestone's third build step). What raises is a fault of the
sealed files or of the evaluator itself, which world loading and the oracle refuse before
a run is looked at. The outcome is one of three:

- *Graded.* The run completed or reported at its cap, and the oracle has an answer for the
  condition it ran under. It holds the claim rows, the plan checks' findings and the
  coverage gaps. A report
  with no claim is graded like any other, every required key a missed row; a
  structurally invalid claim set is graded too, with zero credit, its rows not matched
  and the plan checks marked not evaluated, since their precondition failed.
- *Limited.* The oracle has no claim-level answer: the investigated leave was unreadable
  under the run's condition, or what clauses require was, or one source both answered and
  failed in the run, a mixed condition no registered outage produces. No comparative
  answer metric is computed. Every check that needs no expected answer still is: the
  structural check and the report's own coherence here, and grounding, citations and
  source discipline when the next build step adds them.
- *Excluded.* The run failed by a defect or by infrastructure and is counted, not graded
  (the runtime-policy ruling); or its context is not the one the sealed scenario gives, a
  harness defect, since a run of another scenario, world or ``now`` cannot be graded
  against this key.

The condition is read off the trace, never taken from the record (``condition``). When the
record's stored condition disagrees with the trace, the trace stands and the disagreement
is a harness finding carried on the outcome. A condition no outage registered (two sources
down for the whole run, say) is graded mechanically like any other; whether it enters a
reported comparison is the reporting step's.

Order matters and is fixed: the context, then the terminal status, then the condition,
then the oracle. A failed run is excluded before its trace is read for a condition, and a
context mismatch before anything, so an outcome never rests on a trace that describes
another run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.claims import structural_problems
from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import FailureCategory, System, TerminalStatus
from leaveimpact.evaluator.condition import ObservedCondition, observed_condition
from leaveimpact.evaluator.matching import match_claims
from leaveimpact.evaluator.oracle import (
    Answerable,
    UnreadableLeave,
    oracle_for,
    runtime_truth,
)
from leaveimpact.evaluator.plan_checks import (
    CheckFinding,
    CoverageGap,
    coverage_gaps,
    oracle_checks,
    report_checks,
)
from leaveimpact.evaluator.rows import ClaimRows
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world.scenario import Scenario


class LimitedReason(StrEnum):
    """Why a run has no comparative answer metrics; a member is the wire format."""

    UNREADABLE_LEAVE = "unreadable_leave"
    UNREADABLE_POLICY = "unreadable_policy"
    MIXED_CONDITION = "mixed_condition"


class ExcludedReason(StrEnum):
    """Why a run is counted and not graded; a member is the wire format."""

    FAILED_BY_DEFECT = "failed_by_defect"
    FAILED_BY_INFRASTRUCTURE = "failed_by_infrastructure"
    CONTEXT_MISMATCH = "context_mismatch"


@dataclass(frozen=True, slots=True)
class RunHeader:
    """Which run an outcome is of, as its export identifies it."""

    run_id: str
    attempt: int
    scenario_id: ScenarioId
    system: System
    status: TerminalStatus


@dataclass(frozen=True, slots=True)
class Graded:
    """A run graded against the oracle's answer for the condition it ran under.

    ``oracle_findings``, ``report_findings`` and ``coverage`` are ``None`` exactly when the
    claim set was structurally invalid: the plan checks were not evaluated, which is a
    different statement from having found nothing.
    """

    header: RunHeader
    condition: RunCondition
    rows: ClaimRows
    oracle_findings: tuple[CheckFinding, ...] | None
    report_findings: tuple[CheckFinding, ...] | None
    coverage: tuple[CoverageGap, ...] | None
    harness_findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        evaluated = self.rows.structurally_valid
        checks = (self.oracle_findings, self.report_findings, self.coverage)
        if any((check is not None) != evaluated for check in checks):
            raise ValueError(
                "the plan checks are evaluated exactly when the claim set is structurally valid"
            )


@dataclass(frozen=True, slots=True)
class Limited:
    """A run with no claim-level oracle: its report is checked against itself and no further.

    ``mixed`` holds the sources that both answered and failed, empty for an unreadable
    leave or policy. ``report_findings`` and ``coverage`` are ``None`` when the claim set was
    structurally invalid; the coverage gaps here are the ones the report's own conclusions
    call for, since no oracle outcome exists to call for any, and each is over the whole
    organization, the probe set included: no claim row exists here to hold a probed
    candidate's omission.
    """

    header: RunHeader
    condition: RunCondition
    reason: LimitedReason
    mixed: frozenset[Source]
    structural_problems: tuple[str, ...]
    report_findings: tuple[CheckFinding, ...] | None
    coverage: tuple[CoverageGap, ...] | None
    harness_findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (self.reason is LimitedReason.MIXED_CONDITION) != bool(self.mixed):
            raise ValueError("a mixed condition names its mixed sources, and only it does")
        evaluated = not self.structural_problems
        if any((check is not None) != evaluated for check in (self.report_findings, self.coverage)):
            raise ValueError(
                "the report's checks are evaluated exactly when the claim set is structurally valid"
            )


@dataclass(frozen=True, slots=True)
class Excluded:
    """A run counted and not graded, with the reason."""

    header: RunHeader
    reason: ExcludedReason


type RunOutcome = Graded | Limited | Excluded


def grade_run(world: SealedWorld, export: RunExport) -> RunOutcome:
    """The outcome of the run ``export`` records, against ``world``.

    Raises nothing for what the run did. ``OracleDisagrees`` can propagate from the oracle:
    a defect of the evaluator, which no outcome should paper over.
    """
    record, trace = export.record, export.trace
    header = RunHeader(
        export.run_id, export.attempt, export.context.scenario_id, record.system, record.status
    )
    scenario = world.scenario(export.context.scenario_id)
    if scenario is None or world.context_of(scenario) != export.context:
        return Excluded(header, ExcludedReason.CONTEXT_MISMATCH)
    if record.failure is not None:
        failed_by = (
            ExcludedReason.FAILED_BY_DEFECT
            if record.failure.category is FailureCategory.DEFECT
            else ExcludedReason.FAILED_BY_INFRASTRUCTURE
        )
        return Excluded(header, failed_by)
    observed = observed_condition(trace)
    harness = _condition_findings(record.observed_condition, observed.condition)
    if observed.is_mixed:
        return _limited(
            world, scenario, export, header, observed, LimitedReason.MIXED_CONDITION, harness
        )
    oracle = oracle_for(world, scenario, observed.condition)
    if not isinstance(oracle, Answerable):
        unreadable = (
            LimitedReason.UNREADABLE_LEAVE
            if isinstance(oracle, UnreadableLeave)
            else LimitedReason.UNREADABLE_POLICY
        )
        return _limited(world, scenario, export, header, observed, unreadable, harness)
    claims = trace.claims
    rows = match_claims(oracle, claims)
    if not rows.structurally_valid:
        return Graded(header, observed.condition, rows, None, None, None, harness)
    return Graded(
        header,
        observed.condition,
        rows,
        oracle_checks(oracle, claims),
        report_checks(claims, scenario, oracle.view),
        coverage_gaps(claims, oracle.universe, oracle),
        harness,
    )


def _limited(
    world: SealedWorld,
    scenario: Scenario,
    export: RunExport,
    header: RunHeader,
    observed: ObservedCondition,
    reason: LimitedReason,
    harness: tuple[str, ...],
) -> Limited:
    """The outcome of a run with no claim-level oracle: its report checked against itself,
    or not checked at all when its claim set is structurally invalid."""
    claims = export.trace.claims
    problems = structural_problems(claims)
    findings: tuple[CheckFinding, ...] | None = None
    gaps: tuple[CoverageGap, ...] | None = None
    if not problems:
        view = runtime_truth(world, scenario).at(scenario.spec.today, observed.condition)
        universe = tuple(employee.id for employee in world.org.employees)
        findings = report_checks(claims, scenario, view)
        gaps = coverage_gaps(claims, universe)
    mixed = observed.mixed if reason is LimitedReason.MIXED_CONDITION else frozenset[Source]()
    return Limited(header, observed.condition, reason, mixed, problems, findings, gaps, harness)


def _condition_findings(recorded: RunCondition, observed: RunCondition) -> tuple[str, ...]:
    """The harness finding when the record's condition is not the one the trace shows."""
    if recorded == observed:
        return ()

    def named(condition: RunCondition) -> str:
        unreachable = sorted(source.value for source in Source if source not in condition.reachable)
        return ", ".join(unreachable) if unreachable else "nothing"

    return (
        f"the record states {named(recorded)} unreachable and the trace shows "
        f"{named(observed)} unreachable; the trace stands",
    )


__all__ = [
    "Excluded",
    "ExcludedReason",
    "Graded",
    "Limited",
    "LimitedReason",
    "RunHeader",
    "RunOutcome",
    "grade_run",
]
