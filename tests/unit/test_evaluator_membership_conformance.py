"""Membership conformance over real producers first, then each finding kind cut from a real
export (the outage step, forks 6 and 7 as amended).

The real producers are the outage matrix's benches: the agent under the scripted two-call
turns, the two one-call baselines under their real turns, rules only through its function,
each under every registered condition; every one conforms, the single-shot's query compared
through the shared renderer, full context's enumeration against the level's sealed
membership. The finding kinds are then each provoked by one change to a real export, positions
kept one order, so that the case shows the check and not the fixture: a model read by a
one-call system, the read missing where a dispatch exists, a second read, a read under another
policy, the read after an absent leave, the read after the first intent, the wrong tool, the
wrong arguments (and the same arguments with their keys reordered, which conform), a member
not returned, a document returned twice. The registered values are inputs: without them the
query comparison is not evaluated and every other check runs. The accounting counts the runs
with findings and the ones whose comparison was not evaluated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import pytest

from leaveimpact.core import (
    HarnessOrigin,
    ModelOrigin,
    Operation,
    OperationId,
    RecordsOutcome,
    RunExport,
    Source,
    SystemKind,
    UnreachableOutcome,
)
from leaveimpact.core.query_protocol import LiteralQuery
from leaveimpact.core.run_record import Retrieval, RetrievalKind, System
from leaveimpact.evaluator.membership_conformance import (
    Comparison,
    MembershipConformance,
    MembershipFinding,
    MembershipFindingKind,
    membership_conformance,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from tests.unit.test_agent_outage_matrix import CONDITIONS, bench, condition_name
from tests.unit.throwaway_world import loaded_world

K = MembershipFindingKind
NONE = MembershipConformance(Comparison.NOT_APPLICABLE, Comparison.NOT_APPLICABLE, ())
PROTOCOL, LIMIT = LiteralQuery("handover or coverage"), 10
"""The fixtures' registered single-shot values (``log_histories.inputs``), the ones the bench's
admission froze."""


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def exported(world: SealedWorld, system: str, *down: Source) -> RunExport:
    """The matrix bench's real export of ``system`` assigned ``down``."""
    made = bench(world, system, frozenset(down))
    made.work()
    return made.export()


def conformance(world: SealedWorld, export: RunExport, *, registered: bool = True):
    return membership_conformance(
        world,
        export,
        query_protocol=PROTOCOL if registered else None,
        search_limit=LIMIT if registered else None,
    )


def kinds(result: MembershipConformance) -> list[MembershipFindingKind]:
    return [finding.kind for finding in result.findings]


# --- Mutations of a real export, positions kept one order ------------------------------------


def harness_read_of(export: RunExport) -> Operation:
    (read,) = [op for op in export.trace.operations if isinstance(op.origin, HarnessOrigin)]
    return read


def last_position(export: RunExport) -> int:
    trace = export.trace
    positions = [op.position or 0 for op in trace.operations]
    for call in trace.model_calls:
        for sent in call.dispatches:
            positions.append(sent.intent_position)
            if sent.outcome_position is not None:
                positions.append(sent.outcome_position)
    for count in trace.counting_operations:
        positions.extend(count.positions)
    if trace.finalization_entered is not None:
        positions.append(trace.finalization_entered)
    timing = export.record.timing
    for stamp in (timing.approval_requested, timing.approval_resumed):
        if stamp is not None:
            positions.append(stamp.position)
    return max(positions)


def with_operations(
    export: RunExport,
    operations: Sequence[Operation],
    *,
    hidden: frozenset[OperationId] = frozenset(),
) -> RunExport:
    """``export`` with ``operations`` as its trace's, every dispatch's input reads kept to
    the ids that remain and were not ``hidden`` from the model."""
    ids = {op.id for op in operations} - hidden
    calls = tuple(
        replace(
            call,
            dispatches=tuple(
                replace(sent, input_reads=tuple(r for r in sent.input_reads if r in ids))
                for sent in call.dispatches
            ),
        )
        for call in export.trace.model_calls
    )
    return replace(
        export, trace=replace(export.trace, operations=tuple(operations), model_calls=calls)
    )


def with_read(export: RunExport, read: Operation, *, shown: bool = True) -> RunExport:
    """``export`` with its harness read replaced by ``read``, in the read's place; not among
    the dispatch's input reads when not ``shown``."""
    operations = [
        read if op.id == harness_read_of(export).id else op for op in export.trace.operations
    ]
    hidden: frozenset[OperationId] = frozenset() if shown else frozenset({read.id})
    return with_operations(export, operations, hidden=hidden)


def appended(export: RunExport, operation: Operation) -> RunExport:
    """``export`` with ``operation`` logged after every event, under a fresh id."""
    added = replace(operation, id=OperationId("op-added"), position=last_position(export) + 1)
    return with_operations(export, (*export.trace.operations, added))


