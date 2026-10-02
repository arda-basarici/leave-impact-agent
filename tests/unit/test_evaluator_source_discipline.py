"""Source discipline is read off the trace alone: every read counts for the source it was
recorded against by how it ended and who asked, a refused call for none; the model's refused
tool requests are counted over the operations it asked for and apart from the model calls that
ended as a refusal; a completed read with an earlier one's tool and arguments names it; and an
operation that a conforming harness could not have recorded is a finding. The reads of a full
investigation of a sealed scenario carry no finding."""

from collections.abc import Mapping

from leaveimpact.core import (
    AbsentOutcome,
    DefectOutcome,
    ModelCallId,
    ModelCallOutcome,
    ModelCallRecord,
    ModelOrigin,
    Operation,
    OperationId,
    Origin,
    Outcome,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    RunTrace,
    Source,
    UnreachableOutcome,
)
from leaveimpact.evaluator.source_discipline import (
    Ended,
    OperationFinding,
    OperationFindingKind,
    OriginCount,
    RequiredSourceUse,
    SourceDiscipline,
    source_discipline,
)
from tests.unit.reads_fixture import Recorder, reads_of_everything, systems_holding
from tests.unit.throwaway_world import loaded_world

DIGEST = "a" * 64
PREFETCH = PrefetchOrigin()
CALL = ModelCallId("call-1")
MODEL = ModelOrigin(CALL)
NOTHING = RecordsOutcome(())
REFUSED = RefusedCallOutcome("not an id of that kind")

Read = tuple[Origin, str, Source | None, Mapping[str, object], Outcome]


def call(id: str, outcome: ModelCallOutcome) -> ModelCallRecord:
    """A model call that ended as ``outcome``, with nothing reported that the tests read."""
    answered = outcome.answered
    return ModelCallRecord(
        ModelCallId(id),
        "investigator",
        outcome,
        "end_turn" if answered else None,
        40 if answered else None,
        DIGEST,
        None,
        None,
        None if answered else "timeout",
    )


def discipline_of(
    *reads: Read, calls: tuple[ModelCallRecord, ...] | None = None
) -> SourceDiscipline:
    """The discipline of a trace holding ``reads`` in order, after one model call that asked
    for tools unless ``calls`` says otherwise."""
    operations = tuple(
        Operation(OperationId(f"op-{number}"), origin, tool, source, arguments, outcome)
        for number, (origin, tool, source, arguments, outcome) in enumerate(reads, start=1)
    )
    held = (call(CALL, ModelCallOutcome.TOOL_CALLS),) if calls is None else calls
    return source_discipline(RunTrace(held, operations, ()))


def down(source: Source) -> UnreachableOutcome:
    return UnreachableOutcome(source, "no answer after the retries")


def test_a_read_counts_for_its_source_by_how_it_ended_and_who_asked() -> None:
    seen = discipline_of(
        (PREFETCH, "employees", Source.FRAPPE, {}, NOTHING),
        (PREFETCH, "employee", Source.FRAPPE, {"id": "emp_099"}, AbsentOutcome()),
        (MODEL, "employees", Source.FRAPPE, {}, down(Source.FRAPPE)),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, DefectOutcome(Source.JIRA, "issue 1", "no owner")),
        (MODEL, "components", Source.JIRA, {}, down(Source.JIRA)),
        (MODEL, "work_item", Source.JIRA, {"id": "LIA-42"}, REFUSED),
    )
    hr, tracker = seen.tally(Source.FRAPPE), seen.tally(Source.JIRA)
    assert (hr.completed, hr.unreachable, hr.defect) == (
        OriginCount(2, 0),
        OriginCount(0, 1),
        OriginCount(0, 0),
    )
    assert (tracker.completed, tracker.unreachable, tracker.defect) == (
        OriginCount(0, 1),
        OriginCount(0, 1),
        OriginCount(0, 1),
    )
    # The refused call had a source resolved and counts for none: no source was asked.
    assert [row.ended for row in seen.operations][-1] is Ended.REFUSED
    counted = sum(
        tally.completed.total + tally.unreachable.total + tally.defect.total
        for tally in map(seen.tally, Source)
    )
    assert counted + 1 == len(seen.operations)


