"""The rules-only baseline's basis: what the shared rules conclude over structured reads alone.

A measurement, not a pass-or-fail probe: it has no criterion, it produced the numbers the
six rulings of the investigator milestone's fifth build step were made on (the stream's
`m2-build/2026-10-02-step-5-rulings.md`). It was first run on 2026-10-02 and 2026-10-03
from six scratch scripts, one question at a time, while the rulings were being argued; this
file is the same computation in one pass per world, committed with its capture before any
code of the baseline exists.

The rules-only baseline reads the structured systems through a frozen prefetch, feeds what
came back to the shared rules, and reports their results. It reads no document, so it
holds no clause and no constraint. None of it is built yet, and this probe forecasts it by
simulation: a full read with the document reads left out, the view the evaluator builds
from those reads, the rules asked with an empty constraint list. The build's last code
group grades the real baseline on the reference seed and must reproduce section 6.

Seven questions, the ruling each one decided in brackets:

1. *The structured-only answer against the oracle* [rulings 2 and 4]. Under the normal
   condition, the tracker outage and the calendar outage: which scenarios get the oracle's
   answer whole, which impacts are not grounded, and on the impacts found, how the
   outcome, the required count and each must-assess verdict compare.
2. *Candidate selection* [ruling 1]. The oracle's verdicts restricted to a selection of the
   organization a prefetch might make (the leaver's team, with the component's members,
   with the holders of a needed skill), and the plan rule rerun over the restriction with
   the oracle's required count. The needed skill is the oracle's knowledge: it is stated
   only in a clause, so no prefetch can compute the selections that use it.
3. *The prefetch window* [ruling 5]. The run context carries no window, so a prefetch
   derives one from the leave it read. The scenario's window replaced by the leave's span,
   exactly and with one day each side, the document reads kept so that only the window
   varies, and the oracle's own question asked over the view. And the structured-only
   answer read with the leave's exact span, against the same answer read with the
   scenario's window: the fixture's full read uses the scenario's window, so sections 1,
   4 and 6 forecast a baseline that reads the leave's span only where the two are equal.
   The scratch run did not ask this.
4. *The reporting policy* [ruling 6]. For each impact the structured-only answer grounds:
   an assessment of every employee, against a walk in id order that stops once the
   required count of viable candidates is reached.
5. *Prose in the evaluator's view* [the build design's second call]. The tracker's
   enumeration returns comments, and the evaluator admits the sealed facts a returned
   comment carries. The baseline derives nothing from prose. Counted: those facts in the
   view of a structured-only read, and whether the rules' conclusions with no constraint
   change without them. The scratch run asked this of the reference seed only; here it is
   asked of every seed and condition, since sections 1 and 4 are computed over the
   evaluator's view and forecast the baseline only where the answer is no.
6. *The answer graded* [rulings 2 and 6]. The reference seed. The structured-only answer
   written as a report, every employee assessed for every impact, graded by the real
   evaluator under the three conditions.
7. *The degraded states* [ruling 4]. The reference seed. What the evaluator makes of an
   empty report and of a non-empty one when the HR system is down and when the corpus is;
   what the plan rule says of an impact with nobody enumerated; whether the vocabulary can
   state an unknown about the leave record.

Two imports are stated, since no other committed probe makes either.

The tests' fixtures (`tests.unit`): the throwaway world, the in-memory ports with the
recorder that calls the declared tools through them, the export around a trace, the
truthful report, and the full-read test's `parts`, the comparison it holds a view to the
oracle by. A probe that built its own reads would be a second implementation of the ports,
the recorder and the export. The first scratch run had one wrong column for exactly that
reason, a plan rule written again locally; the outcome here is `core.plans.expected_action`.
The step's acceptance grades the baseline through these same ports. The price is that the
capture regenerates only while the fixtures stand, and the step's execution layer replaces
the recorder: the probe is rerun there, and its capture is identical or the difference is
explained.

`evaluator.oracle._conclusions`, a private name: the rules' conclusions over a view with a
given constraint list. The public `conclusions_in` passes the sealed key's constraints, and
the measurement needs none. A public entry for one measurement would widen the oracle for
nothing the package uses.

The worlds are assembled in memory from seeds and hold nothing private; nothing is read
from a bucket and nothing is written but the report on standard output.

Run: `PYTHONPATH=. uv run python probes/baseline-basis/probe.py > probes/captures/baseline-basis/twenty-seeds.txt`
from a POSIX shell at the repository root (Windows PowerShell 5.1 redirects as UTF-16;
the root is on the path for the tests' fixtures). Seeds 1 to 20 by default; pass seeds as
arguments for another set. Sections 6 and 7 are of the reference seed whatever the set.
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import timedelta

from leaveimpact.core import Operation, OutageAssignment, RunCondition, RunExport, Source, Unknown
from leaveimpact.core.claims import CoverageActionKind, UnknownReason, Verdict
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import FactBase
from leaveimpact.core.ids import claim_id
from leaveimpact.core.plans import expected_action
from leaveimpact.core.predicates import REGISTRY, PredicateName
from leaveimpact.core.refs import leave_ref
from leaveimpact.core.timeshape import encode_date_span, encode_instant
from leaveimpact.core.values import SkillCriterion
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.evaluator.grading import Graded, Limited
from leaveimpact.evaluator.observed_view import ObservedRun, observe
from leaveimpact.evaluator.oracle import Answerable, _conclusions, conclusions_in, oracle_for
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world import Scenario
from leaveimpact.world.runtime_view import window_instants
from leaveimpact.world.version import GENERATOR_VERSION
from tests.unit.export_fixture import DIGEST, run_export
from tests.unit.reads_fixture import Recorder, reads_of_everything, systems_holding
from tests.unit.report_fixture import truthful_report
from tests.unit.test_evaluator_full_read import parts
from tests.unit.throwaway_world import REFERENCE_SEED, loaded_world

PLAN = "golden"
NORMAL = RunCondition.all_reachable()
OUTAGES: tuple[tuple[Source, ...], ...] = ((), (Source.JIRA,), (Source.CALENDAR,))
SELECTIONS = (
    "the leaver's team",
    "team and component members",
    "team and needed-skill holders",
    "all three",
)
MARGINS = (0, 1)
UNIVERSAL = (CoverageActionKind.UNCOVERED, CoverageActionKind.UNKNOWN)
PROSE_CARRIERS = (EntityKind.COMMENT, EntityKind.CLAUSE)


@dataclass(frozen=True)
class StructuredRead:
    """A full read of a scenario less every document read, what the evaluator observes of
    it, and what the rules conclude over that view with no constraint."""

    operations: tuple[Operation, ...]
    run: ObservedRun
    answer: Answerable


def named(down: tuple[Source, ...]) -> str:
    return "normal" if not down else f"{down[0].value} down"


def spread(counter: Counter) -> str:
    return ", ".join(f"{key}: {count}" for key, count in sorted(counter.items())) or "none"


def answerable(answer: object) -> Answerable:
    assert isinstance(answer, Answerable), type(answer)
    return answer


def structured_read(
    world: SealedWorld, scenario: Scenario, down: tuple[Source, ...]
) -> StructuredRead:
    """The simulated baseline's reads of ``scenario`` with ``down`` unreachable throughout."""
    kept = tuple(
        operation
        for operation in reads_of_everything(world, scenario, *down)
        if operation.tool != "document"
    )
    run = observe(world.index, run_export(world, scenario, operations=kept))
    return StructuredRead(kept, run, answerable(_conclusions(world, scenario, run.view, ())))


