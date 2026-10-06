"""The store against PostgreSQL, one connection: the claims the acceptance manifest makes of
its commands (the event log step's ruling on placement and acceptance, part 5), and the
sixteen format fixtures replayed through it.

*Replay.* Every history the reader's acceptance rebuilds is appended through the command
its kind takes (admit, claim, append, close), the store's clock scripted to the history's
timestamps; the stored log folds to the state the commands returned and the reader builds
the fixture's hand-built export from it, the one substitution being the reservation's
ledger revision, which is the store's own number.

*Idempotency.* A repeated admission request returns its recorded result; an identical
re-append and a repeated claim under one nonce are receipts and take no position, segment
or ledger entry; other content under a held identifier raises; a repeated closure is a
receipt with one settled entry behind it.

*Admission.* A refusal is recorded and consumes no attempt number; a successor waits for
its predecessor's closure, then its publication, then the eligibility function's answer;
the ledger refuses above its room and records the refusal, and refuses with no head and
records nothing there.

*Publication.* Pending, published, failed: published is never left, another object under
one record is a conflict, a failed record is repaired under another reader and says so.

*Faults.* Another schema version and a missing bootstrap refuse the connection; a conflict's
formatted traceback names no content of the inputs.
"""

from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest

from leaveimpact.agent import ledger
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    CapExhausted,
    Completed,
    DispatchOutcome,
    Failed,
    LoggedEvent,
    Producer,
    SegmentEnded,
    SegmentStarted,
    WorkerStamp,
    kind_of,
    log_digest,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import (
    AdmissionReceipt,
    AdmissionRefusal,
    AdmissionRequest,
    AttemptRef,
    LogStore,
    LogStoreConflict,
    LogStoreInvariantBroken,
    PublicationState,
)
from leaveimpact.agent.log_transition import Appended, AttemptState, Received, Refused
from leaveimpact.core import (
    AbandonmentReason,
    Attribution,
    AttributionKind,
    DispatchPhase,
    DispatchSite,
    FailureCategory,
    ModelCallId,
    ServiceError,
    export_bytes,
)
from leaveimpact.core.eligibility import EligibilityRule
from tests.integration.log_store_support import Hold, Rig, Scripted, rig
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories

pytestmark = pytest.mark.integration

RULES = histories.RULES
LEDGER = "ledger-test"
AUTHORITY = "operator:test"
PLENTY = 10**15
OBJECT = "exports/run-12/1.json"
DIGEST = "d" * 64
OPERATOR = Producer("operator")

_ = rig  # the fixture, imported for pytest to find


def request_id() -> str:
    return f"req-{uuid4().hex[:12]}"


def opened(rig: Rig, *, threshold: int = PLENTY, ledger_id: str = LEDGER) -> LogStore:
    """A store over the rig's schema with the ledger's threshold set."""
    store = rig.store()
    store.set_threshold(
        ledger_id,
        threshold,
        authority=AUTHORITY,
        registration_commit=cases.COMMIT,
        limit_pico_usd=PLENTY,
    )
    return store


def admission_of(events: tuple[LoggedEvent, ...]) -> tuple[Admitted, Producer]:
    first = events[0]
    assert isinstance(first.event, Admitted) and isinstance(first.envelope, Producer)
    return first.event, first.envelope


def request_for(
    admitted: Admitted, admitter: Producer, *, ledger_id: str = LEDGER
) -> AdmissionRequest:
    inputs = admitted.inputs
    return AdmissionRequest(
        request_id(),
        inputs,
        admitter,
        ledger_id if inputs.reservation_pico_usd is not None else None,
        RULES,
    )


def step(store: LogStore, logged: LoggedEvent, state: AttemptState) -> Appended:
    """One event through the command its kind takes, which must append it."""
    inputs = state.inputs
    assert inputs is not None
    run_id, attempt = inputs.run_id, inputs.attempt
    event = logged.event
    match event:
        case SegmentStarted():
            result = store.claim(
                run_id,
                attempt,
                harness=event.harness,
                nonce=event.nonce,
                launch=event.launch,
                override=event.override,
                rules=RULES,
                state=state,
            )
        case Completed() | CapExhausted() | Failed() | Abandoned():
            result = store.close_attempt(
                run_id,
                attempt,
                logged.envelope,
                replace(event, settlement=None),
                rules=RULES,
                state=state,
            )
        case _:
            result = store.append(run_id, attempt, logged.envelope, event, rules=RULES, state=state)
    assert isinstance(result, Appended), (logged.position, kind_of(event).value, result)
    assert result.state.last_position == logged.position
    return result