def test_a_source_is_attempted_when_it_was_asked_and_succeeded_when_it_answered() -> None:
    seen = discipline_of(
        (PREFETCH, "employees", Source.FRAPPE, {}, NOTHING),
        (PREFETCH, "work_items", Source.JIRA, {}, down(Source.JIRA)),
        (MODEL, "document", Source.CORPUS, {"id": "nope"}, REFUSED),
        (
            PREFETCH,
            "event",
            Source.CALENDAR,
            {"id": "event_001"},
            DefectOutcome(Source.CALENDAR, "e", "x"),
        ),
    )
    used = {
        source: (seen.tally(source).attempted, seen.tally(source).succeeded) for source in Source
    }
    assert used[Source.FRAPPE] == (True, True)
    assert used[Source.JIRA] == (True, False)
    assert used[Source.CALENDAR] == (True, False)  # a malformed record: asked, not answered
    assert used[Source.CORPUS] == (False, False)  # only a refused call named it
    # Joined with the sources a key says its answer depends on, in the key's order.
    assert seen.required_source_use((Source.JIRA, Source.FRAPPE, Source.CORPUS)) == (
        RequiredSourceUse(Source.JIRA, attempted=True, succeeded=False),
        RequiredSourceUse(Source.FRAPPE, attempted=True, succeeded=True),
        RequiredSourceUse(Source.CORPUS, attempted=False, succeeded=False),
    )


def test_refused_calls_are_the_models_and_a_refused_prefetch_is_a_harness_finding() -> None:
    seen = discipline_of(
        (MODEL, "work_item", Source.JIRA, {"id": "LIA-42"}, REFUSED),
        (MODEL, "no_such_tool", None, {}, REFUSED),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (PREFETCH, "employee", Source.FRAPPE, {"id": "LIA-42"}, REFUSED),
    )
    assert (seen.refused_by_the_wrapper, seen.model_operations) == (2, 3)
    assert seen.findings == (
        OperationFinding(OperationId("op-4"), OperationFindingKind.REFUSED_PREFETCH),
    )


def test_model_calls_are_counted_by_how_each_ended_apart_from_refused_operations() -> None:
    calls = (
        call(CALL, ModelCallOutcome.TOOL_CALLS),
        call("call-2", ModelCallOutcome.REFUSAL),
        call("call-3", ModelCallOutcome.PROVIDER_FAULT),
        call("call-4", ModelCallOutcome.TOOL_CALLS),
        call("call-5", ModelCallOutcome.CLAIMS),
    )
    seen = discipline_of((MODEL, "work_item", Source.JIRA, {"id": "LIA-42"}, REFUSED), calls=calls)
    assert seen.model_calls == (
        (ModelCallOutcome.TOOL_CALLS, 2),
        (ModelCallOutcome.CLAIMS, 1),
        (ModelCallOutcome.TEXT, 0),
        (ModelCallOutcome.REFUSAL, 1),
        (ModelCallOutcome.INVALID_OUTPUT, 0),
        (ModelCallOutcome.PROVIDER_FAULT, 1),
    )
    # One model call ended as a refusal; one tool request was refused. Different things.
    assert seen.refused_by_the_wrapper == 1
    # A rules-only trace calls no model and every kind is still there, at zero.
    assert all(count == 0 for _, count in discipline_of(calls=()).model_calls)