# 1. The structured-only answer against the oracle.


def against_oracle(
    c: Counter, scenario: Scenario, oracle: Answerable, read: StructuredRead
) -> None:
    base = read.answer
    c["integrity findings"] += len(read.run.findings)
    base_keys = {truth.key for truth in base.impacts}
    oracle_keys = {truth.key for truth in oracle.impacts}
    c["oracle impacts"] += len(oracle_keys)
    c["impacts not grounded"] += len(oracle_keys - base_keys)
    c["impacts extra"] += len(base_keys - oracle_keys)
    same = base_keys == oracle_keys
    for truth in oracle.impacts:
        got = base.impact(truth.key)
        if got is None:
            continue
        c["impacts found"] += 1
        c[("outcome", truth.outcome.value, got.outcome.value)] += 1
        c[("required", truth.required, got.required)] += 1
        same &= truth.outcome is got.outcome
        for theirs in truth.assessments:
            if theirs.employee_id not in truth.probe:
                continue
            ours = got.assessment_of(theirs.employee_id)
            assert ours is not None
            stated = ours.verdict.value
            if theirs.verdict is ours.verdict and theirs.reasons != ours.reasons:
                stated += " with other reasons"
            c["must-assess on impacts found"] += 1
            c[("must-assess", theirs.verdict.value, stated)] += 1
            same &= (theirs.verdict, theirs.reasons) == (ours.verdict, ours.reasons)
    theirs_conflicts, ours_conflicts = set(oracle.conflicts), set(base.conflicts)
    theirs_unknowns, ours_unknowns = set(oracle.unknowns), set(base.unknowns)
    c["oracle conflicts"] += len(theirs_conflicts)
    c["conflicts not stated"] += len(theirs_conflicts - ours_conflicts)
    c["oracle unknowns"] += len(theirs_unknowns)
    c["unknowns stated"] += len(ours_unknowns)
    same &= theirs_conflicts == ours_conflicts and theirs_unknowns == ours_unknowns
    c[("equal by tier", scenario.key.tier.value, same)] += 1
    needs_corpus = Source.CORPUS in scenario.key.required_sources
    c[("equal by corpus", "required" if needs_corpus else "not required", same)] += 1


