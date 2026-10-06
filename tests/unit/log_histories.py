"""The format fixtures re-expressed as event histories, and a builder for histories by hand.

Test infrastructure. Each history is the log an attempt would hold, event by event with
its stamp, written from the ruling's description of the case and not from any reader: the
reader test folds it and compares the export with the fixture's hand-built one
(``format_fixtures``), which was built before the reader existed and stays independent of
it (the event log step's ruling on placement and acceptance, part 7). The builder assigns
dense positions and timestamps and tracks the current generation, so a history reads as
the table in the rulings file: who appended, what, at which offset.

Response bodies are the provider's Converse objects, as the parse reads them: content
blocks, a stop reason, the usage. A fact payload in the answer's own content is a text
block holding the batch's JSON; a handled fact tool is a ``toolUse`` block of ``state_facts``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from leaveimpact.agent.answer_parse import FACT_TOOL
from leaveimpact.agent.fact_entries import refused_by
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    ApprovalRequested,
    Approved,
    Completed,
    CountKey,
    CountOutcomeLogged,
    CountStarted,
    DispatchIntent,
    DispatchOutcome,
    Event,
    Failed,
    FrozenInputs,
    LoggedEvent,
    LoggedSettlement,
    ModelReadKey,
    OperationEvent,
    OperationResult,
    PrefetchKey,
    Producer,
    Resumed,
    SegmentEnded,
    SegmentStarted,
    WorkerStamp,
    count_id,
)
from leaveimpact.agent.log_transition import Rules
from leaveimpact.core import (
    AbandonmentReason,
    Approver,
    Attribution,
    AttributionKind,
    CallConfiguration,
    CallSetting,
    Caps,
    ClaimAuthor,
    ClientErrorKind,
    CountClientError,
    Counted,
    CountServiceError,
    DefectOutcome,
    Document,
    EstablishedBound,
    FailureCategory,
    InputBoundSite,
    Observed,
    OperationId,
    OperationSite,
    OutageAssignment,
    PrefetchRule,
    RecordOutcome,
    RecordsOutcome,
    Reservation,
    Retrieval,
    RetrievalKind,
    ServiceError,
    Source,
    StatedFact,
    System,
    SystemKind,
    attribution_table_digest,
)
from leaveimpact.core.counting_operations import CountOutcome
from leaveimpact.core.input_bound import CountResult
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.model_calls import CompleteResponse, Observation
from leaveimpact.core.ports.observed import Entity
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_trace import Outcome
from leaveimpact.core.values import Requirement, SkillCriterion
from tests.unit import format_fixtures as cases
from tests.unit import stated_fixture as f

RULES = Rules(cases.TABLE, cases.POLICY)
TABLE_DIGEST = attribution_table_digest(cases.TABLE)
ADMITTER = Producer("admitter")
AUTOMATIC = Producer("policy:automatic")
CONFIGURATION = CallConfiguration(
    "eu.model", (CallSetting("max_tokens", cases.OUTPUT_MAXIMUM), CallSetting("temperature", 0))
)


AGENT = System(SystemKind.AGENT, "reference")


def inputs(*, reservation: int | None, system: System = AGENT) -> FrozenInputs:
    """The frozen inputs every fixture's record states, with ``reservation`` admitted."""
    calls_a_model = system.kind is not SystemKind.RULES_ONLY
    return FrozenInputs(
        run_id="run-12",
        attempt=1,
        context=cases.CONTEXT,
        preregistration_commit=cases.COMMIT,
        system=system,
        retrieval=Retrieval(RetrievalKind.FULL_TEXT if calls_a_model else RetrievalKind.NONE, None),
        caps=Caps(20, 100_000, 2, 5_000, "input_plus_output_cached_included", cases.METHOD),
        model_configurations=((cases.ROLE, CONFIGURATION),) if calls_a_model else (),
        pricing_selections=((cases.ROLE, cases.SELECTION),) if calls_a_model else (),
        counting_identifiers=((cases.ROLE, cases.COUNTING_MODEL),) if calls_a_model else (),
        pricing=cases.BASIS,
        prompt_digests=((cases.ROLE, "system", cases.DIGEST),) if calls_a_model else (),
        tool_surface_digests=((cases.ROLE, cases.DIGEST),) if calls_a_model else (),
        attribution_table=TABLE_DIGEST if calls_a_model else None,
        redispatch=cases.POLICY if calls_a_model else None,
        retry=RetryRule(FailureCategory.INFRASTRUCTURE, 3),
        prefetch_rule=PrefetchRule("prefetch-v1", cases.DIGEST),
        composing_policy=cases.RULES.policy,
        claim_author=ClaimAuthor.RULES,
        parser=refused_by(),
        outage=OutageAssignment(frozenset(), cases.DIGEST),
        corpus_level="base",
        reservation_pico_usd=reservation if calls_a_model else None,
        log_format_version=1,
    )


