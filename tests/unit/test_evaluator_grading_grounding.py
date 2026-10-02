"""A graded and a limited outcome carry what the run's own reads support of its report, and what
those reads returned that the sealed world does not hold that way. Grounding needs no expected
answer, so a limited run has it; it needs a claim set that can be replayed, so a structurally
invalid one does not, and that is recorded as not evaluated. The group's gate is here whole:
a truthful report over a full read is graded correct and grounded end to end."""

from dataclasses import replace

import pytest

from leaveimpact.core import EntityKind, RunCondition, Source
from leaveimpact.core.ids import WorkItemId
from leaveimpact.evaluator.grading import Excluded, Graded, Limited, LimitedReason, grade_run
from leaveimpact.evaluator.grounded import grounded_end_to_end, local_failures
from leaveimpact.evaluator.observed_view import IntegrityFinding, IntegrityKind
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.replay import Standing, UnsupportedReason
from leaveimpact.evaluator.rows import Expectation
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import provider_failed_export, run_export
from tests.unit.reads_fixture import Recorder, full_read, reads_of_everything, systems_holding
from tests.unit.report_fixture import renumbered, truthful_report
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


@pytest.mark.parametrize("down", [(), (Source.JIRA,), (Source.CALENDAR,)], ids=str)
def test_a_truthful_report_over_a_full_read_is_graded_correct_and_grounded_end_to_end(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    condition = NORMAL.without(*down)
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario, condition))
        export = run_export(
            world,
            scenario,
            claims,
            operations=reads_of_everything(world, scenario, *down),
            recorded=condition,
        )
        outcome = grade_run(world, export)
        assert isinstance(outcome, Graded), scenario.spec.id
        assert outcome.condition == condition
        assert (outcome.integrity, outcome.harness_findings) == ((), ())
        # Right: every row expected, nothing unexpected, no finding of any plan check.
        rows = outcome.rows
        every_row = (
            *rows.impacts,
            *rows.constraints,
            *rows.assessments,
            *rows.actions,
            *rows.conflicts,
            *rows.unknowns,
        )
        assert all(row.expectation is not Expectation.UNEXPECTED for row in every_row)
        assert (outcome.oracle_findings, outcome.report_findings) == ((), ())
        # And supported: every claim reproduced by the rules over what the run read.
        assert outcome.grounding is not None
        standings = outcome.grounding.claims
        assert len(standings) == len(claims)
        assert local_failures(standings) == frozenset()
        assert grounded_end_to_end(standings) == {record.claim_id for record in standings}
        assert outcome.grounding.citations == ()  # the truthful report cites nothing


def test_a_right_answer_with_nothing_read_is_graded_correct_and_supported_by_nothing(
    world: SealedWorld,
) -> None:
    # The two questions kept apart: the report is the oracle's own answer, and the run
    # that states it read nothing.
    scenario = world.scenarios[0]
    outcome = grade_run(
        world, run_export(world, scenario, truthful_report(answer(world, scenario)))
    )
    assert isinstance(outcome, Graded)
    assert outcome.oracle_findings == ()
    assert outcome.grounding is not None
    assert all(record.standing is Standing.UNSUPPORTED for record in outcome.grounding.claims)


def test_a_structurally_invalid_claim_set_has_no_grounding_and_keeps_its_integrity_findings(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    claims = truthful_report(answer(world, scenario))
    systems = systems_holding(world)
    foreign = replace(
        next(iter(systems.work.tickets.values())), id=WorkItemId("ticket_999"), comments=()
    )
    systems.work.add_work_item(foreign)
    reads = Recorder(systems)
    full_read(reads, world, scenario)
    outcome = grade_run(
        world,
        run_export(
            world, scenario, (*claims, renumbered(claims[0], 9_999)), operations=reads.operations
        ),
    )
    assert isinstance(outcome, Graded)
    assert not outcome.rows.structurally_valid
    assert outcome.grounding is None  # not evaluated, which is not "nothing grounded"
    assert [finding.kind for finding in outcome.integrity] == [IntegrityKind.UNKNOWN_RECORD]


def test_a_run_shown_something_the_sealed_world_does_not_hold_is_still_graded_and_replayed(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    comment = next(ref for ref in world.index.carried if ref.kind is EntityKind.COMMENT)
    ticket = world.index.parts[comment].parent
    systems = systems_holding(world)
    item = systems.work.tickets[WorkItemId(ticket.id)]
    systems.work.tickets[item.id] = replace(
        item, comments=tuple(replace(each, text="Edited since.") for each in item.comments)
    )
    reads = Recorder(systems)
    full_read(reads, world, scenario)
    claims = truthful_report(answer(world, scenario))
    outcome = grade_run(world, run_export(world, scenario, claims, operations=reads.operations))
    assert isinstance(outcome, Graded)
    assert IntegrityFinding(IntegrityKind.PART_DIFFERS, ticket, comment) in outcome.integrity
    assert outcome.grounding is not None and outcome.rows.structurally_valid


def test_a_limited_run_carries_its_grounding(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    claims = truthful_report(answer(world, scenario))
    # The HR system down for the whole run: no leave, no expected answer, and the report's
    # claims are replayed all the same, each one resting on a leave the run never read.
    export = run_export(
        world,
        scenario,
        claims,
        operations=reads_of_everything(world, scenario, Source.FRAPPE),
        recorded=NORMAL.without(Source.FRAPPE),
    )
    outcome = grade_run(world, export)
    assert isinstance(outcome, Limited)
    assert outcome.reason is LimitedReason.UNREADABLE_LEAVE
    assert outcome.grounding is not None
    reasons = {record.reason for record in outcome.grounding.claims}
    assert UnsupportedReason.LEAVE_NOT_READ in reasons
    assert not any(record.standing is Standing.REPRODUCED for record in outcome.grounding.claims)
    # Structurally invalid, the limited run's grounding is not evaluated either.
    invalid = grade_run(
        world,
        replace(
            export, trace=replace(export.trace, claims=(*claims, renumbered(claims[0], 9_999)))
        ),
    )
    assert isinstance(invalid, Limited)
    assert invalid.grounding is None and invalid.structural_problems


def test_an_excluded_run_is_counted_and_nothing_of_it_is_replayed(world: SealedWorld) -> None:
    outcome = grade_run(world, provider_failed_export(world, world.scenarios[0]))
    assert isinstance(outcome, Excluded)
    assert not hasattr(outcome, "grounding")
