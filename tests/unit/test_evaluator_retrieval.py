"""A run retrieved a target when a completed read returned a comment or a section that carries
it, whoever asked and through whichever tool; a search that is what its tool declares is a row
with the rank of each target it returned, and one that returned none is a row with no hit.
Beside it, for a graded run, whether the report concluded what the target moves: the two are
kept apart, so a target retrieved without the correct conclusion is told from one never
retrieved."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    EntityKind,
    ModelCallId,
    ModelOrigin,
    Operation,
    OperationId,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    RunCondition,
    Source,
    UnreachableOutcome,
)
from leaveimpact.evaluator.matching import match_claims
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.retrieval import SearchHit, SearchRow, retrieval_of
from leaveimpact.evaluator.retrieval_targets import RetrievalTarget, retrieval_targets
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.source_discipline import OriginKind
from leaveimpact.world import Scenario
from tests.unit.reads_fixture import Recorder, reads_of_everything, systems_holding
from tests.unit.report_fixture import truthful_report, without
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario) -> Answerable:
    oracle = oracle_for(world, scenario, NORMAL)
    assert isinstance(oracle, Answerable)
    return oracle


def a_target_carried_by(
    world: SealedWorld, kind: EntityKind
) -> tuple[Scenario, tuple[RetrievalTarget, ...], RetrievalTarget]:
    """The first scenario with a target a carrier of ``kind`` states and a required row rests
    on, with all its targets and that one."""
    for scenario in world.scenarios:
        targets = retrieval_targets(world, answer(world, scenario))
        for target in targets:
            if target.carriers[0].part.kind is kind and target.moves_a_required_key:
                return scenario, targets, target
    raise AssertionError(f"no target carried by a {kind.value}")


def text_of(world: SealedWorld, target: RetrievalTarget) -> str:
    return world.index.parts[target.carriers[0].part].content.text


def test_over_a_full_read_every_target_is_retrieved_and_over_no_read_none(
    world: SealedWorld,
) -> None:
    seen = 0
    for scenario in world.scenarios:
        targets = retrieval_targets(world, answer(world, scenario))
        everything = retrieval_of(reads_of_everything(world, scenario), targets, None)
        assert all(found.retrieved for found in everything.targets), scenario.spec.id
        # The fixture reads documents by id and has no search to make.
        assert everything.searches == ()
        for found in everything.targets:
            tools = {retrieving.tool for retrieving in found.retrieving}
            assert tools == ({"document"} if found.searchable else {"work_items"})
            assert all(retrieving.rank is None for retrieving in found.retrieving)
        nothing = retrieval_of((), targets, None)
        assert not any(found.retrieved for found in nothing.targets)
        assert [found.target for found in nothing.targets] == list(targets)
        seen += len(targets)
    assert seen == 35


def test_a_comment_is_retrieved_inside_its_ticket_and_is_out_of_a_searchs_reach(
    world: SealedWorld,
) -> None:
    _, targets, shown = a_target_carried_by(world, EntityKind.COMMENT)
    reads = Recorder(systems_holding(world))
    reads.read("work_item", {"id": shown.carriers[0].record.id})
    reads.read("work_items")
    found = next(
        each
        for each in retrieval_of(reads.operations, targets, None).targets
        if each.target == shown
    )
    assert not found.searchable
    # Both reads returned the ticket that holds the comment, and both are kept, in order.
    assert [(r.operation, r.tool, r.carrier) for r in found.retrieving] == [
        ("op-1", "work_item", shown.carriers[0].part),
        ("op-2", "work_items", shown.carriers[0].part),
    ]


def test_a_search_is_a_row_with_the_rank_of_each_target_it_returned(world: SealedWorld) -> None:
    _, targets, stated = a_target_carried_by(world, EntityKind.CLAUSE)
    reads = Recorder(systems_holding(world))
    returned = reads.read("search", {"query": text_of(world, stated)[:60].strip(), "limit": 5})
    reads.read("search", {"query": "no document says this anywhere", "limit": 3})
    assert isinstance(returned, RecordsOutcome)
    document = stated.carriers[0].record
    rank = [record.ref for record in returned.records].index(document) + 1
    asked_by_the_model = replace(reads.operations[0], origin=ModelOrigin(ModelCallId("call-1")))
    run = retrieval_of((asked_by_the_model, reads.operations[1]), targets, None)

    hit, miss = run.searches
    assert (hit.operation, hit.origin, hit.limit, hit.returned) == (
        "op-1",
        OriginKind.MODEL,
        5,
        len(returned.records),
    )
    assert SearchHit(stated.statement, rank) in hit.hits
    assert [each.rank for each in hit.hits] == sorted(each.rank for each in hit.hits)
    # A completed search that returned no target is still a row: the denominator of a hit rate.
    assert miss == SearchRow(OperationId("op-2"), OriginKind.PREFETCH, 3, 0, ())
    found = next(each for each in run.targets if each.target == stated)
    assert found.searchable
    assert [(r.operation, r.origin, r.rank, r.limit) for r in found.retrieving] == [
        ("op-1", OriginKind.MODEL, rank, 5)
    ]


def test_the_rank_is_the_carrying_documents_position_among_the_documents_returned(
    world: SealedWorld,
) -> None:
    _, targets, stated = a_target_carried_by(world, EntityKind.CLAUSE)
    reads = Recorder(systems_holding(world))
    documents = [
        planted.entity.id
        for owner in world.scenarios
        for planted in owner.owned.documents
        if planted.entity.id != stated.carriers[0].record.id
    ]
    by_id = [
        reads.read("document", {"id": id})
        for id in (*documents[:2], stated.carriers[0].record.id)
    ]
    listed = RecordsOutcome(
        tuple(outcome.record for outcome in by_id if isinstance(outcome, RecordOutcome))
    )
    assert len(listed.records) == 3

    def search(arguments: dict[str, object]) -> Operation:
        return Operation(
            OperationId("op-1"), PrefetchOrigin(), "search", Source.CORPUS, arguments, listed
        )

    third = retrieval_of((search({"query": "anything", "limit": 5}),), targets, None)
    assert SearchHit(stated.statement, 3) in third.searches[0].hits
    # Recorded with arguments the tool refuses, it is no search row; what it returned came
    # back all the same, with no rank to give.
    undeclared = retrieval_of((search({"query": "anything", "limit": 0}),), targets, None)
    assert undeclared.searches == ()
    found = next(each for each in undeclared.targets if each.target == stated)
    assert [(r.tool, r.rank, r.limit) for r in found.retrieving] == [("search", None, None)]
    # A search the corpus did not answer retrieved nothing and is the tally's, not a row.
    down = Operation(
        OperationId("op-1"),
        PrefetchOrigin(),
        "search",
        Source.CORPUS,
        {"query": "anything", "limit": 5},
        UnreachableOutcome(Source.CORPUS, "no answer after the retries"),
    )
    failed = retrieval_of((down,), targets, None)
    assert failed.searches == () and not any(each.retrieved for each in failed.targets)


def test_a_target_says_whether_the_report_concluded_what_it_moves(world: SealedWorld) -> None:
    scenario, targets, stated = a_target_carried_by(world, EntityKind.CLAUSE)
    oracle = answer(world, scenario)
    claims = truthful_report(oracle)
    operations = reads_of_everything(world, scenario)

    truthful = retrieval_of(operations, targets, match_claims(oracle, claims))
    for found in truthful.targets:
        # A truthful report concludes every row a target moves; a target that moves only
        # rows no report must hold has no conclusion to check.
        assert found.concluded is (True if found.target.moves_a_required_key else None)

    # One required row the statement moves, left out of the report.
    moved = next(moved for moved in stated.moves if moved.required)
    dropped = next(
        claim for claim in claims if (claim.claim_type, claim.key) == (moved.claim_type, moved.key)
    )
    lacking = without(claims, dropped)
    rows = match_claims(oracle, lacking)
    retrieved_only = next(
        each for each in retrieval_of(operations, targets, rows).targets if each.target == stated
    )
    # Retrieved without the correct conclusion, told from never retrieved by the two flags.
    assert (retrieved_only.retrieved, retrieved_only.concluded) == (True, False)
    neither = next(
        each for each in retrieval_of((), targets, rows).targets if each.target == stated
    )
    assert (neither.retrieved, neither.concluded) == (False, False)
    # Right with nothing read: concluded, and not through anything this run retrieved.
    guessed = retrieval_of((), targets, match_claims(oracle, claims))
    assert all(not each.retrieved for each in guessed.targets)
    assert next(each for each in guessed.targets if each.target == stated).concluded is True
    # A run that was not graded has no conclusion to speak of.
    ungraded = retrieval_of(operations, targets, None)
    assert all(each.concluded is None for each in ungraded.targets)