def settlement_of(reservation: Reservation) -> LoggedSettlement:
    """The settlement a closing event holds, as the fixture's reservation states it."""
    return LoggedSettlement(
        reservation.charged_pico_usd,
        reservation.state,
        reservation.kept_reason,
        reservation.ledger_revision,
    )


# --- The builder -----------------------------------------------------------------------------


@dataclass
class History:
    """A log under construction: events with dense positions, the current generation, and a
    clock that gives each event a distinct timestamp unless one is given."""

    admitted_at: datetime = cases.ADMITTED
    events: list[LoggedEvent] = field(default_factory=list[LoggedEvent])
    generation: int = 0

    def _append(self, envelope: WorkerStamp | Producer, event: Event, at: datetime | None) -> int:
        position = len(self.events) + 1
        stamp = self.admitted_at + timedelta(seconds=position) if at is None else at
        self.events.append(LoggedEvent(position, stamp, envelope, event))
        return position

    def admit(self, frozen: FrozenInputs) -> int:
        return self._append(ADMITTER, Admitted(frozen), self.admitted_at)

    def outside(self, identity: str, event: Event, *, at: datetime | None = None) -> int:
        return self._append(Producer(identity), event, at)

    def claim(self, *, harness: object = None, nonce: str | None = None) -> int:
        self.generation += 1
        revision = cases.REVISION if harness is None else harness
        assert isinstance(revision, type(cases.REVISION))
        event = SegmentStarted(revision, nonce or f"nonce-{self.generation}", "launch-1")
        return self._append(WorkerStamp(self.generation, self.generation, 0), event, None)

    def worker(self, event: Event, *, offset: int, at: datetime | None = None) -> int:
        return self._append(WorkerStamp(self.generation, self.generation, offset), event, at)

    def logged(self) -> tuple[LoggedEvent, ...]:
        return tuple(self.events)


# --- Content helpers -------------------------------------------------------------------------


def key_of(call: str) -> CountKey:
    """The reuse key of ``call``'s one count, as the fixtures bound it."""
    return CountKey(cases.METHOD, cases.COUNTING_MODEL, cases.request_digest(call), 1)


def prefetch(
    ordinal: int, tool: str, source: Source, records: Sequence[Observed[Entity]] = ()
) -> OperationEvent:
    """The prefetch's ``ordinal``-th read, returning ``records``."""
    return OperationEvent(
        PrefetchKey(ordinal), OperationResult(tool, source, {}, RecordsOutcome(tuple(records)))
    )


def document_read(ordinal: int, document: Document) -> OperationEvent:
    held = Observed[Entity](document, Source.CORPUS)
    return OperationEvent(
        PrefetchKey(ordinal),
        OperationResult("document", Source.CORPUS, {"id": document.id}, RecordOutcome(held)),
    )


def model_read(
    call: int, tool_call: str, outcome: Outcome, tool: str = "work_item"
) -> OperationEvent:
    """A read the model asked for in tool call ``tool_call`` of ``call``, as the fixtures ask it."""
    return OperationEvent(
        ModelReadKey(call, tool_call),
        OperationResult(tool, Source.JIRA, {"id": "ticket_042"}, outcome),
    )


def count_start(call: str) -> CountStarted:
    return CountStarted(key_of(call), cases.ROLE)


def count_outcome(
    call: str, outcome: CountOutcome | None = None, reading: CountResult = CountResult.COUNTED
) -> CountOutcomeLogged:
    held = (
        Counted(cases.INPUT_BOUND, f"req-{count_id(key_of(call))}", 100)
        if outcome is None
        else outcome
    )
    return CountOutcomeLogged(key_of(call), held, reading)


