"""The plan checks on a throwaway golden-plan world: a truthful report raises nothing, and validity
and coherence fail apart — a plan naming someone the report wrongly calls viable is coherent and
invalid, a plan short of a clause's count is invalid, and incoherent only when the report cited
the clause; a stranger is named as one; an assignee the report never assessed is the report's own
inconsistency; a cited clause nobody can read makes the check uncheckable, never a pass. Coverage
follows the oracle's outcome for the truth-side count and the report's own for its coherence, and
each omission is counted in one place."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    CandidateAssessment,
    Claim,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    Impact,
    RunCondition,
    Source,
    Verdict,
    ViolationKind,
)
from leaveimpact.core.ids import ClauseId, EmployeeId, claim_id
from leaveimpact.core.plans import Violation
from leaveimpact.evaluator.oracle import Answerable, ImpactTruth, oracle_for
from leaveimpact.evaluator.plan_checks import (
    CheckFamily,
    CheckFinding,
    oracle_checks,
    report_checks,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.report_fixture import of_type, renumbered, swapped, truthful_report, without
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()
SPARE = 9_000


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def expecting(world: SealedWorld, *outcomes: CoverageActionKind) -> tuple[Answerable, ImpactTruth]:
    """The first scenario with an impact whose expected outcome is one of ``outcomes``."""
    for scenario in world.scenarios:
        oracle = answer(world, scenario)
        for truth in oracle.impacts:
            if truth.outcome in outcomes:
                return oracle, truth
    raise AssertionError(f"the throwaway world expects none of {outcomes}")


def coherence(oracle: Answerable, claims: tuple[Claim, ...]) -> tuple[CheckFinding, ...]:
    return report_checks(claims, oracle.scenario, oracle.view, oracle.universe)


def families(findings: tuple[CheckFinding, ...]) -> list[CheckFamily]:
    return [finding.family for finding in findings]


def kinds(findings: tuple[CheckFinding, ...], family: CheckFamily) -> list[ViolationKind]:
    return [
        finding.result.kind
        for finding in findings
        if finding.family is family and isinstance(finding.result, Violation)
    ]


def action_on(report: tuple[Claim, ...], truth: ImpactTruth) -> CoverageAction:
    return next(a for a in of_type(report, CoverageAction) if a.key == truth.key)


def assessment_of(
    report: tuple[Claim, ...], truth: ImpactTruth, employee: EmployeeId
) -> CandidateAssessment:
    return next(
        a
        for a in of_type(report, CandidateAssessment)
        if a.impact_key == truth.key and a.employee_id == employee
    )


# --- A truthful report ----------------------------------------------------------------------


def test_a_truthful_report_raises_nothing_where_the_condition_is_well_posed(
    world: SealedWorld,
) -> None:
    conditions = (NORMAL, NORMAL.without(Source.JIRA), NORMAL.without(Source.CALENDAR))
    for scenario in world.scenarios:
        for condition in conditions:
            oracle = answer(world, scenario, condition)
            report = truthful_report(oracle)
            assert oracle_checks(oracle, report) == (), (scenario.spec.id, condition)
            assert coherence(oracle, report) == (), (scenario.spec.id, condition)


def test_under_a_corpus_outage_the_oracles_own_answer_is_valid_and_not_chain_coherent(
    world: SealedWorld,
) -> None:
    """An open finding, held here so it cannot be forgotten, not a behaviour to keep.

    With the corpus down a sealed constraint's clause is unreadable, so the oracle expects
    no constraint claim, and it expects every candidate unknown on what that clause
    requires. The chain rule admits an unknown about a clause only when the report cites
    the clause as a constraint. So the oracle's own answer, stated as a report, fails the
    chain on every such assessment: under this condition no report can be both what the
    oracle expects and coherent, and no run could name the clause at all, since only the
    corpus says which clause applies. What the truth is under a corpus outage is ruled
    with the outage set, before that condition is graded.
    """
    corpus_down = NORMAL.without(Source.CORPUS)
    incoherent = 0
    for scenario in world.scenarios:
        oracle = answer(world, scenario, corpus_down)
        report = truthful_report(oracle)
        assert oracle_checks(oracle, report) == ()
        findings = coherence(oracle, report)
        assert set(families(findings)) <= {CheckFamily.CHAIN}
        # Exactly the scenarios whose key seals a constraint the outage leaves unread.
        assert bool(findings) == bool(scenario.key.constraints and oracle.impacts), scenario.spec.id
        incoherent += bool(findings)
    assert incoherent


def test_the_checks_refuse_a_structurally_invalid_claim_set(world: SealedWorld) -> None:
    oracle = answer(world, world.scenarios[0])
    report = truthful_report(oracle)
    twice = (*report, renumbered(of_type(report, Impact)[0], SPARE))
    with pytest.raises(ValueError, match="not well-formed"):
        oracle_checks(oracle, twice)
    with pytest.raises(ValueError, match="not well-formed"):
        coherence(oracle, twice)


# --- Validity against coherence -------------------------------------------------------------


def test_a_plan_naming_someone_the_report_wrongly_calls_viable_is_coherent_and_invalid(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.ASSIGN)
    report = truthful_report(oracle)
    unfit = next(a for a in truth.assessments if a.verdict is Verdict.NON_VIABLE)
    believed = assessment_of(report, truth, unfit.employee_id)
    action = action_on(report, truth)
    mistaken = swapped(
        swapped(report, believed, replace(believed, verdict=Verdict.VIABLE, reasons=())),
        action,
        replace(action, assignee_ids=(unfit.employee_id,)),
    )
    against_truth = oracle_checks(oracle, mistaken)
    assert kinds(against_truth, CheckFamily.ORACLE_PLAN)[0] is ViolationKind.NON_VIABLE_ASSIGNEE
    assert all(finding.impact == truth.key for finding in against_truth)
    # The report agrees with itself: the mistake is the assessment, and its row says so.
    assert coherence(oracle, mistaken) == ()


def test_a_plan_short_of_a_clauses_count_is_invalid_and_incoherent_only_if_it_cited_the_clause(
    world: SealedWorld,
) -> None:
    oracle = next(
        answer(world, s)
        for s in world.scenarios
        if any(t.required > 1 for t in answer(world, s).impacts)
    )
    truth = next(t for t in oracle.impacts if t.required > 1)
    report = truthful_report(oracle)
    action = action_on(report, truth)
    assert len(action.assignee_ids) == truth.required
    short = swapped(report, action, replace(action, assignee_ids=action.assignee_ids[:1]))
    [violation] = [f.result for f in oracle_checks(oracle, short)]
    assert isinstance(violation, Violation)
    assert violation.kind is ViolationKind.INSUFFICIENT_CARDINALITY
    assert violation.clause_id == truth.requirements[0].clause_id
    # It cited the clause and named too few: it contradicts itself.
    assert kinds(coherence(oracle, short), CheckFamily.DECLARED_CONSTRAINT) == [
        ViolationKind.INSUFFICIENT_CARDINALITY
    ]
    # It never found the clause: still invalid, and consistent with what it knew.
    unaware = without(short, *of_type(short, Constraint))
    assert kinds(oracle_checks(oracle, unaware), CheckFamily.ORACLE_PLAN) == [
        ViolationKind.INSUFFICIENT_CARDINALITY
    ]
    assert kinds(coherence(oracle, unaware), CheckFamily.DECLARED_CONSTRAINT) == []


def test_an_assignee_outside_the_organization_is_named_as_a_stranger_once(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.ASSIGN)
    report = truthful_report(oracle)
    action = action_on(report, truth)
    stranger = EmployeeId("emp_999")
    outside = swapped(
        report, action, replace(action, assignee_ids=(*action.assignee_ids, stranger))
    )
    findings = [f for f in oracle_checks(oracle, outside) if f.family is CheckFamily.ORACLE_PLAN]
    [named] = findings
    assert named.people == (stranger,) and named.result == (
        "emp_999 is assigned and is not in the organization"
    )
    # The report holds no assessment of the stranger either, which is its own inconsistency.
    assert ViolationKind.MISSING_ASSESSMENT in kinds(
        coherence(oracle, outside), CheckFamily.DECLARED_CONSTRAINT
    )


def test_an_assignee_the_report_never_assessed_is_incoherent_and_not_invalid(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.ASSIGN)
    report = truthful_report(oracle)
    assignee = action_on(report, truth).assignee_ids[0]
    silent = without(report, assessment_of(report, truth, assignee))
    # The person is viable in truth, so the plan is valid.
    assert oracle_checks(oracle, silent) == ()
    findings = coherence(oracle, silent)
    # Nobody the report assessed is assigned, so the plan names no viable person either.
    assert kinds(findings, CheckFamily.DECLARED_CONSTRAINT) == [
        ViolationKind.MISSING_ASSESSMENT,
        ViolationKind.INSUFFICIENT_CARDINALITY,
    ]
    assert CheckFamily.CHAIN in families(findings)


def test_a_cited_clause_nobody_can_read_makes_the_check_uncheckable_and_never_a_pass(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.ASSIGN)
    report = truthful_report(oracle)
    invented = Constraint(
        claim_id=claim_id(SPARE),
        evidence_refs=(),
        clause_id=ClauseId("clause_999"),
        applies_to=truth.key.artifact,
    )
    [finding] = [
        f
        for f in coherence(oracle, (*report, invented))
        if f.family is CheckFamily.DECLARED_CONSTRAINT
    ]
    assert finding.uncheckable and finding.impact == truth.key
    assert isinstance(finding.result, str) and "clause_999" in finding.result
    # A real clause whose source is down is uncheckable the same way.
    scenario = next(s for s in world.scenarios if s.key.constraints)
    corpus_down = answer(world, scenario, NORMAL.without(Source.CORPUS))
    remaining = corpus_down.impacts[0]
    sealed = next(c for c in scenario.key.constraints if c.applies_to == remaining.key.artifact)
    degraded = truthful_report(corpus_down)
    action = action_on(degraded, remaining)
    assigning = replace(
        action,
        action=CoverageActionKind.ASSIGN,
        assignee_ids=(corpus_down.universe[0],),
        derived_from_claim_ids=(),
    )
    cited = Constraint(
        claim_id=claim_id(SPARE),
        evidence_refs=(),
        clause_id=sealed.clause_id,
        applies_to=sealed.applies_to,
    )
    unreadable = [
        f
        for f in coherence(corpus_down, (*swapped(degraded, action, assigning), cited))
        if f.family is CheckFamily.DECLARED_CONSTRAINT
    ]
    assert [f.uncheckable for f in unreadable] == [True]


def test_an_unknown_assessment_with_nothing_behind_it_is_a_chain_finding(
    world: SealedWorld,
) -> None:
    oracle = next(answer(world, s) for s in world.scenarios if answer(world, s).unknowns)
    report = truthful_report(oracle)
    unknown = next(a for a in of_type(report, CandidateAssessment) if a.verdict is Verdict.UNKNOWN)
    unsupported = swapped(report, unknown, replace(unknown, derived_from_claim_ids=()))
    [finding] = [f for f in coherence(oracle, unsupported) if f.family is CheckFamily.CHAIN]
    assert finding.impact is None
    assert finding.result == f"{unknown.claim_id} is unknown but derives from no unknown claim"


# --- Coverage -------------------------------------------------------------------------------


def test_where_the_truth_concludes_about_everyone_an_unassessed_colleague_is_counted_once(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.UNCOVERED)
    report = truthful_report(oracle)
    colleague = next(e for e in oracle.universe if e not in truth.probe)
    skipped = without(report, assessment_of(report, truth, colleague))
    [against_truth] = oracle_checks(oracle, skipped)
    assert against_truth.family is CheckFamily.ORACLE_COVERAGE
    assert (against_truth.impact, against_truth.people) == (truth.key, (colleague,))
    # The report itself says uncovered, so its own conclusion is unentitled too.
    [own] = coherence(oracle, skipped)
    assert (own.family, own.people) == (CheckFamily.REPORT_COVERAGE, (colleague,))
    # A probed candidate left out is a recall miss on its row and no coverage finding.
    probed = assessment_of(report, truth, truth.probe[0])
    assert oracle_checks(oracle, without(report, probed)) == ()


def test_oracle_coverage_holds_whatever_action_the_report_chose(world: SealedWorld) -> None:
    oracle, truth = expecting(world, CoverageActionKind.UNCOVERED, CoverageActionKind.UNKNOWN)
    report = truthful_report(oracle)
    kept = {*truth.probe}
    someone = truth.probe[0]
    action = action_on(report, truth)
    # A report that assigns somebody and assesses only the probe set: the wrong action does
    # not lift the burden the right one carries.
    assessments = [
        a
        for a in of_type(report, CandidateAssessment)
        if a.impact_key == truth.key and a.employee_id not in kept
    ]
    hasty = swapped(
        without(report, *assessments),
        action,
        replace(
            action,
            action=CoverageActionKind.ASSIGN,
            assignee_ids=(someone,),
            derived_from_claim_ids=(),
        ),
    )
    coverage = [f for f in oracle_checks(oracle, hasty) if f.family is CheckFamily.ORACLE_COVERAGE]
    [finding] = coverage
    assert len(finding.people) == len(oracle.universe) - len(truth.probe)
    # Its own action is an assign, which quantifies over nobody: no report-coverage finding.
    assert CheckFamily.REPORT_COVERAGE not in families(coherence(oracle, hasty))


def test_a_report_that_concludes_uncovered_without_looking_is_unentitled_to_it(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.ASSIGN)
    report = truthful_report(oracle)
    action = action_on(report, truth)
    outside = [
        a
        for a in of_type(report, CandidateAssessment)
        if a.impact_key == truth.key and a.employee_id not in truth.probe
    ]
    gave_up = swapped(
        without(report, *outside),
        action,
        replace(action, action=CoverageActionKind.UNCOVERED, assignee_ids=()),
    )
    # The truth expects an assign, a conclusion about its assignees only: no oracle coverage.
    assert CheckFamily.ORACLE_COVERAGE not in families(oracle_checks(oracle, gave_up))
    own = [f for f in coherence(oracle, gave_up) if f.family is CheckFamily.REPORT_COVERAGE]
    [finding] = own
    assert finding.impact == truth.key and len(finding.people) == len(outside)
