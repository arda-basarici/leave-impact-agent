"""The plan checks on a throwaway golden-plan world: a truthful report raises nothing, and validity
and coherence fail apart — a plan naming someone the report wrongly calls viable is coherent and
invalid, a plan short of a clause's count is invalid, and incoherent only when the report cited
the clause; a stranger is named as one; an assignee the report never assessed is the report's own
inconsistency; a cited clause nobody can read makes the check uncheckable for an action of any
kind, never a pass. A coverage gap is called for by the oracle's outcome, by the report's own
conclusion, or by both, and one omission is one record: a colleague missing where the two agree is
one gap, and a probed candidate left out is a recall miss where the oracle expects the impact
and a gap where no recall row would hold the omission."""

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
from leaveimpact.evaluator.matching import match_claims
from leaveimpact.evaluator.oracle import Answerable, ImpactTruth, oracle_for, runtime_truth
from leaveimpact.evaluator.plan_checks import (
    CheckFamily,
    CheckFinding,
    CoverageGap,
    coverage_gaps,
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
    return report_checks(claims, oracle.scenario, oracle.view)


def gaps(oracle: Answerable, claims: tuple[Claim, ...]) -> tuple[CoverageGap, ...]:
    return coverage_gaps(claims, oracle.universe, oracle)


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
            assert gaps(oracle, report) == (), (scenario.spec.id, condition)


def test_the_checks_refuse_a_structurally_invalid_claim_set(world: SealedWorld) -> None:
    oracle = answer(world, world.scenarios[0])
    report = truthful_report(oracle)
    twice = (*report, renumbered(of_type(report, Impact)[0], SPARE))
    with pytest.raises(ValueError, match="not well-formed"):
        oracle_checks(oracle, twice)
    with pytest.raises(ValueError, match="not well-formed"):
        coherence(oracle, twice)
    with pytest.raises(ValueError, match="not well-formed"):
        gaps(oracle, twice)


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
    # The report holds no assessment of the stranger either, which is its own inconsistency:
    # the chain's finding, made once, and not repeated by the declared-constraint check.
    within = coherence(oracle, outside)
    assert [f.result for f in within if f.family is CheckFamily.CHAIN] == [
        f"{action.claim_id} assigns emp_999 without a viable assessment"
    ]
    assert kinds(within, CheckFamily.DECLARED_CONSTRAINT) == []


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
    # Two findings, one in each family. The assignee with no assessment is the chain's, said
    # once. And nobody the report assessed viable is assigned, so the count is unmet: the
    # declared-constraint check's, which still counts viable assignees only.
    assert kinds(findings, CheckFamily.DECLARED_CONSTRAINT) == [
        ViolationKind.INSUFFICIENT_CARDINALITY
    ]
    assert [f.result for f in findings if f.family is CheckFamily.CHAIN] == [
        f"{action_on(report, truth).claim_id} assigns {assignee} without a viable assessment"
    ]


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
    # An action that names nobody cites it too, and that is recorded all the same: the
    # clause is resolved before the plan rule is asked anything.
    action = action_on(report, truth)
    for kind in (CoverageActionKind.UNCOVERED, CoverageActionKind.UNKNOWN):
        naming_nobody = replace(action, action=kind, assignee_ids=(), derived_from_claim_ids=())
        [recorded] = [
            f
            for f in coherence(oracle, (*swapped(report, action, naming_nobody), invented))
            if f.family is CheckFamily.DECLARED_CONSTRAINT
        ]
        assert recorded.uncheckable and "clause_999" in str(recorded.result)
    # A real clause whose source is down is uncheckable the same way. No oracle answers
    # under that condition, and the report's own checks need none: the view is enough.
    governed = next(answer(world, s) for s in world.scenarios if answer(world, s).constraints)
    corpus_down = runtime_truth(world, governed.scenario).at(
        governed.scenario.spec.today, NORMAL.without(Source.CORPUS)
    )
    unreadable = [
        f
        for f in report_checks(truthful_report(governed), governed.scenario, corpus_down)
        if f.family is CheckFamily.DECLARED_CONSTRAINT
    ]
    assert unreadable and all(f.uncheckable for f in unreadable)
    assert {f.impact for f in unreadable} == {
        truth.key
        for truth in governed.impacts
        if any(c.applies_to == truth.key.artifact for c in governed.constraints)
    }


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


def test_a_colleague_missing_where_the_oracle_and_the_report_agree_is_one_gap_with_both_causes(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.UNCOVERED)
    report = truthful_report(oracle)
    colleague = next(e for e in oracle.universe if e not in truth.probe)
    skipped = without(report, assessment_of(report, truth, colleague))
    [gap] = gaps(oracle, skipped)
    assert (gap.impact, gap.missing) == (truth.key, (colleague,))
    assert (gap.required_by_oracle, gap.required_by_report) == (True, True)
    # The omission is a gap and nothing else: no finding of either check names it.
    assert oracle_checks(oracle, skipped) == () and coherence(oracle, skipped) == ()


def test_a_probed_candidate_left_out_is_a_gap_only_where_no_recall_row_holds_it(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.UNCOVERED)
    report = truthful_report(oracle)
    probed = assessment_of(report, truth, truth.probe[0])
    silent = without(report, probed)
    # Called for by the oracle and by the report's own uncovered, and no gap: claim matching
    # holds the omission as a missed row.
    assert gaps(oracle, silent) == ()
    [missed] = [row for row in match_claims(oracle, silent).assessments if row.claim_id is None]
    assert missed.key == probed.key
    # With no oracle there is no row, so the gap is the omission's only record.
    [gap] = coverage_gaps(silent, oracle.universe)
    assert (gap.impact, gap.missing) == (truth.key, (truth.probe[0],))
    assert (gap.required_by_oracle, gap.required_by_report) == (False, True)


def test_the_oracle_calls_for_everyone_whatever_action_the_report_chose(
    world: SealedWorld,
) -> None:
    oracle, truth = expecting(world, CoverageActionKind.UNCOVERED, CoverageActionKind.UNKNOWN)
    report = truthful_report(oracle)
    someone = truth.probe[0]
    action = action_on(report, truth)
    # A report that assigns somebody and assesses only the probe set: the wrong action does
    # not lift the burden the right one carries.
    outside = [
        a
        for a in of_type(report, CandidateAssessment)
        if a.impact_key == truth.key and a.employee_id not in truth.probe
    ]
    hasty = swapped(
        without(report, *outside),
        action,
        replace(
            action,
            action=CoverageActionKind.ASSIGN,
            assignee_ids=(someone,),
            derived_from_claim_ids=(),
        ),
    )
    [gap] = gaps(oracle, hasty)
    assert len(gap.missing) == len(oracle.universe) - len(truth.probe)
    # Its own action is an assign, which quantifies over nobody.
    assert (gap.required_by_oracle, gap.required_by_report) == (True, False)


def test_a_report_that_concludes_uncovered_without_looking_calls_for_everyone_itself(
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
    # The truth expects an assign, a conclusion about its assignees only.
    [gap] = gaps(oracle, gave_up)
    assert gap.impact == truth.key and len(gap.missing) == len(outside)
    assert (gap.required_by_oracle, gap.required_by_report) == (False, True)
    # With no oracle to ask (a run with no claim-level answer) the report's own conclusion
    # still calls for everyone.
    [alone] = coverage_gaps(gave_up, oracle.universe)
    assert (alone.missing, alone.required_by_oracle) == (gap.missing, False)


def test_a_gap_names_somebody_and_says_who_called_for_them(world: SealedWorld) -> None:
    oracle, truth = expecting(world, CoverageActionKind.UNCOVERED)
    with pytest.raises(ValueError, match="names at least one unassessed colleague"):
        CoverageGap(truth.key, (), True, False)
    with pytest.raises(ValueError, match="called for by the oracle, the report or both"):
        CoverageGap(truth.key, (oracle.universe[0],), False, False)