def intent(
    call: int, number: int = 1, *, name: str = "call-1", shown: Sequence[str] = ()
) -> DispatchIntent:
    """The intent of dispatch ``number`` of the call ``name`` (its ordinal ``call``)."""
    return DispatchIntent(
        call,
        number,
        cases.ROLE,
        cases.request_digest(name),
        "Converse",
        "eu.model",
        "eu-central-1",
        tuple(OperationId(read) for read in shown),
        EstablishedBound(
            cases.METHOD,
            cases.COUNTING_MODEL,
            cases.request_digest(name),
            cases.INPUT_BOUND,
            count_id(key_of(name)),
        ),
        cases.OUTPUT_MAXIMUM,
        cases.ALLOCATION_TOKENS,
        cases.ALLOCATION,
    )


def outcome(
    call: int,
    number: int,
    observation: Observation,
    read_as: AttributionKind = AttributionKind.BEHAVIOUR,
    *,
    rule: str = "registered-stop-reason",
    response: JsonObject | None = None,
) -> DispatchOutcome:
    return DispatchOutcome(
        call, number, observation, response, Attribution(read_as, rule), None, None
    )


def body(stop_reason: str, *blocks: JsonObject) -> JsonObject:
    """A Converse response with ``blocks`` as its content and the fixtures' reported usage."""
    return {
        "output": {"message": {"role": "assistant", "content": list(blocks)}},
        "stopReason": stop_reason,
        "usage": dict(cases.REPORTED),
        "metrics": {"latencyMs": 840},
    }


def complete(stop_reason: str = "end_turn") -> CompleteResponse:
    return CompleteResponse(stop_reason, 840, 0)


def text(content: str) -> JsonObject:
    return {"text": content}


def tool_use(identifier: str, name: str, arguments: object) -> JsonObject:
    return {"toolUse": {"toolUseId": identifier, "name": name, "input": arguments}}


def entry_of(stated: StatedFact) -> JsonObject:
    """``stated`` as the entry a model would write for it."""
    held: JsonObject = {
        "carrier": stated.carrier.id,
        "predicate": stated.predicate.value,
        "subject": stated.subject.id,
        "value": "" if isinstance(stated.value, Requirement) else str(stated.value),
        "quote": stated.quote,
    }
    if isinstance(stated.value, Requirement):
        held["count"] = stated.value.count
        held["skills"] = [c.skill for c in stated.value.criteria if isinstance(c, SkillCriterion)]
        if stated.target_span is not None:
            held["target_span"] = stated.target_span
    return held


def payload(*entries: object) -> JsonObject:
    return {"facts": list(entries)}


def payload_text(*entries: object) -> JsonObject:
    import json

    return text(json.dumps(payload(*entries)))


# --- The sixteen, as histories ---------------------------------------------------------------

type Build = Callable[[], tuple[LoggedEvent, ...]]

PEOPLE: tuple[Observed[Entity], ...] = (
    Observed[Entity](f.ALICE, Source.FRAPPE),
    Observed[Entity](f.DENIZ, Source.FRAPPE),
)
TICKETS: tuple[Observed[Entity], ...] = (Observed[Entity](f.TICKET, Source.JIRA),)
"""The reads that make the fixtures' admitted facts admissible: Deniz and the ticket holding
Deniz's comment, which the SKILL statement is read from."""


def _closed_completed(
    log: History, reservation: Reservation, *, offset: int = 9_000, terminal: datetime | None = None
) -> None:
    """Request, automatic approval, resume and completion, the segment ending at ``offset``."""
    log.worker(ApprovalRequested((), cases.RULES), offset=offset - 300)
    log.outside(
        AUTOMATIC.identity,
        Approved(Approver.AUTOMATIC, cases.review_payload_digest((), cases.RULES)),
    )
    log.worker(Resumed(), offset=offset - 200)
    log.worker(
        Completed(settlement_of(reservation)),
        offset=offset,
        at=terminal or cases.ADMITTED + timedelta(milliseconds=offset),
    )


def _one_call_prefix(
    log: History, reservation: int, *, reads: Sequence[OperationEvent] = ()
) -> None:
    """Admission, the claim, the prefetch (``reads`` after the empty ticket read), one count."""
    log.admit(inputs(reservation=reservation))
    log.claim()
    log.worker(prefetch(1, "work_items", Source.JIRA), offset=100)
    for ordinal, read in enumerate(reads, start=2):
        log.worker(read, offset=100 + ordinal)
    log.worker(count_start("call-1"), offset=400)
    log.worker(count_outcome("call-1"), offset=500)


