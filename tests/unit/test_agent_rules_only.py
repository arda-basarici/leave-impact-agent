"""The rules-only baseline states exactly what the shared rules conclude over its own reads,
under the one reporting policy: the claim set equal to the policy's enumerated here from the
composing pass over the same view, on every scenario under the normal condition and the two
gradable outages; each claim citing records of its own proof; the same claims on a second run;
abstention when the leave or the universe was not read, a defect at its operation when the
HR system or an adapter contradicted itself, a defect outranking abstention; and the
simulation the step's rulings were measured on reproduced claim for claim."""

from collections import Counter
from dataclasses import dataclass, replace

import pytest

from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.rules_only import Abstention, RulesOnlyRun, investigate
from leaveimpact.core import (
    Assessment,
    AssessmentKey,
    CandidateAssessment,
    Claim,
    ClaimType,
    ConflictFinding,
    ConflictKey,
    CoverageAction,
    CoverageActionKind,
    Fact,
    FailureCategory,
    Grounded,
    Impact,
    ImpactConclusion,
    KindSlice,
    Leave,
    LeaveKind,
    LeaveStatus,
    MalformedRecord,
    Observed,
    PredicateName,
    Reading,
    RunCondition,
    RunExport,
    SliceStatus,
    Source,
    SourceConflict,
    SourceUnreachable,
    TerminalStatus,
    Unknown,
    UnknownKey,
    UnknownReason,
    Unresolved,
    Verdict,
    citable_record,
    conclude_impacts,
    conflicts_on,
    derive_impacts,
    employee_ref,
    key_order,
    project_reads,
)
from leaveimpact.core.entities import Component, Employee
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import EmployeeId, LeaveId, claim_id, employee_id, leave_id
from leaveimpact.core.run_ending import OperationSite
from leaveimpact.core.run_trace import OperationId
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.evaluator.observed_view import observe
from leaveimpact.evaluator.oracle import (
    Answerable,
    _conclusions,  # pyright: ignore[reportPrivateUsage]  # the simulation's own question
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit import world_fixture as w
from tests.unit.export_fixture import approval, run_export
from tests.unit.in_memory_ports import InMemoryPeople, InMemoryWork
from tests.unit.reads_fixture import FakeSystems, Systems, fakes_holding, systems_holding
from tests.unit.report_fixture import truthful_report
from tests.unit.throwaway_world import loaded_world

OUTAGES: tuple[tuple[Source, ...], ...] = ((), (Source.JIRA,), (Source.CALENDAR,))
CLAIMS_FORECAST: dict[tuple[Source, ...], int] = {
    (): 810,
    (Source.JIRA,): 270,
    (Source.CALENDAR,): 540,
}
Statement = tuple[object, ...]
TYPE_ORDER = (
    ClaimType.IMPACT,
    ClaimType.UNKNOWN,
    ClaimType.CANDIDATE_ASSESSMENT,
    ClaimType.COVERAGE_ACTION,
    ClaimType.SOURCE_CONFLICT,
)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def systems(world: SealedWorld) -> Systems:
    return systems_holding(world)


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


def run(
    world: SealedWorld, scenario: Scenario, systems: Systems | FakeSystems, *down: Source
) -> RulesOnlyRun:
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    return investigate(world.context_of(scenario), systems.ports)


def statement(claim: Claim) -> Statement:
    """What a claim states, apart from its id, its links and its citations."""
    match claim:
        case Impact():
            return ("impact", claim.key)
        case Unknown():
            return ("unknown", claim.key, claim.reason)
        case CandidateAssessment():
            return ("assessment", claim.key, claim.verdict, claim.reasons)
        case CoverageAction():
            return ("action", claim.key, claim.action, claim.assignee_ids)
        case SourceConflict():
            return (
                "conflict",
                claim.key,
                claim.observations,
                claim.resolved_value,
                claim.authority_rule,
            )
        case _:
            return ("other", claim.key)


# --- The claim set is the policy's --------------------------------------------------------------


def policy_statements(
    result: RulesOnlyRun, world: SealedWorld, scenario: Scenario
) -> Counter[Statement]:
    """The statements ruling 6's policy makes of the composing pass over the run's own view,
    enumerated here without the report writer: every grounded impact, everyone's assessment
    for each, one action per impact, the open questions once each, the conflicts on the
    evidence used."""
    context = world.context_of(scenario)
    projection = project_reads(result.operations, context.today)
    view = projection.view()
    leave = scenario.investigated_leave
    universe = sorted(
        {EmployeeId(r.ref.id) for r in projection.returned if r.ref.kind is EntityKind.EMPLOYEE}
    )
    grounded = derive_impacts(
        view, context.leave_id, leave.employee_id, leave.span, context.reference_timezone
    ).grounded
    conclusions = conclude_impacts(
        view, grounded, (), leave.employee_id, leave.span, context.reference_timezone, universe
    )
    expected: Counter[Statement] = Counter()
    evidence: list[Fact] = []
    for c in conclusions:
        assert isinstance(c.reading.grounding, Grounded)
        expected[("impact", c.impact)] += 1
        evidence.extend(c.reading.grounding.facts)
        viable = sorted(a.employee_id for a in c.reading.assessments if a.verdict is Verdict.VIABLE)
        assignees = tuple(viable[: c.required]) if c.outcome is CoverageActionKind.ASSIGN else ()
        expected[("action", c.impact, c.outcome, assignees)] += 1
        for a in c.reading.assessments:
            expected[("assessment", a_key(c, a), a.verdict, a.reasons)] += 1
            evidence.extend(a.evidence)
    for c in conclusions:
        for a in c.reading.assessments:
            for q in a.unresolved:
                expected[("unknown", u_key(q), q.reason)] = 1
    for finding in conflicts_on(view, evidence):
        expected[
            (
                "conflict",
                c_key(finding),
                finding.observations,
                finding.resolution.value,
                finding.resolution.rule,
            )
        ] += 1
    return +expected


def a_key(c: ImpactConclusion, a: Assessment) -> AssessmentKey:
    return AssessmentKey(c.impact, a.employee_id)


def u_key(q: Unresolved) -> UnknownKey:
    return UnknownKey(q.subject, q.predicate)


def c_key(finding: ConflictFinding) -> ConflictKey:
    return ConflictKey(finding.subject, finding.predicate)


@pytest.mark.parametrize("down", OUTAGES, ids=str)
def test_the_claim_set_is_the_policys_on_every_scenario(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    claims_total = 0
    for scenario in world.scenarios:
        result = run(world, scenario, systems_holding(world), *down)
        assert result.failure is None and result.abstention is None, scenario.spec.id
        assert Counter(statement(claim) for claim in result.claims) == policy_statements(
            result, world, scenario
        ), scenario.spec.id
        claims_total += len(result.claims)
    assert claims_total == CLAIMS_FORECAST[down]


def test_the_baseline_reproduces_the_simulation_the_rulings_were_measured_on(
    world: SealedWorld,
) -> None:
    # The probe forecast the baseline as the oracle's own composition over the evaluator's
    # view of a full read less the documents, with no constraint; the real baseline's
    # statements are the same ones, scenario by scenario, under each condition.
    for down in OUTAGES:
        for scenario in world.scenarios:
            result = run(world, scenario, systems_holding(world), *down)
            export = run_export(world, scenario, operations=result.operations)
            simulated = _conclusions(world, scenario, observe(world.index, export).view, ())
            assert isinstance(simulated, Answerable)
            assert Counter(statement(claim) for claim in result.claims) == Counter(
                statement(claim) for claim in truthful_report(simulated)
            ), scenario.spec.id


def test_claims_are_ordered_by_type_then_key_and_numbered_after_that(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    result = run(world, scenario, systems)
    claims = result.claims
    assert [claim.claim_id for claim in claims] == [claim_id(n) for n in range(1, len(claims) + 1)]
    types = [claim.claim_type for claim in claims]
    assert types == sorted(types, key=TYPE_ORDER.index)
    for kind in TYPE_ORDER:
        keys = [key_order(claim.key) for claim in claims if claim.claim_type is kind]
        assert keys == sorted(keys), kind
    assert not [claim for claim in claims if claim.claim_type is ClaimType.CONSTRAINT]


def test_the_same_observations_give_the_same_claims(world: SealedWorld, scenario: Scenario) -> None:
    first = run(world, scenario, systems_holding(world))
    second = run(world, scenario, systems_holding(world))
    assert first.claims == second.claims and first.claims
    assert first.operations == second.operations


def test_every_citation_is_a_record_of_the_claims_own_proof(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    result = run(world, scenario, systems)
    context = world.context_of(scenario)
    projection = project_reads(result.operations, context.today)
    view = projection.view()
    leave = scenario.investigated_leave
    universe = sorted(
        {EmployeeId(r.ref.id) for r in projection.returned if r.ref.kind is EntityKind.EMPLOYEE}
    )
    conclusions = {
        c.impact: c
        for c in conclude_impacts(
            view,
            derive_impacts(
                view, context.leave_id, leave.employee_id, leave.span, context.reference_timezone
            ).grounded,
            (),
            leave.employee_id,
            leave.span,
            context.reference_timezone,
            universe,
        )
    }
    cited = 0
    for claim in result.claims:
        targets = {evidence.target for evidence in claim.evidence_refs}
        match claim:
            case Impact():
                proof = conclusions[claim.key].reading.grounding.proof
            case CandidateAssessment():
                (assessment,) = [
                    a
                    for a in conclusions[claim.impact_key].reading.assessments
                    if a.employee_id == claim.employee_id
                ]
                proof = assessment.proof
            case CoverageAction():
                assert targets == set()
                continue
            case _:
                continue
        own = {t for witness in proof if (t := citable_record(witness)) is not None}
        assert targets == own, claim.claim_id
        cited += len(targets)
    assert cited > 0


# --- Abstention and defect ----------------------------------------------------------------------


def test_with_the_hr_system_down_the_run_abstains_after_one_operation(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    result = run(world, scenario, systems, Source.FRAPPE)
    assert result.abstention is Abstention.LEAVE_NOT_RETURNED
    assert result.claims == () and result.failure is None
    assert len(result.operations) == 1
    assert Source.FRAPPE not in result.condition.condition.reachable


def test_a_leave_the_hr_system_does_not_hold_is_an_abstention(
    world: SealedWorld, scenario: Scenario
) -> None:
    systems = fakes_holding(world)
    del systems.people.leaves[LeaveId(scenario.spec.leave_id)]
    result = run(world, scenario, systems)
    assert result.abstention is Abstention.LEAVE_NOT_RETURNED
    assert [op.tool for op in result.operations] == ["leave"]


@dataclass
class _PeopleWithoutAnEnumeration(InMemoryPeople):
    def employees(self) -> tuple[Observed[Employee], ...]:
        raise SourceUnreachable(self.source, "the list endpoint timed out")


@dataclass
class _PeopleWhoseWindowOmitsTheLeave(InMemoryPeople):
    def leaves_within(self, span: DateSpan) -> tuple[Observed[Leave], ...]:
        return ()


def test_a_window_that_omits_the_leave_read_by_id_is_a_defect_at_the_window(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    # The prefetch reads the leave by id and then every leave over its span: a window that
    # does not hold it contradicts the first read, and the run fails where that showed.
    people = _PeopleWhoseWindowOmitsTheLeave(
        people=dict(systems.people.people),
        leaves=dict(systems.people.leaves),
        teams=dict(systems.people.teams),
    )
    result = investigate(world.context_of(scenario), replace(systems.ports, people=people))
    window = next(op for op in result.operations if op.tool == "leaves_within")
    assert result.failure is not None and result.claims == ()
    assert result.failure.site == OperationSite(window.id)
    assert result.failure.reason == (
        f"omitted_by_window: this read and {result.operations[0].id} disagree about "
        f"leave {scenario.spec.leave_id}"
    )


def test_an_earlier_defect_still_outranks_a_later_contradiction(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    leave = scenario.investigated_leave
    people = _PeopleWhoseWindowOmitsTheLeave(
        people={k: v for k, v in systems.people.people.items() if k != leave.employee_id},
        leaves=dict(systems.people.leaves),
        teams=dict(systems.people.teams),
    )
    result = investigate(world.context_of(scenario), replace(systems.ports, people=people))
    assert result.failure is not None
    enumeration = next(op for op in result.operations if op.tool == "employees")
    assert result.failure.site == OperationSite(enumeration.id)


def test_an_uncovered_universe_is_an_abstention_and_the_plan_rule_never_runs(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    people = _PeopleWithoutAnEnumeration(
        people=dict(systems.people.people),
        leaves=dict(systems.people.leaves),
        teams=dict(systems.people.teams),
    )
    result = investigate(world.context_of(scenario), replace(systems.ports, people=people))
    assert result.abstention is Abstention.UNIVERSE_NOT_COVERED
    assert result.claims == ()
    # The HR system stopped at its enumeration; the leaves of the span were never asked for.
    assert [op.tool for op in result.operations] == [
        "leave",
        "employees",
        "components",
        "work_items",
        "events_within",
    ]
    projection = project_reads(result.operations, world.context_of(scenario).today)
    assert projection.coverage.status(KindSlice(EntityKind.EMPLOYEE)) is SliceStatus.FAILED


def test_another_leave_for_the_id_asked_is_a_defect_at_the_opening_operation(
    world: SealedWorld, scenario: Scenario
) -> None:
    systems = fakes_holding(world)
    asked = LeaveId(scenario.spec.leave_id)
    systems.people.leaves[asked] = Leave(
        leave_id(998),
        employee_id(1),
        scenario.investigated_leave.start,
        scenario.investigated_leave.end,
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    )
    result = run(world, scenario, systems)
    assert result.failure is not None
    assert result.failure.category is FailureCategory.DEFECT
    assert result.failure.site == OperationSite(OperationId("op-1"))
    assert "leave_998" in result.failure.reason
    assert result.abstention is None and result.claims == ()


def test_an_enumeration_without_the_leaver_is_a_defect_at_that_operation(
    world: SealedWorld, scenario: Scenario
) -> None:
    systems = fakes_holding(world)
    del systems.people.people[scenario.investigated_leave.employee_id]
    result = run(world, scenario, systems)
    assert result.failure is not None and result.failure.site == OperationSite(OperationId("op-2"))
    assert "holds no" in result.failure.reason


def test_a_record_no_fact_can_be_made_from_is_a_defect_at_its_operation(
    world: SealedWorld, scenario: Scenario
) -> None:
    systems = fakes_holding(world)
    blank = replace(world.org.employees[1], location="  ")
    systems.people.people[blank.id] = blank
    result = run(world, scenario, systems)
    assert result.failure is not None and result.failure.site == OperationSite(OperationId("op-2"))
    assert "no fact could be made" in result.failure.reason


@dataclass
class _WorkWithBrokenComponents(InMemoryWork):
    def components(self) -> tuple[Observed[Component], ...]:
        self._reach()
        raise MalformedRecord(self.source, "Component/all", "a member id of the wrong shape")


def test_a_malformed_record_is_a_defect_at_its_operation_and_outranks_abstention(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    work = _WorkWithBrokenComponents(
        tickets=dict(systems.work.tickets),
        components_by_id=dict(systems.work.components_by_id),
    )
    result = investigate(world.context_of(scenario), replace(systems.ports, work=work))
    assert result.failure is not None and result.failure.site == OperationSite(OperationId("op-4"))
    assert result.failure.category is FailureCategory.DEFECT
    # The same fault with the universe also unreadable: still the defect, never the abstention.
    people = _PeopleWithoutAnEnumeration(
        people=dict(systems.people.people),
        leaves=dict(systems.people.leaves),
        teams=dict(systems.people.teams),
    )
    both = investigate(
        world.context_of(scenario), ReadPorts(people, work, systems.calendar, systems.documents)
    )
    assert both.failure is not None and both.abstention is None
    assert both.failure.site == OperationSite(OperationId("op-3"))


def exported(world: SealedWorld, scenario: Scenario, result: RulesOnlyRun) -> RunExport:
    """``result`` as a run export, the fixture's provenance around it: what group E writes."""
    template = run_export(world, scenario)
    status = TerminalStatus.FAILED if result.failure is not None else TerminalStatus.COMPLETED
    return RunExport(
        template.format_version,
        "run-1",
        1,
        template.context,
        replace(
            template.record,
            status=status,
            failure=result.failure,
            approval=approval(result.claims, failed=result.failure is not None),
        ),
        replace(template.trace, operations=result.operations, claims=result.claims),
    )


def test_every_way_a_run_ends_is_exportable(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    context = world.context_of(scenario)
    leave = scenario.investigated_leave
    ways: dict[str, RulesOnlyRun] = {}
    ways["concluded"] = investigate(context, systems_holding(world).ports)
    hr_down = systems_holding(world)
    hr_down.people.reachable = False
    ways["abstained, leave not returned"] = investigate(context, hr_down.ports)
    no_list = systems_holding(world)
    people = _PeopleWithoutAnEnumeration(
        people=dict(no_list.people.people),
        leaves=dict(no_list.people.leaves),
        teams=dict(no_list.people.teams),
    )
    ways["abstained, universe not covered"] = investigate(
        context, replace(no_list.ports, people=people)
    )
    broken = systems_holding(world)
    work = _WorkWithBrokenComponents(
        tickets=dict(broken.work.tickets),
        components_by_id=dict(broken.work.components_by_id),
    )
    ways["defect, malformed"] = investigate(context, replace(broken.ports, work=work))
    another = fakes_holding(world)
    another.people.leaves[LeaveId(context.leave_id)] = Leave(
        leave_id(998),
        employee_id(1),
        leave.start,
        leave.end,
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    )
    ways["defect, another leave"] = investigate(context, another.ports)
    no_leaver = fakes_holding(world)
    del no_leaver.people.people[leave.employee_id]
    ways["defect, enumeration without the leaver"] = investigate(context, no_leaver.ports)
    blank = fakes_holding(world)
    blank.people.people[world.org.employees[1].id] = replace(world.org.employees[1], location="  ")
    ways["defect, underivable record"] = investigate(context, blank.ports)
    omitting = systems_holding(world)
    ways["defect, a window without the leave"] = investigate(
        context,
        replace(
            omitting.ports,
            people=_PeopleWhoseWindowOmitsTheLeave(
                people=dict(omitting.people.people),
                leaves=dict(omitting.people.leaves),
                teams=dict(omitting.people.teams),
            ),
        ),
    )

    assert sum(way.failure is not None for way in ways.values()) == 5
    assert sum(way.abstention is not None for way in ways.values()) == 2
    for name, way in ways.items():
        export = exported(world, scenario, way)
        assert export.record.failure == way.failure, name
        assert export.trace.operations == way.operations, name


# --- The report alone -----------------------------------------------------------------------------


def test_two_reasons_under_one_open_question_refuse_the_report() -> None:
    from leaveimpact.agent.report import rules_only_report

    who = employee_ref(w.BOB)
    first = Assessment(
        w.MEETING,
        w.BOB,
        Verdict.UNKNOWN,
        (),
        (Unresolved(who, PredicateName.HAS_SKILL, UnknownReason.INSUFFICIENT),),
        (),
    )
    second = Assessment(
        w.MEETING,
        w.DENIZ,
        Verdict.UNKNOWN,
        (),
        (Unresolved(who, PredicateName.HAS_SKILL, UnknownReason.INACCESSIBLE),),
        (),
    )
    reading = Reading(w.MEETING, Grounded(()), (first, second))
    conclusion = ImpactConclusion(
        reading,
        Unresolved(w.MEETING.artifact, PredicateName.SCHEDULED_AT, UnknownReason.INSUFFICIENT),
        (),
        1,
        CoverageActionKind.UNKNOWN,
    )
    with pytest.raises(ValueError, match="one reason per question"):
        rules_only_report((conclusion,), w.WORLD.at(w.NOW, RunCondition.all_reachable()))