def test_a_completed_read_with_an_earlier_ones_tool_and_arguments_names_it() -> None:
    week = {"span": {"start": "2026-09-15", "end": "2026-09-19"}}
    reordered = {"span": {"end": "2026-09-19", "start": "2026-09-15"}}
    other_week = {"span": {"start": "2026-09-22", "end": "2026-09-26"}}
    seen = discipline_of(
        (PREFETCH, "work_items", Source.JIRA, {}, down(Source.JIRA)),
        (PREFETCH, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "leaves_within", Source.FRAPPE, week, NOTHING),
        (MODEL, "leaves_within", Source.FRAPPE, other_week, NOTHING),
        (MODEL, "leaves_within", Source.FRAPPE, reordered, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, NOTHING),
        (MODEL, "work_items", Source.JIRA, {}, down(Source.JIRA)),
    )
    assert [row.repeat_of for row in seen.operations] == [
        None,  # failed: not a completed read
        None,  # the first completed one; the failed attempt before it is not what it repeats
        "op-2",
        None,
        None,  # the same tool over another window
        "op-4",  # the order a caller spelled the keys in says nothing
        "op-2",  # the first such read, however many came between
        None,  # failed again: a failed read repeats nothing
    ]
    assert [row.operation for row in seen.repeats] == ["op-3", "op-6", "op-7"]


def test_an_operation_no_conforming_harness_records_is_a_finding_by_kind() -> None:
    world = loaded_world("golden")
    reads = Recorder(systems_holding(world))
    employees = reads.read("employees")
    documents = [
        planted.entity.id for owner in world.scenarios for planted in owner.owned.documents
    ]
    found = [reads.read("document", {"id": id}) for id in documents[:2]]
    two_documents = RecordsOutcome(
        tuple(outcome.record for outcome in found if isinstance(outcome, RecordOutcome))
    )
    assert len(two_documents.records) == 2
    seen = discipline_of(
        (PREFETCH, "everyone", Source.FRAPPE, {}, NOTHING),
        (PREFETCH, "employees", Source.JIRA, {}, down(Source.JIRA)),
        (PREFETCH, "work_items", Source.FRAPPE, {"id": "emp_001"}, employees),
        (MODEL, "employees", Source.FRAPPE, {}, AbsentOutcome()),
        (MODEL, "search", Source.CORPUS, {"query": "rotation", "limit": 1}, two_documents),
        (MODEL, "search", Source.CORPUS, {"query": "rotation", "limit": 2}, two_documents),
    )
    kinds = OperationFindingKind
    assert seen.findings == (
        OperationFinding(OperationId("op-1"), kinds.UNKNOWN_TOOL),
        # An unreachable outcome recorded against a source its tool does not read.
        OperationFinding(OperationId("op-2"), kinds.SOURCE_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-3"), kinds.SOURCE_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-3"), kinds.RECORD_KIND_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-3"), kinds.ARGUMENTS_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-4"), kinds.CARDINALITY_NOT_THE_TOOLS),
        OperationFinding(OperationId("op-5"), kinds.MORE_THAN_THE_LIMIT),
    )
    # The mismatched reads still count for the source they were recorded against.
    assert seen.tally(Source.JIRA).unreachable == OriginCount(1, 0)


def test_the_reads_of_a_full_investigation_carry_no_finding_and_sum_to_the_trace() -> None:
    world = loaded_world("golden")
    for scenario in world.scenarios[:5]:
        for down_sources in ((), (Source.JIRA,), (Source.CALENDAR,)):
            operations = reads_of_everything(world, scenario, *down_sources)
            seen = source_discipline(RunTrace((), tuple(operations), ()))
            assert seen.findings == ()
            assert seen.repeats == ()
            assert (seen.model_operations, seen.refused_by_the_wrapper) == (0, 0)
            counted = sum(
                tally.completed.total + tally.unreachable.total + tally.defect.total
                for tally in map(seen.tally, Source)
            )
            assert counted == len(operations)
            for source in Source:
                tally = seen.tally(source)
                assert tally.attempted
                assert tally.succeeded == (source not in down_sources)