def facts_beside_tools() -> tuple[LoggedEvent, ...]:
    expected = cases.facts_beside_tools().record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(
        log,
        expected.pico_usd,
        reads=(
            prefetch(2, "employees", Source.FRAPPE, PEOPLE),
            prefetch(3, "work_items", Source.JIRA, TICKETS),
        ),
    )
    log.worker(intent(1, shown=("prefetch/1",)), offset=600)
    log.worker(
        outcome(
            1,
            1,
            complete("tool_use"),
            response=body(
                "tool_use",
                text("Looking at the ticket."),
                tool_use("tu_1", "work_item", {"id": "ticket_042"}),
                payload_text(entry_of(cases.SKILL)),
            ),
        ),
        offset=1_500,
    )
    log.worker(model_read(1, "tu_1", cases.asked("x", "call-1", 1).outcome), offset=1_700)
    _closed_completed(log, expected)
    return log.logged()


def malformed_batch() -> tuple[LoggedEvent, ...]:
    expected = cases.malformed_batch().record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    truncated = '{"facts": [{"predicate": "has_skill", "subject": "emp_023", "va'
    log.worker(outcome(1, 1, complete(), response=body("end_turn", text(truncated))), offset=1_500)
    _closed_completed(log, expected)
    return log.logged()


def refused_fact() -> tuple[LoggedEvent, ...]:
    expected = cases.refused_fact().record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(
        log,
        expected.pico_usd,
        reads=(
            prefetch(2, "employees", Source.FRAPPE, PEOPLE),
            prefetch(3, "work_items", Source.JIRA, TICKETS),
        ),
    )
    log.worker(intent(1), offset=600)
    unreadable = {
        "predicate": "has_skill",
        "subject": f.DENIZ_REF.id,
        "value": 7,
        "carrier": f.COMMENT_REF.id,
        "quote": f.REMARK,
    }
    misquoted = StatedFact(
        PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, "I led the Kafka migration"
    )
    log.worker(
        outcome(
            1,
            1,
            complete(),
            response=body(
                "end_turn", payload_text(unreadable, entry_of(misquoted), entry_of(cases.SKILL))
            ),
        ),
        offset=1_500,
    )
    _closed_completed(log, expected)
    return log.logged()


def cut_call() -> tuple[LoggedEvent, ...]:
    expected = cases.cut_call().record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    log.worker(
        outcome(
            1,
            1,
            complete("max_tokens"),
            response=body("max_tokens", tool_use("tu_1", "employee", {})),
        ),
        offset=1_500,
    )
    _closed_completed(log, expected)
    return log.logged()


def handled_fact_tool() -> tuple[LoggedEvent, ...]:
    expected = cases.handled_fact_tool().record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(
        log,
        expected.pico_usd,
        reads=(
            prefetch(2, "employees", Source.FRAPPE, PEOPLE),
            prefetch(3, "work_items", Source.JIRA, TICKETS),
        ),
    )
    log.worker(intent(1), offset=600)
    log.worker(
        outcome(
            1,
            1,
            complete("tool_use"),
            response=body("tool_use", tool_use("tu_1", FACT_TOOL, payload(entry_of(cases.SKILL)))),
        ),
        offset=1_500,
    )
    _closed_completed(log, expected)
    return log.logged()


def unresolved_then_answered() -> tuple[LoggedEvent, ...]:
    fixture = cases.unresolved_then_answered()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=3_000)
    log.claim()
    log.worker(intent(1, 2), offset=300)
    log.worker(outcome(1, 2, complete(), response=body("end_turn", text("Done."))), offset=1_200)
    _closed_completed(log, expected, offset=2_500, terminal=fixture.record.timing.terminal_at)
    return log.logged()


def nova_signature_beside_another() -> tuple[LoggedEvent, ...]:
    expected = cases.nova_signature_beside_another().record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    log.worker(
        outcome(
            1,
            1,
            ServiceError(424, "ModelErrorException", None, cases.NOVA_CUT, 0, "req-nova-1"),
            AttributionKind.BEHAVIOUR,
            rule="nova-cut-tool-use",
        ),
        offset=1_500,
    )
    log.worker(count_start("call-2"), offset=1_600)
    log.worker(count_outcome("call-2"), offset=1_700)
    log.worker(intent(2, name="call-2"), offset=1_800)
    log.worker(
        outcome(
            2,
            1,
            ServiceError(
                424, "ModelErrorException", None, "Model timed out mid-generation", 0, "req-nova-2"
            ),
            AttributionKind.INFRASTRUCTURE,
            rule="unmatched",
        ),
        offset=2_700,
    )
    log.worker(intent(2, 2, name="call-2"), offset=2_800)
    log.worker(outcome(2, 2, complete(), response=body("end_turn", text("Done."))), offset=3_700)
    _closed_completed(log, expected)
    return log.logged()