def as_system(export: RunExport, kind: SystemKind) -> RunExport:
    """``export`` with its record claiming ``kind`` and the retrieval that kind registers; the
    trace is left as the run made it."""
    retrieval = export.record.retrieval
    if kind is not SystemKind.SINGLE_SHOT:
        retrieval = Retrieval(RetrievalKind.NONE, None)
    record = replace(
        export.record, system=System(kind, export.record.system.variant), retrieval=retrieval
    )
    return replace(export, record=record)


# --- The real producers -----------------------------------------------------------------------


@pytest.mark.parametrize("down", CONDITIONS, ids=condition_name)
def test_the_agent_conforms_under_every_condition(
    world: SealedWorld, down: frozenset[Source]
) -> None:
    export = exported(world, "agent", *down)
    assert conformance(world, export) == NONE


@pytest.mark.parametrize("down", CONDITIONS, ids=condition_name)
def test_the_single_shot_conforms_under_every_condition_and_its_query_is_compared(
    world: SealedWorld, down: frozenset[Source]
) -> None:
    """The query the harness rendered is the one the evaluator renders over the same prefetch
    records, the fallback included under the tracker's outage; with no read, under the HR
    outage, there is nothing to compare."""
    export = exported(world, "single_shot", *down)
    result = conformance(world, export)
    assert result.findings == ()
    expected = Comparison.NOT_APPLICABLE if Source.FRAPPE in down else Comparison.EVALUATED
    assert (result.query, result.membership) == (expected, Comparison.NOT_APPLICABLE)
    unregistered = conformance(world, export, registered=False)
    assert unregistered.findings == ()
    if Source.FRAPPE not in down:
        assert unregistered.query is Comparison.NOT_EVALUATED


@pytest.mark.parametrize("down", CONDITIONS, ids=condition_name)
def test_full_context_conforms_under_every_condition_and_its_enumeration_is_compared(
    world: SealedWorld, down: frozenset[Source]
) -> None:
    """Every document of the level once; under the corpus's outage the read returned nothing
    and the comparison does not apply; under the HR outage there is no read."""
    export = exported(world, "full_context", *down)
    result = conformance(world, export)
    assert result.findings == ()
    if Source.FRAPPE in down or Source.CORPUS in down:
        expected = Comparison.NOT_APPLICABLE
    else:
        expected = Comparison.EVALUATED
    assert (result.query, result.membership) == (Comparison.NOT_APPLICABLE, expected)


def test_the_evaluation_carries_the_check_for_every_export(world: SealedWorld) -> None:
    export = exported(world, "single_shot")
    evaluated = evaluate_run(world, export, query_protocol=PROTOCOL, search_limit=LIMIT)
    assert evaluated.metrics.membership.query is Comparison.EVALUATED
    assert evaluate_run(world, export).metrics.membership.query is Comparison.NOT_EVALUATED


# --- Each finding, cut from a real export --------------------------------------------------------


def test_a_model_read_by_a_system_shown_no_read_tool_is_a_finding(world: SealedWorld) -> None:
    """The agent's run, whose model read the leave and an employee, relabelled as each one-call
    system: every model-origin operation is a finding, and the read their dispatch obliges is
    missing. Rules only is not relabelled: its record refuses a model configuration, so no
    valid export of it holds a model-origin operation, and the check's rule for it is the
    same branch."""
    agent = exported(world, "agent")
    by_model = [op.id for op in agent.trace.operations if isinstance(op.origin, ModelOrigin)]
    assert len(by_model) == 2
    for kind in (SystemKind.SINGLE_SHOT, SystemKind.FULL_CONTEXT):
        result = conformance(world, as_system(agent, kind))
        assert kinds(result) == [K.MODEL_READ, K.MODEL_READ, K.MISSING_HARNESS_READ]
        assert [f.operation for f in result.findings] == [*by_model, None]


def test_a_read_missing_where_a_dispatch_exists_is_a_finding_and_none_where_none_does(
    world: SealedWorld,
) -> None:
    export = exported(world, "single_shot")
    without = with_operations(
        export, [op for op in export.trace.operations if op.id != harness_read_of(export).id]
    )
    assert kinds(conformance(world, without)) == [K.MISSING_HARNESS_READ]
    # A run that ended before its call owes no read: the same operations with no dispatch.
    undispatched = replace(
        without,
        record=replace(without.record, cost=None),
        trace=replace(
            without.trace, model_calls=(), counting_operations=(), finalization_entered=None
        ),
    )
    assert conformance(world, undispatched) == NONE


