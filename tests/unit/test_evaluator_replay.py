"""The grounding replay gives each claim a local standing over what the run read: reproduced
when the rules conclude its payload, contradicted when they conclude another, unsupported with
a typed reason when they cannot conclude. A truthful report over a full read is reproduced
whole, under the normal condition and under each outage that leaves an answer; the same report
over no reads is supported by nothing. Each claim type is then broken one way at a time, and
the premises each replay consumed are named."""

from collections.abc import Callable
from dataclasses import replace

import pytest

from leaveimpact.core import (
    AssessmentKey,
    AssessmentReason,
    CandidateAssessment,
    Claim,
    ClaimType,
    Constraint,
    Consulted,
    CoverageAction,
    CoverageActionKind,
    EntityKind,
    Impact,
    KindSlice,
    PredicateName,
    RunCondition,
    SliceStatus,
    Source,
    SourceConflict,
    Unknown,
    UnknownReason,
    Verdict,
)
from leaveimpact.core.ids import ClauseId, claim_id
from leaveimpact.evaluator.observed_view import observe
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.replay import (
    MissingPremise,
    Standing,
    UnsupportedReason,
    replay,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import run_export
from tests.unit.reads_fixture import reads_of_everything as everything
from tests.unit.replay_fixture import replayed
from tests.unit.report_fixture import of_type, swapped, truthful_report, without
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()
REPRODUCED, CONTRADICTED = Standing.REPRODUCED, Standing.CONTRADICTED
UNSUPPORTED = Standing.UNSUPPORTED


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def holding[T: Claim](
    world: SealedWorld, kind: type[T], wanted: Callable[[T], bool] = lambda _: True
) -> tuple[Scenario, Answerable, tuple[Claim, ...], T]:
    """The first scenario whose truthful report holds a ``kind`` claim that ``wanted`` accepts."""
    for scenario in world.scenarios:
        oracle = answer(world, scenario)
        claims = truthful_report(oracle)
        for claim in of_type(claims, kind):
            if wanted(claim):
                return scenario, oracle, claims, claim
    raise AssertionError(f"no truthful report holds such a {kind.__name__}")


# --- The whole report --------------------------------------------------------------------------


@pytest.mark.parametrize("down", [(), (Source.JIRA,), (Source.CALENDAR,)], ids=str)
def test_a_truthful_report_over_a_full_read_is_reproduced_whole(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    types: set[ClaimType] = set()
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario, NORMAL.without(*down)))
        for claim, record in replayed(
            world, scenario, claims, everything(world, scenario, *down)
        ).items():
            assert record.standing is REPRODUCED, (scenario.spec.id, claim)
            assert record.missing_premises == (), (scenario.spec.id, claim)
            types.add(record.claim_type)
    assert types >= {ClaimType.IMPACT, ClaimType.CANDIDATE_ASSESSMENT, ClaimType.UNKNOWN}


def test_over_no_reads_the_same_report_is_supported_by_nothing(world: SealedWorld) -> None:
    reasons: dict[ClaimType, set[UnsupportedReason | None]] = {}
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario))
        for record in replayed(world, scenario, claims).values():
            assert record.standing is UNSUPPORTED
            reasons.setdefault(record.claim_type, set()).add(record.reason)
    assert reasons == {
        ClaimType.IMPACT: {UnsupportedReason.LEAVE_NOT_READ},
        ClaimType.CANDIDATE_ASSESSMENT: {UnsupportedReason.LEAVE_NOT_READ},
        ClaimType.COVERAGE_ACTION: {UnsupportedReason.LEAVE_NOT_READ},
        ClaimType.CONSTRAINT: {UnsupportedReason.CLAUSE_NOT_READ},
        ClaimType.SOURCE_CONFLICT: {UnsupportedReason.OBSERVATION_NOT_READ},
        ClaimType.UNKNOWN: {UnsupportedReason.UNKNOWN_WITHOUT_QUESTION},
    }