def recovered_attempt() -> tuple[LoggedEvent, ...]:
    fixture = cases.recovered_attempt()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    log.admit(inputs(reservation=expected.pico_usd))
    log.claim()
    log.worker(prefetch(1, "work_items", Source.JIRA), offset=1_200)
    log.claim()
    log.worker(count_start("call-1"), offset=400)
    log.worker(count_outcome("call-1"), offset=500)
    log.worker(intent(1, shown=("prefetch/1",)), offset=600)
    log.worker(outcome(1, 1, complete(), response=body("end_turn", text("Done."))), offset=1_500)
    _closed_completed(log, expected, offset=6_000, terminal=fixture.record.timing.terminal_at)
    return log.logged()


def abandoned_attempt() -> tuple[LoggedEvent, ...]:
    fixture = cases.abandoned_attempt()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    log.worker(outcome(1, 1, complete(), response=body("end_turn", text("Done."))), offset=1_500)
    log.worker(ApprovalRequested((), cases.RULES), offset=4_800)
    log.outside(
        "operator",
        Abandoned(1, AbandonmentReason.CANCELLED, settlement_of(expected)),
        at=fixture.record.timing.terminal_at,
    )
    return log.logged()


def approval_wait_across_restart() -> tuple[LoggedEvent, ...]:
    fixture = cases.approval_wait_across_restart()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    log.worker(outcome(1, 1, complete(), response=body("end_turn", text("Done."))), offset=1_500)
    log.worker(ApprovalRequested((), cases.RULES), offset=7_000)
    log.worker(SegmentEnded(), offset=7_900)
    log.claim()
    log.outside(
        AUTOMATIC.identity,
        Approved(Approver.AUTOMATIC, cases.review_payload_digest((), cases.RULES)),
    )
    log.claim()
    log.worker(Resumed(), offset=50)
    log.worker(
        Completed(settlement_of(expected)), offset=2_050, at=fixture.record.timing.terminal_at
    )
    return log.logged()


def wrong_scope_beside_unplaced() -> tuple[LoggedEvent, ...]:
    fixture = cases.wrong_scope_beside_unplaced()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(
        log,
        expected.pico_usd,
        reads=(
            prefetch(2, "employees", Source.FRAPPE, PEOPLE),
            prefetch(3, "work_items", Source.JIRA, TICKETS),
            document_read(4, cases.SCOPED_RUNBOOK),
        ),
    )
    log.worker(intent(1), offset=600)
    on_the_meeting, unread = cases.requirement(f.MEETING.title), cases.requirement("Ledger cutover")
    log.worker(
        outcome(
            1,
            1,
            complete(),
            response=body("end_turn", payload_text(entry_of(on_the_meeting), entry_of(unread))),
        ),
        offset=1_500,
    )
    composition = fixture.trace.composition
    log.worker(ApprovalRequested((), composition), offset=8_700)
    log.outside(
        AUTOMATIC.identity,
        Approved(Approver.AUTOMATIC, cases.review_payload_digest((), composition)),
    )
    log.worker(Resumed(), offset=8_800)
    log.worker(
        Completed(settlement_of(expected)), offset=9_000, at=fixture.record.timing.terminal_at
    )
    return log.logged()


def _two_tool_calls() -> JsonObject:
    return body(
        "tool_use",
        tool_use("tu_1", "work_item", {"id": "ticket_042"}),
        tool_use("tu_2", "employee", {"id": "emp_023"}),
    )


def first_tool_call_ends_the_attempt() -> tuple[LoggedEvent, ...]:
    fixture = cases.first_tool_call_ends_the_attempt()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    log.worker(outcome(1, 1, complete("tool_use"), response=_two_tool_calls()), offset=1_500)
    log.worker(
        model_read(1, "tu_1", DefectOutcome(Source.JIRA, "LIA-42", "no world id")), offset=1_700
    )
    log.worker(
        Failed(
            FailureCategory.DEFECT,
            OperationSite(cases.OperationId("call-1/tu_1")),
            "a malformed record",
            settlement_of(expected),
        ),
        offset=9_000,
        at=fixture.record.timing.terminal_at,
    )
    return log.logged()