def equal_of(c: Counter, name: str) -> str:
    groups = sorted({key[1] for key in c if isinstance(key, tuple) and key[0] == name})
    return ", ".join(
        f"{group} {c[(name, group, True)]} of {c[(name, group, True)] + c[(name, group, False)]}"
        for group in groups
    )


def transitions(c: Counter, name: str) -> str:
    rows = sorted(
        (key[1], key[2], count)
        for key, count in c.items()
        if isinstance(key, tuple) and key[0] == name
    )
    return ", ".join(f"{theirs} -> {ours}: {count}" for theirs, ours, count in rows) or "none"


def print_against_oracle(basis: dict[tuple[Source, ...], Counter]) -> None:
    print("\n1. The structured-only answer against the oracle")
    print("(a transition reads: the oracle's -> the structured-only answer's)")
    for down, c in basis.items():
        print(f"{named(down)}:")
        print(
            "  scenarios equal to the oracle's answer whole, by tier: "
            f"{equal_of(c, 'equal by tier')}"
        )
        print(f"  by whether the key requires the corpus: {equal_of(c, 'equal by corpus')}")
        print(
            f"  impacts: the oracle's {c['oracle impacts']}, not grounded "
            f"{c['impacts not grounded']}, found {c['impacts found']}, beyond the oracle's "
            f"{c['impacts extra']}"
        )
        print(f"  outcome on the impacts found: {transitions(c, 'outcome')}")
        print(f"  required count on the impacts found: {transitions(c, 'required')}")
        print(
            f"  must-assess verdicts on the impacts found ({c['must-assess on impacts found']}): "
            f"{transitions(c, 'must-assess')}"
        )
        print(
            f"  conflicts: the oracle's {c['oracle conflicts']}, not stated "
            f"{c['conflicts not stated']}; unknowns: the oracle's {c['oracle unknowns']}, "
            f"stated {c['unknowns stated']}"
        )
        print(f"  integrity findings in the view: {c['integrity findings']}")


# 2. Candidate selection.