def test_a_second_read_under_the_policy_is_a_finding(world: SealedWorld) -> None:
    export = exported(world, "single_shot")
    result = conformance(world, appended(export, harness_read_of(export)))
    assert kinds(result) == [K.SECOND_HARNESS_READ]
    assert result.findings[0].operation == OperationId("op-added")
    assert result.query is Comparison.EVALUATED


def test_a_read_under_another_policy_is_foreign_and_leaves_the_owed_one_missing(
    world: SealedWorld,
) -> None:
    export = exported(world, "single_shot")
    read = harness_read_of(export)
    foreign = with_read(export, replace(read, origin=HarnessOrigin("another_policy")))
    assert kinds(conformance(world, foreign)) == [K.FOREIGN_HARNESS_READ, K.MISSING_HARNESS_READ]
    # The agent issues no policy: the single-shot's own read is foreign to it.
    agent = appended(exported(world, "agent"), read)
    assert kinds(conformance(world, agent)) == [K.FOREIGN_HARNESS_READ]


def test_a_read_after_an_absent_leave_is_a_finding(world: SealedWorld) -> None:
    """The HR outage's run holds the opening read alone and no dispatch; a harness read logged
    after it is owed by nothing and is a finding, with no count finding beside it."""
    abstained = exported(world, "single_shot", Source.FRAPPE)
    assert len(abstained.trace.operations) == 1 and abstained.trace.model_calls == ()
    read = harness_read_of(exported(world, "single_shot"))
    result = conformance(world, appended(abstained, read))
    assert kinds(result) == [K.READ_AFTER_ABSENT_LEAVE]
    assert result.query is Comparison.NOT_EVALUATED, "no leave, so no query to render"


def test_a_read_after_the_first_intent_is_out_of_order(world: SealedWorld) -> None:
    export = exported(world, "single_shot")
    read = harness_read_of(export)
    moved = replace(read, position=last_position(export) + 1)
    assert kinds(conformance(world, with_read(export, moved, shown=False))) == [K.OUT_OF_ORDER]


def test_the_wrong_tool_is_a_finding_and_ends_the_reads_comparison(world: SealedWorld) -> None:
    export = exported(world, "single_shot")
    read = harness_read_of(export)
    result = conformance(world, with_read(export, replace(read, tool="documents", arguments={})))
    assert kinds(result) == [K.WRONG_TOOL]
    assert result.query is Comparison.NOT_APPLICABLE


def test_the_query_is_compared_in_one_canonical_form(world: SealedWorld) -> None:
    """Another limit is a finding under the registered values and no finding without them;
    the same arguments with their keys in another order conform (the step-6 lesson)."""
    export = exported(world, "single_shot")
    read = harness_read_of(export)
    arguments = dict(read.arguments)
    assert set(arguments) == {"query", "limit"}
    other_limit = with_read(export, replace(read, arguments={**arguments, "limit": LIMIT + 1}))
    assert kinds(conformance(world, other_limit)) == [K.WRONG_ARGUMENTS]
    unregistered = conformance(world, other_limit, registered=False)
    assert unregistered.findings == () and unregistered.query is Comparison.NOT_EVALUATED
    backwards = dict(reversed(list(arguments.items())))
    assert list(backwards) != list(arguments)
    reordered = with_read(export, replace(read, arguments=backwards))
    assert conformance(world, reordered).findings == ()


def test_full_contexts_enumeration_is_held_to_the_levels_membership(world: SealedWorld) -> None:
    """A member not returned and a document returned twice are findings naming the document;
    an argument on the enumeration is a finding; the real enumeration has none."""
    export = exported(world, "full_context")
    read = harness_read_of(export)
    assert isinstance(read.outcome, RecordsOutcome)
    records = read.outcome.records
    members = world.level_documents(export.record.corpus_level)
    assert members is not None and len(records) == len(members) > 2
    dropped = with_read(export, replace(read, outcome=RecordsOutcome(records[1:])))
    result = conformance(world, dropped)
    assert result.findings == (MembershipFinding(K.MEMBERSHIP_MISSING, read.id, records[0].ref),)
    assert result.membership is Comparison.EVALUATED
    doubled = with_read(export, replace(read, outcome=RecordsOutcome((*records, records[0]))))
    assert conformance(world, doubled).findings == (
        MembershipFinding(K.MEMBERSHIP_DUPLICATE, read.id, records[0].ref),
    )
    argued = with_read(export, replace(read, arguments={"limit": 3}))
    assert kinds(conformance(world, argued)) == [K.WRONG_ARGUMENTS]


def test_an_enumeration_that_returned_nothing_is_not_compared(world: SealedWorld) -> None:
    export = exported(world, "full_context", Source.CORPUS)
    assert isinstance(harness_read_of(export).outcome, UnreachableOutcome)
    result = conformance(world, export)
    assert result == NONE