def tool_result_lost() -> tuple[LoggedEvent, ...]:
    fixture = cases.tool_result_lost()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    log.worker(
        outcome(
            1,
            1,
            complete("tool_use"),
            response=body("tool_use", tool_use("tu_1", "work_item", {"id": "ticket_042"})),
        ),
        offset=2_000,
    )
    log.outside(
        "recovery",
        Abandoned(1, AbandonmentReason.INTERRUPTED, settlement_of(expected)),
        at=fixture.record.timing.terminal_at,
    )
    return log.logged()


def never_claimed() -> tuple[LoggedEvent, ...]:
    fixture = cases.never_claimed()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    log.admit(inputs(reservation=expected.pico_usd))
    log.outside(
        "operator",
        Abandoned(0, AbandonmentReason.CANCELLED, settlement_of(expected)),
        at=fixture.record.timing.terminal_at,
    )
    return log.logged()


def defect_finalized_by_operator() -> tuple[LoggedEvent, ...]:
    fixture = cases.defect_finalized_by_operator()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    _one_call_prefix(log, expected.pico_usd)
    log.worker(intent(1), offset=600)
    log.worker(outcome(1, 1, complete("tool_use"), response=_two_tool_calls()), offset=1_500)
    log.worker(
        model_read(1, "tu_1", DefectOutcome(Source.JIRA, "LIA-42", "no world id")), offset=1_600
    )
    log.outside(
        "operator",
        Abandoned(1, AbandonmentReason.INTERRUPTED, settlement_of(expected)),
        at=fixture.record.timing.terminal_at,
    )
    return log.logged()


def input_bound_exhausted() -> tuple[LoggedEvent, ...]:
    fixture = cases.input_bound_exhausted()
    expected = fixture.record.reservation
    assert expected is not None
    log = History()
    log.admit(inputs(reservation=expected.pico_usd))
    log.claim()
    log.worker(prefetch(1, "work_items", Source.JIRA), offset=100)
    first = CountKey(cases.METHOD, cases.COUNTING_MODEL, cases.DIGEST, 1)
    second = CountKey(cases.METHOD, cases.COUNTING_MODEL, cases.DIGEST, 2)
    third = CountKey(cases.METHOD, cases.COUNTING_MODEL, cases.DIGEST, 3)
    log.worker(CountStarted(first, cases.ROLE), offset=400)
    log.worker(
        CountOutcomeLogged(
            first,
            CountServiceError(429, "ThrottlingException", "rate exceeded", "req-count-1", 80),
            CountResult.FAILED,
        ),
        offset=500,
    )
    log.worker(CountStarted(second, cases.ROLE), offset=1_000)
    log.worker(
        CountOutcomeLogged(
            second, CountClientError(ClientErrorKind.TIMEOUT, 30_000), CountResult.FAILED
        ),
        offset=31_000,
    )
    log.claim()
    log.worker(CountStarted(third, cases.ROLE), offset=900)
    log.claim()
    log.worker(
        Failed(
            FailureCategory.INFRASTRUCTURE,
            InputBoundSite(count_id(third)),
            "the counting requests were exhausted without a count",
            settlement_of(expected),
        ),
        offset=100,
        at=fixture.record.timing.terminal_at,
    )
    return log.logged()


HISTORIES: dict[str, Build] = {
    "facts beside tools in one answer": facts_beside_tools,
    "a malformed batch": malformed_batch,
    "a refused fact that cannot construct a value": refused_fact,
    "a cut call": cut_call,
    "a handled fact-submission tool": handled_fact_tool,
    "an unresolved dispatch followed by an answered one": unresolved_then_answered,
    "the Nova signature beside another model error": nova_signature_beside_another,
    "a recovered attempt": recovered_attempt,
    "an abandoned attempt": abandoned_attempt,
    "an approval wait across a restart": approval_wait_across_restart,
    "a wrong scope beside an unplaced one": wrong_scope_beside_unplaced,
    "a multi-tool answer whose first call ends the attempt": first_tool_call_ends_the_attempt,
    "a tool call whose result was lost before it was logged": tool_result_lost,
    "an attempt admitted and never claimed": never_claimed,
    "a recorded defect an operator finalized": defect_finalized_by_operator,
    "a request whose input bound was never established": input_bound_exhausted,
}
"""Each fixture's history, by the fixture's name."""


__all__ = ["HISTORIES", "RULES", "History", "inputs", "settlement_of"]