def replay(
    store: LogStore, events: tuple[LoggedEvent, ...], *, upto: int | None = None
) -> AttemptState:
    """The history admitted and appended through ``upto`` (every event by default)."""
    admitted, admitter = admission_of(events)
    receipt = store.admit(request_for(admitted, admitter))
    assert isinstance(receipt, AdmissionReceipt)
    state = store.load(admitted.inputs.run_id, admitted.inputs.attempt, rules=RULES)
    for logged in events[1 : upto if upto is not None else len(events)]:
        state = step(store, logged, state).state
    return state


def published(store: LogStore, run_id: str, attempt: int) -> None:
    digest = log_digest(store.events(run_id, attempt))
    store.publication_pending(
        run_id,
        attempt,
        reader_commit=cases.COMMIT,
        export_format=3,
        log_digest=digest,
        object_identity=OBJECT,
        object_digest=DIGEST,
    )
    store.publication_published(run_id, attempt, object_identity=OBJECT, object_digest=DIGEST)


# --- The histories ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(histories.HISTORIES))
def test_a_history_replayed_through_the_store_rebuilds_its_export(rig: Rig, name: str) -> None:
    events = histories.HISTORIES[name]()
    plain = opened(rig)
    store = rig.store(clock=Scripted([logged.timestamp for logged in events]))
    final = replay(store, events)
    run_id, attempt = admission_of(events)[0].inputs.run_id, 1
    stored = store.load(run_id, attempt, rules=RULES)
    assert stored == final, "the state the commands returned is the fold of what was stored"
    assert [logged.position for logged in stored.events] == list(range(1, len(events) + 1))
    expected = cases.FIXTURES[name]()
    reservation = expected.record.reservation
    if reservation is not None:
        view = plain.ledger_view(LEDGER)
        settled = [entry for entry in view.entries if entry.kind is ledger.EntryKind.SETTLED]
        assert len(settled) == 1 and settled[0].amount_pico_usd == reservation.charged_pico_usd
        assert view.head.total_pico_usd == reservation.charged_pico_usd
        record = replace(
            expected.record, reservation=replace(reservation, ledger_revision=settled[0].revision)
        )
        expected = replace(expected, record=record)
    actual = export_of(stored)
    assert actual == expected
    assert export_bytes(actual) == export_bytes(expected)
    assert store.open_attempts() == ()


# --- Admission -------------------------------------------------------------------------------


def test_an_admission_is_one_receipt_however_often_it_is_asked(rig: Rig) -> None:
    store = opened(rig)
    admitted, admitter = admission_of(histories.HISTORIES["facts beside tools in one answer"]())
    request = request_for(admitted, admitter)
    first = store.admit(request)
    assert isinstance(first, AdmissionReceipt) and first.ledger_revision == 2
    assert store.admit(request) == first, "a repeated request returns its recorded result"
    with pytest.raises(LogStoreConflict, match="with other content"):
        store.admit(replace(request, inputs=replace(admitted.inputs, corpus_level="padded")))
    with pytest.raises(LogStoreConflict, match="with other content"):
        store.admit(replace(request, ledger_id="ledger-other"))
    again = store.admit(replace(request, request_id=request_id()))
    assert again == first, "another request for an attempt that exists gets its receipt"
    with pytest.raises(LogStoreConflict, match="exists with other frozen inputs"):
        store.admit(
            replace(
                request,
                request_id=request_id(),
                inputs=replace(admitted.inputs, corpus_level="padded"),
            )
        )
    assert store.open_attempts() == (AttemptRef("run-12", 1),)
    view = store.ledger_view(LEDGER)
    assert [entry.kind for entry in view.entries] == [
        ledger.EntryKind.THRESHOLD_SET,
        ledger.EntryKind.ADMITTED,
    ]
    assert view.head.total_pico_usd == admitted.inputs.reservation_pico_usd
    (event,) = store.events("run-12", 1)
    assert event.position == 1 and event.event == admitted and event.envelope == admitter


