"""What the replay's records add up to: a claim is grounded end to end when it and every
premise under it are reproduced, strictly so when nothing in that chain stood without a source
no read can close, and the failures are counted where they start. One wrong constraint is one
root however many claims rest on it."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    ClaimType,
    Consulted,
    EntityKind,
    KindSlice,
    RunCondition,
    SliceStatus,
    Source,
    Unknown,
    UnknownReason,
)
from leaveimpact.core.ids import ClaimId, claim_id
from leaveimpact.evaluator.grounded import (
    grounded_end_to_end,
    local_failures,
    strictly_grounded,
    unclosed_slices,
)
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.replay import ClaimGrounding, Standing, UnsupportedReason
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.reads_fixture import reads_of_everything
from tests.unit.replay_fixture import replayed
from tests.unit.report_fixture import of_type, swapped, truthful_report
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()
THE_CORPUS = KindSlice(EntityKind.DOCUMENT)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


def record(number: int, *premises: int, standing: Standing = Standing.REPRODUCED) -> ClaimGrounding:
    reason = UnsupportedReason.NOT_CONCLUDED if standing is Standing.UNSUPPORTED else None
    return ClaimGrounding(
        claim_id(number),
        ClaimType.CANDIDATE_ASSESSMENT,
        standing,
        reason,
        premises=tuple(claim_id(premise) for premise in premises),
    )


def rests_on_the_corpus(r: ClaimGrounding, by_id: dict[ClaimId, ClaimGrounding]) -> bool:
    """Whether ``r``, or any claim under it, stood without a source no read can close."""
    return bool(unclosed_slices(r)) or any(
        rests_on_the_corpus(by_id[premise], by_id) for premise in r.premises
    )


def test_a_failure_is_counted_where_it_starts_and_felt_by_everything_above_it() -> None:
    # 1 fails; 2 and 3 rest on it, 4 on 3; 5 stands alone.
    records = (
        record(1, standing=Standing.CONTRADICTED),
        record(2, 1),
        record(3, 1),
        record(4, 3),
        record(5),
    )
    assert local_failures(records) == {claim_id(1)}
    assert grounded_end_to_end(records) == {claim_id(5)}


def test_a_premise_the_report_lacks_is_a_failure_of_the_claim_that_needed_it(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    claims = truthful_report(answer(world, scenario))
    impact = claims[0]
    records = tuple(
        replayed(
            world,
            scenario,
            tuple(c for c in claims if c is not impact),
            reads_of_everything(world, scenario),
        ).values()
    )
    orphans = {r.claim_id for r in records if r.missing_premises}
    assert orphans
    assert all(r.standing is Standing.REPRODUCED for r in records)
    assert local_failures(records) == orphans
    assert not orphans & grounded_end_to_end(records)


def test_a_truthful_report_over_a_full_read_is_grounded_end_to_end(world: SealedWorld) -> None:
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario))
        records = tuple(
            replayed(world, scenario, claims, reads_of_everything(world, scenario)).values()
        )
        assert local_failures(records) == frozenset()
        assert grounded_end_to_end(records) == {r.claim_id for r in records}


def test_the_strict_reading_fails_only_where_the_corpus_was_left_unclosed(
    world: SealedWorld,
) -> None:
    strict = operational = 0
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario))
        records = tuple(
            replayed(world, scenario, claims, reads_of_everything(world, scenario)).values()
        )
        by_id = {r.claim_id: r for r in records}
        strictly = strictly_grounded(records)
        operational += len(records)
        strict += len(strictly)
        for r in records:
            # The one source no read can close is the corpus, and a claim is outside the
            # strict reading exactly when something under it stood without it.
            assert set(unclosed_slices(r)) <= {THE_CORPUS}
            assert (r.claim_id not in strictly) == rests_on_the_corpus(r, by_id)
    # Both readings from one replay: the strict one is smaller and not empty.
    assert 0 < strict < operational


def test_an_answer_an_outage_stopped_does_not_rest_on_the_corpus(world: SealedWorld) -> None:
    # With the tracker down every skill question is inaccessible. The corpus is still
    # unclosable, and no answer stood without it, so the strict reading loses nothing.
    down = NORMAL.without(Source.JIRA)
    waived = Consulted(THE_CORPUS, SliceStatus.UNCLOSABLE, waived=True)
    asked = Consulted(THE_CORPUS, SliceStatus.UNCLOSABLE)
    seen_unwaived = False
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario, down))
        records = tuple(
            replayed(
                world, scenario, claims, reads_of_everything(world, scenario, Source.JIRA)
            ).values()
        )
        assert strictly_grounded(records) == grounded_end_to_end(records)
        assert not any(waived in r.proof for r in records)
        seen_unwaived = seen_unwaived or any(asked in r.proof for r in records)
    assert seen_unwaived


def test_one_wrong_unknown_is_one_root_and_every_claim_resting_on_it_is_ungrounded(
    world: SealedWorld,
) -> None:
    for scenario in world.scenarios:
        claims = truthful_report(answer(world, scenario))
        unknowns = of_type(claims, Unknown)
        if not unknowns:
            continue
        unknown = unknowns[0]
        other = next(
            reason
            for reason in (UnknownReason.ABSENT, UnknownReason.INACCESSIBLE)
            if reason is not unknown.reason
        )
        wrong = replace(unknown, reason=other)
        found = replayed(
            world,
            scenario,
            swapped(claims, unknown, wrong),
            reads_of_everything(world, scenario),
        )
        records = tuple(found.values())
        assert local_failures(records) == {wrong.claim_id}
        # The assessments the rules leave unknown on that question are reproduced, each of
        # them, and none is grounded: they rest on an unknown the report misstates.
        resting = {r.claim_id for r in records if wrong.claim_id in r.premises}
        above = {r.claim_id for r in records if resting & set(r.premises)}
        # An action rests on it too where its outcome needs that assessment.
        assert resting
        assert all(found[c].standing is Standing.REPRODUCED for c in found if c.claim_id in resting)
        everyone = {r.claim_id for r in records}
        assert everyone - grounded_end_to_end(records) == {wrong.claim_id} | resting | above
        return
    raise AssertionError("no truthful report holds an unknown")