def candidate_selection(
    selection: dict[str, Counter],
    totals: Counter,
    world: SealedWorld,
    scenario: Scenario,
    oracle: Answerable,
) -> None:
    employees = {employee.id: employee for employee in world.org.employees}
    members = {component.id: set(component.member_ids) for component in world.org.components}
    component_of = {
        planted.entity.id: planted.entity.component_id
        for owner in world.scenarios
        for planted in owner.owned.work_items
    }
    leaver = scenario.investigated_leave.employee_id
    team = {e.id for e in world.org.employees if e.team_id == employees[leaver].team_id}
    for truth in oracle.impacts:
        totals["impacts"] += 1
        artifact = truth.key.artifact.id
        component = members[component_of[artifact]] if artifact in component_of else set()
        needed = {
            criterion.skill
            for resolved in truth.requirements
            for criterion in resolved.requirement.criteria
            if isinstance(criterion, SkillCriterion)
        }
        holders = {e.id for e in world.org.employees if e.skills and needed & set(e.skills)}
        viable = {a.employee_id for a in truth.assessments if a.verdict is Verdict.VIABLE}
        probe = set(truth.probe)
        totals["viable verdicts"] += len(viable)
        totals["must-assess verdicts"] += len(probe)
        selected_sets = (team, team | component, team | holders, team | component | holders)
        chosen = dict(zip(SELECTIONS, selected_sets, strict=True))
        for name, selected in chosen.items():
            s = selection[name]
            s["size"] += len(selected)
            s["viable outside"] += len(viable - selected)
            s["must-assess outside"] += len(probe - selected)
            narrowed = expected_action(
                (a.verdict for a in truth.assessments if a.employee_id in selected),
                truth.required,
            )
            s["outcome changes"] += narrowed is not truth.outcome


def print_candidate_selection(selection: dict[str, Counter], totals: Counter) -> None:
    print("\n2. Candidate selection (normal condition)")
    print(
        f"impacts: {totals['impacts']}; viable verdicts: {totals['viable verdicts']}; "
        f"must-assess verdicts: {totals['must-assess verdicts']}; organization size: "
        f"{totals['employees'] // totals['worlds']}"
    )
    print(
        f"  {'selection':<32}{'mean size':>10}{'viable outside':>16}"
        f"{'must-assess outside':>21}{'outcome changes':>17}"
    )
    for name, s in selection.items():
        print(
            f"  {name:<32}{s['size'] / totals['impacts']:>10.1f}{s['viable outside']:>16}"
            f"{s['must-assess outside']:>21}{s['outcome changes']:>17}"
        )


# 3. The prefetch window.


def reads_with_window(
    world: SealedWorld, scenario: Scenario, window: DateSpan, down: tuple[Source, ...] = ()
) -> tuple[Operation, ...]:
    """A full read of ``scenario`` with ``window`` read in place of the scenario's own and
    ``down`` unreachable throughout.

    The fixture's ``full_read`` takes its window from the scenario's spec, and a spec
    refuses a window that leaves its ``now`` outside, which a leave's span does. So the
    same reads are listed here with the window as a parameter, the one place this probe
    restates a fixture.
    """
    systems = systems_holding(world)
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    reads = Recorder(systems)
    spec = scenario.spec
    instants = window_instants(window, spec.reference_timezone)
    reads.read("leave", {"id": spec.leave_id})
    reads.read("employees")
    reads.read("components")
    reads.read("work_items")
    reads.read("leaves_within", {"span": encode_date_span(window)})
    reads.read(
        "events_within",
        {"span": {"start": encode_instant(instants.start), "end": encode_instant(instants.end)}},
    )
    for owner in world.scenarios:
        for planted in owner.owned.documents:
            reads.read("document", {"id": planted.entity.id})
    return tuple(reads.operations)


def prefetch_window(
    shape: dict[str, Counter],
    equal: dict[int, Counter],
    structured: Counter,
    world: SealedWorld,
    scenario: Scenario,
    oracle: Answerable,
    reads: dict[tuple[Source, ...], StructuredRead],
) -> None:
    """The window's effect on the oracle's question, the documents read, and on the
    structured-only answer of ``reads``, which was read with the scenario's own window."""
    leave, window = scenario.investigated_leave, scenario.spec.window
    shape["leave length in days"][(leave.end - leave.start).days + 1] += 1
    shape["days the scenario's window starts before the leave"][
        (leave.start - window.start).days
    ] += 1
    shape["days the scenario's window ends after the leave"][(window.end - leave.end).days] += 1
    for planted in scenario.owned.events:
        hours = (planted.entity.end - planted.entity.start).total_seconds() / 3600
        shape["event length in hours"][round(hours, 1)] += 1
    for margin in MARGINS:
        derived = DateSpan(leave.start - timedelta(days=margin), leave.end + timedelta(days=margin))
        operations = reads_with_window(world, scenario, derived)
        run = observe(world.index, run_export(world, scenario, operations=operations))
        same = parts(conclusions_in(world, scenario, run.view)) == parts(oracle)
        equal[margin][(scenario.key.tier.value, same)] += 1
    for down, read in reads.items():
        kept = tuple(
            operation
            for operation in reads_with_window(world, scenario, leave.span, down)
            if operation.tool != "document"
        )
        view = observe(world.index, run_export(world, scenario, operations=kept)).view
        narrowed = _conclusions(world, scenario, view, ())
        structured[(named(down), parts(narrowed) == parts(read.answer))] += 1


