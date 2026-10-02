"""Citations on three independent axes: whether the sealed world holds what is cited, whether
the run read it, and whether the claim's proof rests on it. A report citing exactly its
proofs' witnesses resolves, is retrieved and is used throughout; one citing nothing has no
citation to judge; and each axis is shown to fail alone."""

from collections.abc import Sequence
from dataclasses import replace

import pytest

from leaveimpact.core import (
    SOURCE_BY_TARGET_KIND,
    CandidateAssessment,
    Claim,
    ClaimType,
    Consulted,
    CoverageAction,
    CoverageActionKind,
    EntityKind,
    EntityRef,
    EvidenceRef,
    Impact,
    KindSlice,
    Operation,
    RecordSlice,
    RunCondition,
    SliceStatus,
    Source,
    Verdict,
    employee_ref,
    leave_ref,
)
from leaveimpact.core.ids import claim_id
from leaveimpact.evaluator.citations import (
    CitationRecord,
    citable_witnesses,
    cited_witnesses,
    judge_citations,
)
from leaveimpact.evaluator.observed_view import observe
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.replay import ClaimGrounding, Standing, replay
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import run_export
from tests.unit.reads_fixture import reads_of_everything
from tests.unit.report_fixture import citing, of_type, swapped, truthful_report
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def judged(
    world: SealedWorld,
    scenario: Scenario,
    claims: Sequence[Claim],
    operations: Sequence[Operation],
) -> tuple[CitationRecord, ...]:
    export = run_export(world, scenario, claims, operations=operations)
    observed = observe(world.index, export)
    groundings = replay(
        observed, world.index, export.trace.claims, scenario.spec.reference_timezone
    )
    return judge_citations(export.trace.claims, groundings, observed, world.index)


def cite(target: EntityRef) -> tuple[EvidenceRef, ...]:
    return (EvidenceRef(SOURCE_BY_TARGET_KIND[target.kind], target),)


def citing_report(
    world: SealedWorld, scenario: Scenario, operations: Sequence[Operation], *down: Source
) -> tuple[Claim, ...]:
    """The truthful report of ``scenario`` with each claim citing its own proof's witnesses."""
    claims = truthful_report(answer(world, scenario, NORMAL.without(*down)))
    export = run_export(world, scenario, claims, operations=operations)
    groundings = replay(
        observe(world.index, export),
        world.index,
        export.trace.claims,
        scenario.spec.reference_timezone,
    )
    return citing(export.trace.claims, groundings)


# --- The whole report ----------------------------------------------------------------------------