def test_a_structurally_invalid_claim_set_is_not_replayed(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    claims = truthful_report(answer(world, scenario))
    twice = (*claims, claims[0])
    export = run_export(world, scenario)
    with pytest.raises(ValueError, match="not well-formed"):
        replay(observe(world.index, export), world.index, twice, scenario.spec.reference_timezone)


# --- Impacts and constraints ---------------------------------------------------------------------


def test_an_impact_the_leaver_does_not_hold_is_contradicted(world: SealedWorld) -> None:
    scenario, _, claims, impact = holding(
        world, Impact, lambda c: c.artifact.kind is EntityKind.WORK_ITEM
    )
    foreign = next(
        planted.entity
        for other in world.scenarios
        if other is not scenario
        for planted in other.owned.work_items
        if planted.entity.owner_id != scenario.investigated_leave.employee_id
    )
    not_theirs = replace(impact, artifact=replace(impact.artifact, id=foreign.id))
    found = replayed(
        world, scenario, swapped(claims, impact, not_theirs), everything(world, scenario)
    )
    assert found[not_theirs].standing is CONTRADICTED
    assert found[not_theirs].proof  # what the tracker says of that ticket


def test_an_impact_is_open_when_its_source_could_not_be_read(world: SealedWorld) -> None:
    scenario, _, claims, impact = holding(
        world, Impact, lambda c: c.artifact.kind is EntityKind.WORK_ITEM
    )
    record = replayed(world, scenario, claims, everything(world, scenario, Source.JIRA))[impact]
    assert (record.standing, record.reason) == (UNSUPPORTED, UnsupportedReason.NOT_CONCLUDED)


def test_a_constraint_is_what_the_clause_read_as_sealed_is_scoped_to(world: SealedWorld) -> None:
    scenario, _, claims, constraint = holding(world, Constraint)
    full = everything(world, scenario)
    elsewhere = next(
        c.applies_to
        for c in of_type(_every_constraint(world), Constraint)
        if c.applies_to != constraint.applies_to
    )
    moved = replace(constraint, applies_to=elsewhere)
    assert (
        replayed(world, scenario, swapped(claims, constraint, moved), full)[moved].standing
        is CONTRADICTED
    )
    # The clause never read: the run cannot have known what it applies to.
    no_documents = [operation for operation in full if operation.tool != "document"]
    unread = replayed(world, scenario, claims, no_documents)[constraint]
    assert (unread.standing, unread.reason) == (UNSUPPORTED, UnsupportedReason.CLAUSE_NOT_READ)


def _every_constraint(world: SealedWorld) -> list[Claim]:
    return [
        Constraint(
            claim_id=claim_id(1),
            evidence_refs=(),
            clause_id=key.clause_id,
            applies_to=key.applies_to,
        )
        for scenario in world.scenarios
        for key in scenario.key.constraints
    ]


def test_a_cited_clause_that_states_no_requirement_is_contradicted_and_raises_nothing(
    world: SealedWorld,
) -> None:
    scenario, _, claims, action = holding(world, CoverageAction)
    silent = next(
        ClauseId(ref.id)
        for ref in world.index.parts
        if ref.kind is EntityKind.CLAUSE and ClauseId(ref.id) not in world.index.scope
    )
    cited = Constraint(
        claim_id=claim_id(9_999),
        evidence_refs=(),
        clause_id=silent,
        applies_to=action.impact_key.artifact,
    )
    found = replayed(world, scenario, (*claims, cited), everything(world, scenario))
    assert found[cited].standing is CONTRADICTED
    # The rule cannot apply it, so the assessments replay without it and still name it.
    assessments = [
        c for c in of_type(claims, CandidateAssessment) if c.impact_key == action.impact_key
    ]
    assert all(found[each].standing is REPRODUCED for each in assessments)
    assert all(cited.claim_id in found[each].premises for each in assessments)
    # The action's plan cites a clause nobody can read a requirement from.
    assert (found[action].standing, found[action].reason) == (
        UNSUPPORTED,
        UnsupportedReason.PLAN_NOT_READABLE,
    )


# --- Assessments and the unknowns behind them -----------------------------------------------------


def test_an_assessment_the_rules_conclude_otherwise_is_contradicted(world: SealedWorld) -> None:
    scenario, _, claims, viable = holding(
        world, CandidateAssessment, lambda c: c.verdict is Verdict.VIABLE
    )
    wrong = replace(viable, verdict=Verdict.NON_VIABLE, reasons=(AssessmentReason.SKILL,))
    found = replayed(world, scenario, swapped(claims, viable, wrong), everything(world, scenario))
    assert found[wrong].standing is CONTRADICTED
    # The rules conclude viable and the claim stops at unknown: that too is another payload.
    unsure = replace(viable, verdict=Verdict.UNKNOWN)
    found = replayed(world, scenario, swapped(claims, viable, unsure), everything(world, scenario))
    assert found[unsure].standing is CONTRADICTED


def test_a_definite_assessment_the_reads_leave_open_is_unsupported(world: SealedWorld) -> None:
    scenario, _, claims, lacking = holding(
        world, CandidateAssessment, lambda c: c.reasons == (AssessmentReason.SKILL,)
    )
    without_the_tickets = [o for o in everything(world, scenario) if o.tool != "work_items"]
    record = replayed(world, scenario, claims, without_the_tickets)[lacking]
    # Right, as it happens, and asserted beyond what the run read.
    assert (record.standing, record.reason) == (UNSUPPORTED, UnsupportedReason.NOT_CONCLUDED)


def test_an_assessment_rests_on_its_impact_the_clauses_applied_and_its_unknowns(
    world: SealedWorld,
) -> None:
    scenario, _, claims, unknown = holding(
        world, CandidateAssessment, lambda c: c.verdict is Verdict.UNKNOWN
    )
    full = everything(world, scenario)
    found = replayed(world, scenario, claims, full)
    impact = next(c for c in of_type(claims, Impact) if c.key == unknown.impact_key)
    behind = {c.claim_id for c in of_type(claims, Unknown)}
    record = found[unknown]
    assert impact.claim_id in record.premises
    assert behind & set(record.premises)
    assert set(unknown.derived_from_claim_ids) <= set(record.premises)
    # The impact claim dropped: the assessment is still what the rules conclude, and a
    # premise is missing.
    orphaned = replayed(world, scenario, without(claims, impact), full)[unknown]
    assert orphaned.standing is REPRODUCED
    assert orphaned.missing_premises == (MissingPremise(ClaimType.IMPACT, unknown.impact_key),)


def test_an_unknown_is_replayed_against_the_question_the_replay_stopped_on(
    world: SealedWorld,
) -> None:
    scenario, _, claims, unknown = holding(world, Unknown)
    full = everything(world, scenario)
    other = next(
        reason
        for reason in (UnknownReason.ABSENT, UnknownReason.INACCESSIBLE)
        if reason is not unknown.reason
    )
    renamed = replace(unknown, reason=other)
    assert (
        replayed(world, scenario, swapped(claims, unknown, renamed), full)[renamed].standing
        is CONTRADICTED
    )
    # A reason only an agent gives, on a question the rules too leave open.
    agent = replace(unknown, reason=UnknownReason.AMBIGUOUS)
    record = replayed(world, scenario, swapped(claims, unknown, agent), full)[agent]
    assert (record.standing, record.reason) == (
        UNSUPPORTED,
        UnsupportedReason.NON_REPLAYABLE_UNKNOWN_REASON,
    )


def test_an_unknown_about_an_established_fact_is_contradicted_whatever_reason_it_gives(
    world: SealedWorld,
) -> None:
    # The adversarial tier's planted case: a runbook names a stale owner, the tracker
    # resolves it, and a report that stops at "conflicting" is wrong.
    scenario, _, claims, conflict = holding(world, SourceConflict)
    stopped = Unknown(
        claim_id=claim_id(9_998),
        evidence_refs=(),
        subject=conflict.entity,
        required_fact=conflict.predicate,
        reason=UnknownReason.CONFLICTING,
    )
    found = replayed(world, scenario, (*claims, stopped), everything(world, scenario))
    assert found[stopped].standing is CONTRADICTED
    # Over no reads the same subject and fact, single-valued, are the whole question, and
    # an unknown stated as insufficient is what the rules conclude.
    honest = replace(stopped, reason=UnknownReason.INSUFFICIENT)
    assert replayed(world, scenario, (honest,))[honest].standing is REPRODUCED


def test_a_multi_valued_unknown_no_replay_asked_about_is_unsupported(world: SealedWorld) -> None:
    scenario, _, _, unknown = holding(
        world, Unknown, lambda c: c.required_fact is PredicateName.HAS_SKILL
    )
    alone = replayed(world, scenario, (unknown,), everything(world, scenario))[unknown]
    assert (alone.standing, alone.reason) == (
        UNSUPPORTED,
        UnsupportedReason.UNKNOWN_WITHOUT_QUESTION,
    )


# --- Conflicts ------------------------------------------------------------------------------------


def test_a_conflict_is_what_the_view_holds_and_unsupported_when_a_side_was_not_read(
    world: SealedWorld,
) -> None:
    scenario, _, claims, conflict = holding(world, SourceConflict)
    full = everything(world, scenario)
    loser = next(o.value for o in conflict.observations if o.value != conflict.resolved_value)
    wrong = replace(conflict, resolved_value=loser)
    assert (
        replayed(world, scenario, swapped(claims, conflict, wrong), full)[wrong].standing
        is CONTRADICTED
    )
    no_documents = [operation for operation in full if operation.tool != "document"]
    unread = replayed(world, scenario, claims, no_documents)[conflict]
    assert (unread.standing, unread.reason) == (
        UNSUPPORTED,
        UnsupportedReason.OBSERVATION_NOT_READ,
    )


# --- Actions --------------------------------------------------------------------------------------


def test_an_assign_is_the_plan_rule_over_the_reports_own_assessments(world: SealedWorld) -> None:
    scenario, _, claims, assign = holding(
        world, CoverageAction, lambda c: c.action is CoverageActionKind.ASSIGN
    )
    full = everything(world, scenario)
    record = replayed(world, scenario, claims, full)[assign]
    assessed = {
        c.employee_id: c
        for c in of_type(claims, CandidateAssessment)
        if c.impact_key == assign.impact_key
    }
    assert record.proof == ()  # an assignment has no witness of its own
    assert {assessed[e].claim_id for e in assign.assignee_ids} <= set(record.premises)
    non_viable = next(e for e, c in assessed.items() if c.verdict is Verdict.NON_VIABLE)
    bad = replace(assign, assignee_ids=(non_viable,))
    assert (
        replayed(world, scenario, swapped(claims, assign, bad), full)[bad].standing is CONTRADICTED
    )
    # An assignee the report never assessed: a missing premise, never a non-viable one.
    dropped = assessed[assign.assignee_ids[0]]
    orphaned = replayed(world, scenario, without(claims, dropped), full)[assign]
    assert (orphaned.standing, orphaned.reason) == (
        UNSUPPORTED,
        UnsupportedReason.ASSIGNEE_NOT_ASSESSED,
    )
    assert orphaned.missing_premises == (
        MissingPremise(
            ClaimType.CANDIDATE_ASSESSMENT, AssessmentKey(assign.impact_key, dropped.employee_id)
        ),
    )


def test_a_conclusion_about_everyone_needs_everyone_the_run_listed_assessed(
    world: SealedWorld,
) -> None:
    scenario, _, claims, universal = holding(
        world, CoverageAction, lambda c: c.action is not CoverageActionKind.ASSIGN
    )
    full = everything(world, scenario)
    record = replayed(world, scenario, claims, full)[universal]
    everyone = [
        c for c in of_type(claims, CandidateAssessment) if c.impact_key == universal.impact_key
    ]
    assert record.standing is REPRODUCED
    assert {c.claim_id for c in everyone} <= set(record.premises)
    # Who everyone is was read off the enumeration of the employees: its one witness.
    listed = KindSlice(EntityKind.EMPLOYEE)
    assert record.proof == (Consulted(listed, SliceStatus.COVERED),)
    other = next(
        k
        for k in (CoverageActionKind.UNCOVERED, CoverageActionKind.UNKNOWN)
        if k is not universal.action
    )
    wrong = replace(universal, action=other, derived_from_claim_ids=())
    assert (
        replayed(world, scenario, swapped(claims, universal, wrong), full)[wrong].standing
        is CONTRADICTED
    )
    # One colleague unassessed: the conclusion is not about everyone.
    partial = replayed(world, scenario, without(claims, everyone[0]), full)[universal]
    assert (partial.standing, partial.reason) == (
        UNSUPPORTED,
        UnsupportedReason.UNIVERSE_NOT_ASSESSED,
    )
    assert partial.missing_premises == ()  # named by the coverage gap, not here
    assert partial.proof == record.proof
    # The organization never listed: who "everyone" is was not read.
    never_listed = [operation for operation in full if operation.tool != "employees"]
    unlisted = replayed(world, scenario, claims, never_listed)[universal]
    assert (unlisted.standing, unlisted.reason) == (
        UNSUPPORTED,
        UnsupportedReason.UNIVERSE_NOT_READ,
    )
    assert unlisted.proof == (Consulted(listed, SliceStatus.UNREAD),)  # what stopped it