def print_prefetch_window(
    shape: dict[str, Counter], equal: dict[int, Counter], structured: Counter
) -> None:
    print("\n3. The prefetch window")
    for name, counter in shape.items():
        print(f"{name}: {spread(counter)}")
    for margin, c in equal.items():
        tiers = sorted({tier for tier, _ in c})
        same = sum(count for (_, equal_), count in c.items() if equal_)
        by_tier = ", ".join(f"{t} {c[(t, True)]} of {c[(t, True)] + c[(t, False)]}" for t in tiers)
        print(
            f"a full read with the leave's span and {margin} day(s) each side, normal "
            f"condition: the answer equals the oracle's in {same} of {sum(c.values())} "
            f"({by_tier})"
        )
    conditions = sorted({name for name, _ in structured}, key=[named(d) for d in OUTAGES].index)
    print(
        "the structured-only answer read with the leave's exact span, against the one read "
        "with the scenario's window (sections 1, 4 and 6): "
        + ", ".join(
            f"{name} equal in {structured[(name, True)]} of "
            f"{structured[(name, True)] + structured[(name, False)]}"
            for name in conditions
        )
    )


# 4. The reporting policy.


def reporting_policy(c: Counter, oracle: Answerable, read: StructuredRead) -> None:
    for got in read.answer.impacts:
        c["impacts grounded"] += 1
        ordered = sorted(got.assessments, key=lambda assessment: assessment.employee_id)
        c["everyone: assessments"] += len(ordered)
        walked: list = []
        viable = 0
        for assessment in ordered:
            walked.append(assessment.employee_id)
            viable += assessment.verdict is Verdict.VIABLE
            if viable >= got.required:
                break
        c["stopping: assessments"] += len(walked)
        truth = oracle.impact(got.key)
        if truth is None:
            continue
        probe = set(truth.probe)
        c["must-assess rows"] += len(probe)
        c["stopping: must-assess rows left out"] += len(probe - set(walked))
        if truth.outcome in UNIVERSAL:
            c["impacts where the oracle calls for everyone"] += 1
            everyone = {assessment.employee_id for assessment in truth.assessments}
            missing = everyone - probe - set(walked)
            c["stopping: impacts with a coverage gap"] += bool(missing)
            c["stopping: colleagues named by the gaps"] += len(missing)


def print_reporting_policy(c: Counter) -> None:
    print(
        "\n4. The reporting policy (normal condition, the impacts the structured-only answer "
        "grounds)"
    )
    print(
        f"impacts grounded: {c['impacts grounded']}; must-assess rows on them: "
        f"{c['must-assess rows']}"
    )
    print(
        f"everyone assessed: {c['everyone: assessments']} assessments, no must-assess row left out"
    )
    print(
        "walking the employees in id order and stopping at the required count of viable "
        f"candidates: {c['stopping: assessments']} assessments, "
        f"{c['stopping: must-assess rows left out']} must-assess rows left out"
    )
    print(
        f"impacts where the oracle calls for everyone: "
        f"{c['impacts where the oracle calls for everyone']}; with a coverage gap under "
        f"stopping: {c['stopping: impacts with a coverage gap']}, naming "
        f"{c['stopping: colleagues named by the gaps']} colleagues"
    )


# 5. Prose in the evaluator's view.


def prose_in_view(c: Counter, world: SealedWorld, scenario: Scenario, read: StructuredRead) -> None:
    view = read.run.view
    prose = [fact for fact in view.facts if fact.evidence.target.kind in PROSE_CARRIERS]
    c["scenarios"] += 1
    c["scenarios holding one"] += bool(prose)
    for fact in prose:
        c[("carried", fact.predicate.value, fact.evidence.target.kind.value)] += 1
    structured = tuple(fact for fact in view.facts if fact not in prose)
    bare = FactBase(structured, tuple(view.gaps)).observed(
        scenario.spec.today, view.condition, read.run.coverage
    )
    without = _conclusions(world, scenario, bare, ())
    c["conclusions changed without them"] += parts(read.answer) != parts(without)