@pytest.mark.parametrize("down", [(), (Source.JIRA,), (Source.CALENDAR,)], ids=str)
def test_a_report_citing_its_proofs_witnesses_resolves_is_retrieved_and_is_used(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    total = 0
    for scenario in world.scenarios:
        operations = reads_of_everything(world, scenario, *down)
        records = judged(
            world, scenario, citing_report(world, scenario, operations, *down), operations
        )
        for record in records:
            assert (record.resolves, record.retrieved, record.used) == (True, True, True), (
                scenario.spec.id,
                record,
            )
        total += len(records)
    assert total > 0


def test_a_report_that_cites_nothing_has_no_citation_to_judge(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    claims = truthful_report(answer(world, scenario))
    assert judged(world, scenario, claims, reads_of_everything(world, scenario)) == ()


# --- Each axis alone -----------------------------------------------------------------------------


def one_claim(
    world: SealedWorld, scenario: Scenario, kind: type[Claim]
) -> tuple[tuple[Claim, ...], Claim]:
    claims = truthful_report(answer(world, scenario))
    return claims, of_type(claims, kind)[0]


def judged_with(
    world: SealedWorld,
    scenario: Scenario,
    claims: Sequence[Claim],
    claim: Claim,
    target: EntityRef,
    operations: Sequence[Operation],
) -> CitationRecord:
    cited = replace(claim, evidence_refs=cite(target))
    (record,) = judged(world, scenario, swapped(claims, claim, cited), operations)
    return record


def test_a_citation_of_a_sealed_record_the_run_never_read_resolves_and_no_more(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    claims, impact = one_claim(world, scenario, Impact)
    assert isinstance(impact, Impact)
    without_the_tickets = [
        operation
        for operation in reads_of_everything(world, scenario)
        if operation.tool != "work_items"
    ]
    ticket = next(ref for ref in world.index.records if ref.kind is EntityKind.WORK_ITEM)
    record = judged_with(world, scenario, claims, impact, ticket, without_the_tickets)
    assert (record.resolves, record.retrieved, record.used) == (True, False, None)


def test_a_citation_of_an_id_nothing_holds_does_not_resolve(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    claims, impact = one_claim(world, scenario, Impact)
    nobody = EntityRef(EntityKind.EMPLOYEE, "emp_999")
    record = judged_with(
        world, scenario, claims, impact, nobody, reads_of_everything(world, scenario)
    )
    assert (record.resolves, record.retrieved, record.used) == (False, False, None)


def test_a_record_read_and_no_part_of_the_proof_is_retrieved_and_unused(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    claims, impact = one_claim(world, scenario, Impact)
    assert isinstance(impact, Impact)
    # An impact's proof is about its artifact and the leave: a colleague's HR record was
    # read, by the enumeration, and has no part in it.
    bystander = next(
        employee_ref(e.id)
        for e in world.org.employees
        if e.id != scenario.investigated_leave.employee_id
    )
    record = judged_with(
        world, scenario, claims, impact, bystander, reads_of_everything(world, scenario)
    )
    assert (record.resolves, record.retrieved, record.used) == (True, True, False)


def test_use_is_not_judged_for_a_claim_that_was_not_reproduced(world: SealedWorld) -> None:
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario))
        viable = next(
            (c for c in of_type(claims, CandidateAssessment) if c.verdict is Verdict.VIABLE), None
        )
        if viable is None:
            continue
        wrong = replace(
            viable,
            verdict=Verdict.UNKNOWN,
            evidence_refs=cite(employee_ref(viable.employee_id)),
        )
        (record,) = judged(
            world,
            scenario,
            swapped(claims, viable, wrong),
            reads_of_everything(world, scenario),
        )
        assert (record.resolves, record.retrieved, record.used) == (True, True, None)
        return
    raise AssertionError("no truthful report holds a viable assessment")


def test_a_witnessing_comments_ticket_counts_as_used_and_the_reverse_does_not(
    world: SealedWorld,
) -> None:
    comment = next(ref for ref in world.index.carried if ref.kind is EntityKind.COMMENT)
    ticket = world.index.parts[comment].parent
    (fact,) = world.index.carried[comment]
    for scenario in world.scenarios:
        operations = reads_of_everything(world, scenario)
        claims = citing_report(world, scenario, operations)
        resting = next(
            (
                c
                for c in of_type(claims, CandidateAssessment)
                if c.employee_id == fact.subject.id
                and comment in {evidence.target for evidence in c.evidence_refs}
            ),
            None,
        )
        if resting is None:
            continue
        # The skill is shown by the comment: citing the ticket it is read inside is a use.
        by_its_ticket = replace(resting, evidence_refs=cite(ticket))
        (record,) = [
            r
            for r in judged(world, scenario, swapped(claims, resting, by_its_ticket), operations)
            if r.claim_id == resting.claim_id
        ]
        assert record.used is True
        return
    raise AssertionError("no assessment of the golden plan rests on a comment")


def test_a_cited_comment_supports_no_structured_fact_of_its_ticket(world: SealedWorld) -> None:
    # The reverse of the rule above. A proof that holds the ticket's own record, as a
    # negative about its fields does, is cited by the ticket and not by a comment on it.
    comment = next(ref for ref in world.index.carried if ref.kind is EntityKind.COMMENT)
    ticket = world.index.parts[comment].parent
    on_the_record = ClaimGrounding(
        claim_id(1),
        ClaimType.IMPACT,
        Standing.REPRODUCED,
        proof=(Consulted(RecordSlice(ticket), SliceStatus.COVERED),),
    )
    by_id = {on_the_record.claim_id: on_the_record}
    assert cited_witnesses(on_the_record, by_id, world.index) == {ticket}
    on_the_comment = replace(on_the_record, proof=tuple(world.index.carried[comment]))
    assert cited_witnesses(on_the_comment, by_id, world.index) == {comment, ticket}
    # An enumeration that closed a negative, and a source left unclosed, name no record.
    every_ticket = KindSlice(EntityKind.WORK_ITEM)
    unnamed = replace(
        on_the_record,
        proof=(
            Consulted(every_ticket, SliceStatus.COVERED),
            Consulted(KindSlice(EntityKind.DOCUMENT), SliceStatus.UNCLOSABLE, waived=True),
        ),
    )
    assert citable_witnesses(unnamed) == frozenset()


def test_an_action_has_no_witnesses_of_its_own_and_may_cite_its_premises(
    world: SealedWorld,
) -> None:
    for scenario in world.scenarios:
        operations = reads_of_everything(world, scenario)
        claims = citing_report(world, scenario, operations)
        assign = next(
            (c for c in of_type(claims, CoverageAction) if c.action is CoverageActionKind.ASSIGN),
            None,
        )
        if assign is None:
            continue
        assert assign.evidence_refs == ()
        export = run_export(world, scenario, claims, operations=operations)
        groundings = replay(
            observe(world.index, export),
            world.index,
            export.trace.claims,
            scenario.spec.reference_timezone,
        )
        own = next(g for g in groundings if g.claim_id == assign.claim_id)
        assert citable_witnesses(own) == frozenset()
        # Citing a witness of an assessment the action rests on is a use of it.
        beneath = {
            target
            for premise in own.premises
            for target in citable_witnesses(next(g for g in groundings if g.claim_id == premise))
        }
        assert beneath
        cited = replace(assign, evidence_refs=cite(sorted(beneath, key=lambda ref: ref.id)[0]))
        (record,) = [
            r
            for r in judged(world, scenario, swapped(claims, assign, cited), operations)
            if r.claim_id == assign.claim_id
        ]
        assert (record.resolves, record.retrieved, record.used) == (True, True, True)
        # The assignee's own HR record is no witness unless a criterion asked it: read, by
        # the enumeration, and not what this plan rests on.
        bystander = next(
            employee_ref(e.id)
            for e in world.org.employees
            if employee_ref(e.id)
            not in cited_witnesses(own, {g.claim_id: g for g in groundings}, world.index)
        )
        aside = replace(assign, evidence_refs=cite(bystander))
        (unused,) = [
            r
            for r in judged(world, scenario, swapped(claims, assign, aside), operations)
            if r.claim_id == assign.claim_id
        ]
        assert (unused.retrieved, unused.used) == (True, False)
        return
    raise AssertionError("no truthful report assigns anyone")


def test_an_impact_and_a_deadlines_assessment_rest_on_the_leave_record(
    world: SealedWorld,
) -> None:
    # Who is leaving and when is read off the leave record, so that record is a witness
    # of every impact, and of an assessment whose window is the leave's span (the batch
    # review of group C).
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario))
        impact = next(
            (c for c in of_type(claims, Impact) if c.artifact.kind is EntityKind.WORK_ITEM), None
        )
        if impact is None:
            continue
        operations = reads_of_everything(world, scenario)
        leave = leave_ref(impact.leave_id)
        record = judged_with(world, scenario, claims, impact, leave, operations)
        assert (record.resolves, record.retrieved, record.used) == (True, True, True)
        assessment = next(
            c for c in of_type(claims, CandidateAssessment) if c.impact_key == impact.key
        )
        record = judged_with(world, scenario, claims, assessment, leave, operations)
        assert record.used is True
        return
    raise AssertionError("no truthful report holds an impact on a work item")


def test_a_contradicted_premise_lends_no_witness_to_the_claim_that_rests_on_it(
    world: SealedWorld,
) -> None:
    # The batch review of group C: an assessment falsely says viable, an action assigns
    # that person and cites the very record that contradicts the assessment. The action
    # is the plan rule over the report's own assessments, so it is reproduced; the
    # evidence it cites is what the rules hold against its premise, and is not its support.
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario))
        assign = next(
            (c for c in of_type(claims, CoverageAction) if c.action is CoverageActionKind.ASSIGN),
            None,
        )
        truthful = next(
            (
                c
                for c in of_type(claims, CandidateAssessment)
                if assign is not None
                and c.impact_key == assign.impact_key
                and c.verdict is Verdict.NON_VIABLE
            ),
            None,
        )
        if assign is None or truthful is None:
            continue
        operations = reads_of_everything(world, scenario)
        export = run_export(world, scenario, claims, operations=operations)
        groundings = replay(
            observe(world.index, export),
            world.index,
            export.trace.claims,
            scenario.spec.reference_timezone,
        )
        held = next(g for g in groundings if g.claim_id == truthful.claim_id)
        against = sorted(citable_witnesses(held), key=lambda ref: ref.id)[0]
        falsely = replace(truthful, verdict=Verdict.VIABLE, reasons=())
        acting = replace(
            assign, assignee_ids=(truthful.employee_id,), evidence_refs=cite(against)
        )
        report = swapped(swapped(claims, truthful, falsely), assign, acting)
        export = run_export(world, scenario, report, operations=operations)
        observed = observe(world.index, export)
        groundings = replay(
            observed, world.index, export.trace.claims, scenario.spec.reference_timezone
        )
        by_id = {g.claim_id: g for g in groundings}
        assert by_id[falsely.claim_id].standing is Standing.CONTRADICTED
        assert by_id[acting.claim_id].standing is Standing.REPRODUCED
        (record,) = judge_citations(export.trace.claims, groundings, observed, world.index)
        assert (record.claim_id, record.retrieved, record.used) == (acting.claim_id, True, False)
        # Nothing is lent by a claim that was not reproduced, itself included.
        assert cited_witnesses(by_id[falsely.claim_id], by_id, world.index) == frozenset()
        return
    raise AssertionError("no truthful report both assigns and holds a non-viable candidate")