def test_a_request_for_an_attempt_that_is_not_the_next_is_a_conflict(rig: Rig) -> None:
    store = opened(rig)
    admitted, admitter = admission_of(histories.HISTORIES["a cut call"]())
    with pytest.raises(LogStoreConflict, match="attempt 3 is not the next"):
        store.admit(
            request_for(replace(admitted, inputs=replace(admitted.inputs, attempt=3)), admitter)
        )


def test_a_successor_waits_for_closure_then_publication_then_the_ending(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["an attempt admitted and never claimed"]()
    admitted, admitter = admission_of(events)
    second = replace(admitted, inputs=replace(admitted.inputs, attempt=2))
    state = replay(store, events, upto=1)
    refused = store.admit(request_for(second, admitter))
    assert refused == AdmissionRefusal("run-12", 2, "attempt 1 is open", None)
    assert store.open_attempts() == (AttemptRef("run-12", 1),), "a refusal consumes no number"
    step(store, events[1], state)
    refused = store.admit(request_for(second, admitter))
    assert isinstance(refused, AdmissionRefusal)
    assert refused.reason == "attempt 1's export is not published (publication absent)"
    digest = log_digest(store.events("run-12", 1))
    store.publication_pending(
        "run-12",
        1,
        reader_commit=cases.COMMIT,
        export_format=3,
        log_digest=digest,
        object_identity=OBJECT,
        object_digest=DIGEST,
    )
    refused = store.admit(request_for(second, admitter))
    assert isinstance(refused, AdmissionRefusal) and refused.reason.endswith(
        "(publication pending)"
    )
    store.publication_published("run-12", 1, object_identity=OBJECT, object_digest=DIGEST)
    receipt = store.admit(request_for(second, admitter))
    assert isinstance(receipt, AdmissionReceipt) and receipt.attempt == 2
    assert store.open_attempts() == (AttemptRef("run-12", 2),)
    view = store.ledger_view(LEDGER)
    assert [entry.kind for entry in view.entries] == [
        ledger.EntryKind.THRESHOLD_SET,
        ledger.EntryKind.ADMITTED,
        ledger.EntryKind.SETTLED,
        ledger.EntryKind.ADMITTED,
    ], "eligibility and publication refusals touch no ledger revision"


def test_a_graded_predecessor_permits_no_successor(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["facts beside tools in one answer"]()
    admitted, admitter = admission_of(events)
    replay(store, events)
    published(store, "run-12", 1)
    second = replace(admitted, inputs=replace(admitted.inputs, attempt=2))
    refused = store.admit(request_for(second, admitter))
    assert isinstance(refused, AdmissionRefusal)
    assert refused.reason == (
        f"attempt 1's ending permits no new attempt ({EligibilityRule.GRADED_RESULT.value})"
    )


def test_the_ledger_refuses_above_its_room_and_records_it(rig: Rig) -> None:
    store = opened(rig, threshold=1)
    admitted, admitter = admission_of(histories.HISTORIES["a cut call"]())
    reserved = admitted.inputs.reservation_pico_usd
    assert reserved is not None and reserved > 1
    request = request_for(admitted, admitter)
    refused = store.admit(request)
    assert isinstance(refused, AdmissionRefusal) and refused.ledger_revision == 2
    assert "exceeds the room of 1" in refused.reason
    assert store.admit(request) == refused
    view = store.ledger_view(LEDGER)
    assert [entry.kind for entry in view.entries] == [
        ledger.EntryKind.THRESHOLD_SET,
        ledger.EntryKind.REFUSED,
    ]
    assert view.entries[1].reason == refused.reason and view.head.total_pico_usd == 0
    assert store.open_attempts() == ()


def test_a_ledger_with_no_head_refuses_and_records_nothing_there(rig: Rig) -> None:
    store = rig.store()
    admitted, admitter = admission_of(histories.HISTORIES["a cut call"]())
    refused = store.admit(request_for(admitted, admitter, ledger_id="ledger-unset"))
    assert isinstance(refused, AdmissionRefusal) and refused.ledger_revision is None
    assert refused.reason == "ledger ledger-unset has no head: no threshold is set on it"
    with pytest.raises(ValueError, match="has no head"):
        store.ledger_view("ledger-unset")


def test_a_threshold_is_refused_above_the_limit_and_below_the_total(rig: Rig) -> None:
    store = opened(rig)
    with pytest.raises(ValueError, match="above the registered limit"):
        store.set_threshold(
            LEDGER,
            PLENTY + 1,
            authority=AUTHORITY,
            registration_commit=cases.COMMIT,
            limit_pico_usd=PLENTY,
        )
    admitted, admitter = admission_of(histories.HISTORIES["a cut call"]())
    store.admit(request_for(admitted, admitter))
    reserved = admitted.inputs.reservation_pico_usd
    assert reserved is not None
    with pytest.raises(ValueError, match="below the committed total"):
        store.set_threshold(
            LEDGER,
            reserved - 1,
            authority=AUTHORITY,
            registration_commit=cases.COMMIT,
            limit_pico_usd=PLENTY,
        )
    lowered = store.set_threshold(
        LEDGER,
        reserved,
        authority=AUTHORITY,
        registration_commit=cases.COMMIT,
        limit_pico_usd=PLENTY,
    )
    assert lowered.revision == 3 and store.ledger_view(LEDGER).head.threshold_pico_usd == reserved


# --- Idempotency -----------------------------------------------------------------------------


def test_a_repeated_claim_under_one_nonce_is_a_receipt_until_a_takeover_fences_it(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["a cut call"]()
    state = replay(store, events, upto=2)
    started = events[1].event
    assert isinstance(started, SegmentStarted)
    again = store.claim(
        "run-12",
        1,
        harness=started.harness,
        nonce=started.nonce,
        launch=started.launch,
        rules=RULES,
        state=state,
    )
    assert again == Received(2)
    assert len(store.load("run-12", 1, rules=RULES).segments) == 1
    with pytest.raises(LogStoreConflict, match="another content under the claim nonce"):
        store.claim(
            "run-12",
            1,
            harness=started.harness,
            nonce=started.nonce,
            launch="launch-other",
            rules=RULES,
            state=state,
        )
    taken = store.claim(
        "run-12", 1, harness=started.harness, nonce="nonce-other", launch="launch-2", rules=RULES
    )
    assert isinstance(taken, Appended) and taken.state.generation == 2
    fenced = store.claim(
        "run-12",
        1,
        harness=started.harness,
        nonce=started.nonce,
        launch=started.launch,
        rules=RULES,
    )
    assert fenced == Refused(
        "the claim under this nonce opened generation 1, fenced by generation 2"
    )


def test_an_identical_re_append_is_a_receipt_and_other_content_raises(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["a cut call"]()
    state = replay(store, events, upto=3)
    operation = events[2]
    again = store.append("run-12", 1, operation.envelope, operation.event, rules=RULES, state=state)
    assert again == Received(3)
    assert store.load("run-12", 1, rules=RULES) == state
    other = replace(operation.event, resolution=replace(operation.event.resolution, tool="other"))  # type: ignore[union-attr, arg-type]
    with pytest.raises(LogStoreConflict, match="another content under the identifier"):
        store.append("run-12", 1, operation.envelope, other, rules=RULES, state=state)
    assert store.events("run-12", 1) == tuple(store.load("run-12", 1, rules=RULES).events)


def test_a_repeated_closure_is_a_receipt_with_one_settled_entry(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["a cut call"]()
    state = replay(store, events)
    closing = events[-1]
    assert isinstance(closing.event, Completed)
    again = store.close_attempt(
        "run-12",
        1,
        closing.envelope,
        replace(closing.event, settlement=None),
        rules=RULES,
        state=state,
    )
    assert again == Received(closing.position)
    other = store.close_attempt(
        "run-12",
        1,
        OPERATOR,
        Abandoned(1, AbandonmentReason.CANCELLED, None),
        rules=RULES,
    )
    assert other == Refused(f"the attempt is closed at position {closing.position}")
    view = store.ledger_view(LEDGER)
    assert [entry.kind for entry in view.entries].count(ledger.EntryKind.SETTLED) == 1
    with pytest.raises(ValueError, match="pass the closing event without one"):
        store.close_attempt("run-12", 1, closing.envelope, closing.event, rules=RULES)


def test_another_content_under_the_closing_events_identifier_raises(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["an abandoned attempt"]()
    replay(store, events)
    closing = events[-1].event
    assert isinstance(closing, Abandoned) and closing.reason is AbandonmentReason.CANCELLED
    with pytest.raises(LogStoreConflict, match="closed at position .* with other content"):
        store.close_attempt(
            "run-12",
            1,
            OPERATOR,
            replace(closing, reason=AbandonmentReason.INTERRUPTED, settlement=None),
            rules=RULES,
        )
    assert store.ledger_view(LEDGER).head.revision == 3, "the conflict wrote nothing"


def test_the_commands_with_a_shape_of_their_own_are_refused_by_append(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["a cut call"]()
    state = replay(store, events, upto=2)
    for event in (events[0].event, events[1].event, events[-1].event):
        with pytest.raises(ValueError, match="through its own command"):
            store.append("run-12", 1, events[1].envelope, event, rules=RULES, state=state)
    with pytest.raises(ValueError, match="has no attempt 2"):
        store.append("run-12", 2, WorkerStamp(1, 1, 5), SegmentEnded(), rules=RULES)


def test_a_readers_failure_rolls_back_no_closure_or_settlement(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["a cut call"]()
    replay(store, events)
    before = store.ledger_view(LEDGER)

    def failing_reader() -> None:
        raise RuntimeError("the export would not construct")

    with pytest.raises(RuntimeError):
        failing_reader()
    assert store.load("run-12", 1, rules=RULES).closed is not None
    assert store.ledger_view(LEDGER) == before
    assert store.open_attempts() == ()


# --- Publication -----------------------------------------------------------------------------


def test_publication_states_and_what_never_changes_back(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["a cut call"]()
    state = replay(store, events, upto=len(events) - 1)
    assert store.publication_of("run-12", 1) is None
    with pytest.raises(ValueError, match="is open and has no export"):
        store.publication_pending(
            "run-12",
            1,
            reader_commit=cases.COMMIT,
            export_format=3,
            log_digest=DIGEST,
            object_identity=OBJECT,
            object_digest=DIGEST,
        )
    step(store, events[-1], state)
    digest = log_digest(store.events("run-12", 1))
    pending = store.publication_pending(
        "run-12",
        1,
        reader_commit=cases.COMMIT,
        export_format=3,
        log_digest=digest,
        object_identity=OBJECT,
        object_digest=DIGEST,
    )
    assert (
        pending.state is PublicationState.PENDING and store.publication_of("run-12", 1) == pending
    )
    failed = store.publication_failed(
        "run-12", 1, reader_commit=cases.COMMIT, object_identity=OBJECT, incident="upload refused"
    )
    assert failed.state is PublicationState.FAILED and failed.incident == "upload refused"
    repaired = store.publication_pending(
        "run-12",
        1,
        reader_commit="e" * 40,
        export_format=3,
        log_digest=digest,
        object_identity=OBJECT,
        object_digest=DIGEST,
    )
    assert repaired.state is PublicationState.PENDING
    assert repaired.repaired_from_commit == cases.COMMIT and repaired.incident == "upload refused"
    stale = store.publication_failed(
        "run-12", 1, reader_commit=cases.COMMIT, object_identity=OBJECT, incident="A's late handler"
    )
    assert stale == repaired, "a replaced publisher's late failure changes nothing"
    with pytest.raises(LogStoreConflict, match="over another log digest"):
        store.publication_pending(
            "run-12",
            1,
            reader_commit="e" * 40,
            export_format=3,
            log_digest="f" * 64,
            object_identity=OBJECT,
            object_digest=DIGEST,
        )
    with pytest.raises(LogStoreConflict, match="names another object"):
        store.publication_published("run-12", 1, object_identity=OBJECT, object_digest="0" * 64)
    done = store.publication_published("run-12", 1, object_identity=OBJECT, object_digest=DIGEST)
    assert done.state is PublicationState.PUBLISHED and done.repaired_from_commit == cases.COMMIT
    assert (
        store.publication_published("run-12", 1, object_identity=OBJECT, object_digest=DIGEST)
        == done
    )
    assert (
        store.publication_failed(
            "run-12", 1, reader_commit="e" * 40, object_identity=OBJECT, incident="late handler"
        )
        == done
    )
    late = store.publication_pending(
        "run-12",
        1,
        reader_commit="e" * 40,
        export_format=3,
        log_digest=digest,
        object_identity="exports/elsewhere.json",
        object_digest=DIGEST,
    )
    assert late == done, "published is never left"
    with pytest.raises(ValueError, match="has no publication"):
        store.publication_failed(
            "run-12", 7, reader_commit=cases.COMMIT, object_identity=OBJECT, incident="x"
        )


# --- Faults ----------------------------------------------------------------------------------


def test_another_schema_version_and_a_missing_bootstrap_refuse_the_connection(rig: Rig) -> None:
    setup = rig.store()
    setup.ensure_schema()
    setup.ensure_schema()
    assert setup.open_attempts() == ()
    conn = rig.connections[max(rig.connections)]  # the setup store's, still open
    conn.execute("UPDATE log_schema SET version = 2")
    rejected = rig.store()
    for _ in range(2):
        with pytest.raises(LogStoreInvariantBroken, match="holds version 2"):
            rejected.open_attempts()
    conn.execute("DROP TABLE log_schema")
    with pytest.raises(LogStoreInvariantBroken, match="not bootstrapped"):
        rig.store().open_attempts()


def test_a_conflicts_traceback_names_no_content_of_the_inputs(rig: Rig) -> None:
    store = opened(rig)
    admitted, admitter = admission_of(histories.HISTORIES["a cut call"]())
    store.admit(request_for(admitted, admitter))
    other = replace(admitted, inputs=replace(admitted.inputs, corpus_level="padded-content"))
    try:
        store.admit(request_for(other, admitter))
    except LogStoreConflict as exc:
        text = "".join(traceback.format_exception(exc))
    else:
        raise AssertionError("a conflict was expected")
    assert "padded-content" not in text and admitted.inputs.corpus_level not in text
    assert admitted.inputs.context.world_version not in text  # type: ignore[attr-defined]
    assert "run-12" in text


# --- The review's reads and the disowned attribution --------------------------------------------


def test_a_read_without_the_lock_is_consistent_at_the_rows_cutoff(rig: Rig) -> None:
    """An append between the row's read and the events' read is below no cutoff the row
    gave, so the load returns the state at the row and raises nothing."""
    events = histories.HISTORIES["a cut call"]()
    plain = opened(rig)
    state = replay(plain, events, upto=2)
    hold = Hold("read")
    reader = rig.store(boundary=hold)
    with ThreadPoolExecutor(1) as pool:
        loading = pool.submit(reader.load, "run-12", 1, rules=RULES)
        hold.wait_reached()
        appended = plain.append(
            "run-12", 1, WorkerStamp(1, 1, 5), SegmentEnded(), rules=RULES, state=state
        )
        assert isinstance(appended, Appended)
        hold.release.set()
        loaded = loading.result(10)
    assert loaded.last_position == 2, "the read is the row's cutoff, not the append between"
    hold.release.set()
    assert reader.load("run-12", 1, rules=RULES).last_position == 3


def test_a_predecessor_whose_attribution_the_table_disowns_permits_no_successor(rig: Rig) -> None:
    store = opened(rig)
    events = histories.HISTORIES["a cut call"]()
    admitted, admitter = admission_of(events)
    state = replay(store, events, upto=6)
    held = events[6].event
    assert isinstance(held, DispatchOutcome)
    mislabelled = replace(
        held,
        observation=ServiceError(429, "ThrottlingException", None, "too many requests"),
        response=None,
        attribution=Attribution(AttributionKind.INFRASTRUCTURE, "stream"),
        zero_cost_rule=None,
    )
    appended = store.append("run-12", 1, events[6].envelope, mislabelled, rules=RULES, state=state)
    assert isinstance(appended, Appended) and appended.state.stopped is not None
    closing = Failed(
        FailureCategory.INFRASTRUCTURE,
        DispatchSite(ModelCallId("call-1"), 1, DispatchPhase.SEND),
        "the call failed by infrastructure and no further dispatch is permitted",
        None,
    )
    closed = store.close_attempt(
        "run-12", 1, WorkerStamp(1, 1, 1_600), closing, rules=RULES, state=appended.state
    )
    assert isinstance(closed, Appended)
    published(store, "run-12", 1)
    second = replace(admitted, inputs=replace(admitted.inputs, attempt=2))
    refused = store.admit(request_for(second, admitter))
    assert isinstance(refused, AdmissionRefusal)
    assert refused.reason == (
        "attempt 1's failure at a dispatch's send is recorded under an attribution the table "
        "does not give its observation"
    )