def prose_line(c: Counter) -> str:
    carried = Counter(
        {f"{key[1]} on a {key[2]}": count for key, count in c.items() if isinstance(key, tuple)}
    )
    return (
        f"prose-carried facts {sum(carried.values())} ({spread(carried)}); scenarios holding "
        f"one {c['scenarios holding one']} of {c['scenarios']}; scenarios whose conclusions "
        f"with no constraint change without them {c['conclusions changed without them']}"
    )


def print_prose(prose: dict[tuple[Source, ...], Counter], reference: Counter) -> None:
    print("\n5. Prose in the evaluator's view of a structured-only read")
    for down, c in prose.items():
        print(f"{named(down)}: {prose_line(c)}")
    if reference:
        print(f"the reference seed alone, normal: {prose_line(reference)}")


# 6 and 7. The reference seed through the real evaluator.


def with_outage(export: RunExport, down: tuple[Source, ...]) -> RunExport:
    outage = OutageAssignment(frozenset(down), DIGEST)
    return replace(export, record=replace(export.record, outage=outage))


def graded_summary(world: SealedWorld, build: Callable[[Scenario], RunExport]) -> list[str]:
    """What the evaluator makes of ``build``'s export of every scenario, as report lines."""
    outcomes: Counter = Counter()
    standings: Counter = Counter()
    against_oracle_: Counter = Counter()
    report: Counter = Counter()
    c: Counter = Counter()
    for scenario in world.scenarios:
        export = build(scenario)
        c["claims"] += len(export.trace.claims)
        outcome = evaluate_run(world, export).outcome
        name = type(outcome).__name__
        if isinstance(outcome, Limited):
            name += f" as {outcome.reason.value}"
        outcomes[name] += 1
        if not isinstance(outcome, (Graded, Limited)):
            continue
        problems = (
            outcome.rows.structural_problems
            if isinstance(outcome, Graded)
            else outcome.structural_problems
        )
        c["structural problems"] += len(problems)
        c["coverage gaps"] += len(outcome.coverage or ())
        c["integrity findings"] += len(outcome.integrity)
        c["harness findings"] += len(outcome.harness_findings)
        for finding in outcome.report_findings or ():
            report[finding.family.value] += 1
        if isinstance(outcome, Graded):
            for finding in outcome.oracle_findings or ():
                against_oracle_[finding.family.value] += 1
        if outcome.grounding is not None:
            for grounding in outcome.grounding.claims:
                standing = grounding.standing.value
                if grounding.reason is not None:
                    standing += f" ({grounding.reason.value})"
                standings[f"{grounding.claim_type.value} {standing}"] += 1
    reproduced = sum(n for key, n in standings.items() if key.endswith(" reproduced"))
    return [
        f"{c['claims']} claims in {len(world.scenarios)} reports; outcomes: {spread(outcomes)}",
        f"  replay: {reproduced} reproduced of {sum(standings.values())} ({spread(standings)})",
        f"  structural problems {c['structural problems']}, report findings "
        f"{sum(report.values())}, coverage gaps {c['coverage gaps']}, integrity findings "
        f"{c['integrity findings']}, harness findings {c['harness findings']}",
        f"  findings against the oracle: {spread(against_oracle_)}",
    ]


def print_graded(world: SealedWorld) -> None:
    print("\n6. The structured-only answer graded by the evaluator (the reference seed)")
    for down in OUTAGES:
        condition = NORMAL.without(*down)

        def build(scenario: Scenario, down=down, condition=condition) -> RunExport:
            read = structured_read(world, scenario, down)
            claims = truthful_report(read.answer)
            export = run_export(
                world, scenario, claims, operations=read.operations, recorded=condition
            )
            return with_outage(export, down)

        lines = graded_summary(world, build)
        print(f"{named(down)}: {lines[0]}")
        print("\n".join(lines[1:]))


def print_degraded(world: SealedWorld) -> None:
    print("\n7. The degraded states (the reference seed)")

    def export_under(
        scenario: Scenario, down: tuple[Source, ...], claims: Sequence = ()
    ) -> RunExport:
        operations = reads_of_everything(world, scenario, *down)
        export = run_export(
            world, scenario, claims, operations=operations, recorded=NORMAL.without(*down)
        )
        return with_outage(export, down)

    hr, corpus = (Source.FRAPPE,), (Source.CORPUS,)
    rows: dict[str, Callable[[Scenario], RunExport]] = {
        "the HR system down, an empty report": lambda s: export_under(s, hr),
        "the HR system down, the normal condition's truthful report": lambda s: export_under(
            s, hr, truthful_report(answerable(oracle_for(world, s, NORMAL)))
        ),
        "the corpus down, an empty report": lambda s: export_under(s, corpus),
        "the corpus down, the structured-only answer": lambda s: export_under(
            s, corpus, truthful_report(structured_read(world, s, ()).answer)
        ),
    }
    for name, build in rows.items():
        lines = graded_summary(world, build)
        print(f"{name}: {lines[0]}")
        print("\n".join(lines[1:3]))

    print(
        "the plan rule over no verdicts, one viable person required: "
        f"{expected_action((), 1).value}"
    )
    leave = world.scenarios[0].spec.leave_id
    try:
        Unknown(
            claim_id=claim_id(1),
            evidence_refs=(),
            subject=leave_ref(leave),
            required_fact=PredicateName.ON_LEAVE,
            reason=UnknownReason.INACCESSIBLE,
        )
        stated = "constructed"
    except ValueError as refused:
        stated = f"refused at construction ({refused})"
    print(f"an unknown about the leave record, on_leave, inaccessible: {stated}")
    subjects = Counter(row.subject.value for row in REGISTRY.values())
    print(f"subject kinds of the predicate registry: {spread(subjects)}")


def main(seeds: list[int]) -> None:
    totals: Counter = Counter()
    basis = {down: Counter() for down in OUTAGES}
    selection = {name: Counter() for name in SELECTIONS}
    shape: dict[str, Counter] = {
        "leave length in days": Counter(),
        "days the scenario's window starts before the leave": Counter(),
        "days the scenario's window ends after the leave": Counter(),
        "event length in hours": Counter(),
    }
    window_equal = {margin: Counter() for margin in MARGINS}
    window_structured: Counter = Counter()
    policy: Counter = Counter()
    prose = {down: Counter() for down in OUTAGES}
    reference_prose: Counter = Counter()

    for seed in seeds:
        world = loaded_world(PLAN, seed)
        totals["worlds"] += 1
        totals["scenarios"] += len(world.scenarios)
        totals["employees"] += len(world.org.employees)
        for scenario in world.scenarios:
            normal = answerable(oracle_for(world, scenario, NORMAL))
            reads: dict[tuple[Source, ...], StructuredRead] = {}
            for down in OUTAGES:
                oracle = (
                    normal
                    if not down
                    else answerable(oracle_for(world, scenario, NORMAL.without(*down)))
                )
                read = reads[down] = structured_read(world, scenario, down)
                against_oracle(basis[down], scenario, oracle, read)
                prose_in_view(prose[down], world, scenario, read)
                if not down:
                    reporting_policy(policy, oracle, read)
                    if seed == REFERENCE_SEED:
                        prose_in_view(reference_prose, world, scenario, read)
            candidate_selection(selection, totals, world, scenario, normal)
            prefetch_window(shape, window_equal, window_structured, world, scenario, normal, reads)
        print(f"seed {seed} done", file=sys.stderr)

    print(
        f"the rules-only baseline's basis, measured on the {PLAN} plan under generator "
        f"version {GENERATOR_VERSION}"
    )
    print(
        f"seeds {seeds[0]}..{seeds[-1]} ({len(seeds)} worlds), scenarios "
        f"{totals['scenarios']}; the reference seed is {REFERENCE_SEED}"
    )
    print_against_oracle(basis)
    print_candidate_selection(selection, totals)
    print_prefetch_window(shape, window_equal, window_structured)
    print_reporting_policy(policy)
    print_prose(prose, reference_prose)
    reference = loaded_world(PLAN, REFERENCE_SEED)
    print_graded(reference)
    print_degraded(reference)


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]] or list(range(1, 21)))
