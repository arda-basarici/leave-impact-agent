"""The commands over the real store: the work command runs the reference script to its
closing; a human approval is delivered as a command, refused where the ruling says, and
repeated as a receipt; an abandonment closes a claimed and a never-claimed attempt and is
refused on a closed one; publication is created, repeated as the record, adopted over an
object already present (verified and, under a put-only grant, unverified), failed on a
conflict and on a reader that cannot build, and repaired under another reader at another
key; the export bytes of one closed log are equal across two builds; the inventory is
sealed at the key its digest names and lists the attempt with its publication; the
threshold command passes the store's refusal on as a value; and the evaluator's four
audits over the real export report no finding."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest

from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.wiring import (
    UploadOutcome,
    inventory_publisher_over,
    run_export_publisher_over,
)
from leaveimpact.agent.commands import (
    AbandonRequest,
    ApprovalDelivered,
    ApprovalDelivery,
    AttemptAbandoned,
    CommandRefused,
    InventoryRequest,
    PublishRequest,
    ThresholdRequest,
    WorkRequest,
    abandon,
    deliver_approval,
    publish,
    set_threshold,
    work,
    write_inventory,
)
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.log_events import ApprovalRequested
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import AttemptState
from leaveimpact.agent.worker import (
    HumanApproval,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core.inventory import InventoryScope, PublicationStatus, decode_inventory_bytes
from leaveimpact.core.run_ending import AbandonmentReason
from leaveimpact.core.run_export import EXPORT_FORMAT_VERSION, RunExport
from leaveimpact.core.run_export_json import decode_export_bytes, export_bytes
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from tests.integration.log_store_support import Rig, Scripted, rig
from tests.integration.worker_rig import (
    ATTEMPT,
    LEDGER,
    PLENTY,
    RULES,
    RUN,
    admitted,
    completed,
    composition,
    saver_on,
)
from tests.unit import format_fixtures as cases
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.throwaway_world import loaded_world

pytestmark = pytest.mark.integration

AT = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
READER = cases.COMMIT
OTHER_READER = "d" * 40

_ = rig  # the fixture, imported for pytest to find


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def published_key(inputs: Any, reader: str = READER) -> str:
    return layout.run_export_key(inputs.context.world_version, RUN, ATTEMPT, reader)


# --- work and deliver an approval ------------------------------------------------------------


def test_the_work_command_runs_the_reference_script_to_its_closing(
    rig: Rig, world: SealedWorld
) -> None:
    store, _ = completed(rig, world)
    assert store.load(RUN, ATTEMPT, rules=RULES).closed is not None


def test_an_approval_is_delivered_as_a_command_and_the_next_work_resumes(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = admitted(rig, world)
    first = work(
        WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"),
        store,
        composition(inputs, world, saver_on(rig), approval=HumanApproval()),
    )
    assert first.kind is WorkerEndingKind.AWAITING_APPROVAL
    state = store.load(RUN, ATTEMPT, rules=RULES)
    request = state.approval_requested
    assert request is not None and isinstance(request.event, ApprovalRequested)
    digest = review_payload_digest(request.event.claims, request.event.composition)
    wrong = deliver_approval(
        ApprovalDelivery(RUN, ATTEMPT, "approver:a", "0" * 64), store, rules=RULES
    )
    assert wrong == CommandRefused(
        f"run {RUN} attempt {ATTEMPT}", "the digest given is not the requested payload's"
    )
    delivered = deliver_approval(
        ApprovalDelivery(RUN, ATTEMPT, "approver:a", digest), store, rules=RULES
    )
    assert isinstance(delivered, ApprovalDelivered)
    again = deliver_approval(
        ApprovalDelivery(RUN, ATTEMPT, "approver:b", digest), store, rules=RULES
    )
    assert again == delivered, "a repeat with the same digest is the delivery already made"
    second = work(
        WorkRequest(RUN, ATTEMPT, "nonce-2", "launch-2"),
        store,
        composition(inputs, world, saver_on(rig), approval=HumanApproval()),
    )
    assert second == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "completed")
    closed = deliver_approval(
        ApprovalDelivery(RUN, ATTEMPT, "approver:a", digest), store, rules=RULES
    )
    assert isinstance(closed, CommandRefused) and closed.reason.startswith("the attempt is closed")


def test_an_approval_with_none_requested_is_refused(rig: Rig, world: SealedWorld) -> None:
    store, _ = admitted(rig, world)
    refused = deliver_approval(
        ApprovalDelivery(RUN, ATTEMPT, "approver:a", "0" * 64), store, rules=RULES
    )
    assert refused == CommandRefused(f"run {RUN} attempt {ATTEMPT}", "no approval is requested")


# --- abandon ---------------------------------------------------------------------------------


def test_an_abandonment_closes_a_never_claimed_attempt_and_a_closed_one_is_refused(
    rig: Rig, world: SealedWorld
) -> None:
    store, _ = admitted(rig, world)
    request = AbandonRequest(RUN, ATTEMPT, "operator:test", AbandonmentReason.CANCELLED)
    closed = abandon(request, store, rules=RULES)
    assert closed == AttemptAbandoned(RUN, ATTEMPT, 0, 2)
    again = abandon(request, store, rules=RULES)
    assert again == CommandRefused(
        f"run {RUN} attempt {ATTEMPT}", "the attempt is closed at position 2"
    )
    export = export_of(store.load(RUN, ATTEMPT, rules=RULES))
    assert export.record.abandonment is not None
    assert export.record.abandonment.ownership_generation == 0


def test_an_abandonment_fences_the_generation_a_worker_holds(rig: Rig, world: SealedWorld) -> None:
    store, inputs = admitted(rig, world)
    first = work(
        WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"),
        store,
        composition(inputs, world, saver_on(rig), approval=HumanApproval()),
    )
    assert first.kind is WorkerEndingKind.AWAITING_APPROVAL
    closed = abandon(
        AbandonRequest(RUN, ATTEMPT, "operator:test", AbandonmentReason.INTERRUPTED),
        store,
        rules=RULES,
    )
    assert isinstance(closed, AttemptAbandoned) and closed.generation_fenced == 1


# --- publish ---------------------------------------------------------------------------------


def test_the_export_bytes_of_one_closed_log_are_equal_across_two_builds(
    rig: Rig, world: SealedWorld
) -> None:
    """Fork 6 rests on it: one key holds one possible content."""
    store, _ = completed(rig, world)
    first = export_bytes(export_of(store.load(RUN, ATTEMPT, rules=RULES)))
    second = export_bytes(export_of(store.load(RUN, ATTEMPT, rules=RULES)))
    assert first == second


def test_publication_is_created_once_and_repeated_as_the_record(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = completed(rig, world)
    memory = InMemoryObjectStore()
    publisher = run_export_publisher_over(memory)
    record = publish(PublishRequest(RUN, ATTEMPT, READER), store, publisher, rules=RULES)
    assert isinstance(record, PublicationRecord) and record.state is PublicationStatus.PUBLISHED
    assert record.object_identity == published_key(inputs)
    held = memory.get(published_key(inputs))
    assert held is not None and record.object_digest == hashlib.sha256(held.content).hexdigest()
    assert decode_export_bytes(held.content).run_id == RUN
    again = publish(PublishRequest(RUN, ATTEMPT, OTHER_READER), store, publisher, rules=RULES)
    assert again == record, "published is never left, whoever asks"
    assert memory.list_keys("") == (published_key(inputs),)


def test_an_object_already_present_with_equal_bytes_is_adopted(
    rig: Rig, world: SealedWorld
) -> None:
    """A lost acknowledgement: the put landed and the record did not; the next publish finds
    the object present with equal bytes and adopts it."""
    store, inputs = completed(rig, world)
    content = export_bytes(export_of(store.load(RUN, ATTEMPT, rules=RULES)))
    memory = InMemoryObjectStore()
    memory.put_if_absent(published_key(inputs), content)
    record = publish(
        PublishRequest(RUN, ATTEMPT, READER), store, run_export_publisher_over(memory), rules=RULES
    )
    assert isinstance(record, PublicationRecord) and record.state is PublicationStatus.PUBLISHED
    assert record.object_digest == hashlib.sha256(content).hexdigest()
    assert len(memory.writes) == 1, "nothing was written twice"


def test_an_unverified_presence_is_adopted_under_the_pending_record_this_command_wrote(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = completed(rig, world)
    content = export_bytes(export_of(store.load(RUN, ATTEMPT, rules=RULES)))
    memory = InMemoryObjectStore(readable=False)
    memory.put_if_absent(published_key(inputs), content)
    record = publish(
        PublishRequest(RUN, ATTEMPT, READER), store, run_export_publisher_over(memory), rules=RULES
    )
    assert isinstance(record, PublicationRecord) and record.state is PublicationStatus.PUBLISHED


def test_a_conflict_is_a_failed_record_naming_both_digests_and_nothing_overwrites(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = completed(rig, world)
    memory = InMemoryObjectStore()
    memory.put_if_absent(published_key(inputs), b"other bytes")
    record = publish(
        PublishRequest(RUN, ATTEMPT, READER), store, run_export_publisher_over(memory), rules=RULES
    )
    assert isinstance(record, PublicationRecord) and record.state is PublicationStatus.FAILED
    assert record.incident is not None
    assert hashlib.sha256(b"other bytes").hexdigest() in record.incident
    held = memory.get(published_key(inputs))
    assert held is not None and held.content == b"other bytes"
    # A repair under another reader is another key, created, naming the commit it repairs.
    repaired = publish(
        PublishRequest(RUN, ATTEMPT, OTHER_READER),
        store,
        run_export_publisher_over(memory),
        rules=RULES,
    )
    assert isinstance(repaired, PublicationRecord) and repaired.state is PublicationStatus.PUBLISHED
    assert repaired.object_identity == published_key(inputs, OTHER_READER)
    assert repaired.repaired_from_commit == READER


def test_a_reader_that_cannot_build_is_a_failed_record_with_no_object(
    rig: Rig, world: SealedWorld
) -> None:
    store, _ = completed(rig, world)
    memory = InMemoryObjectStore()

    def broken(state: AttemptState) -> RunExport:
        raise ValueError("the export's constructor refused what the log states")

    record = publish(
        PublishRequest(RUN, ATTEMPT, READER),
        store,
        run_export_publisher_over(memory),
        rules=RULES,
        reader=broken,
    )
    assert isinstance(record, PublicationRecord) and record.state is PublicationStatus.FAILED
    assert record.object_identity is None and record.object_digest is None
    assert record.incident == "the reader could not build the export: ValueError"
    assert record.export_format == EXPORT_FORMAT_VERSION and memory.list_keys("") == ()
    assert store.publication_of(RUN, ATTEMPT) == record
    # The fixed reader publishes, naming the commit it repairs.
    repaired = publish(
        PublishRequest(RUN, ATTEMPT, OTHER_READER),
        store,
        run_export_publisher_over(memory),
        rules=RULES,
    )
    assert isinstance(repaired, PublicationRecord) and repaired.state is PublicationStatus.PUBLISHED
    assert repaired.repaired_from_commit == READER


def test_an_open_attempt_has_no_export_to_publish(rig: Rig, world: SealedWorld) -> None:
    store, _ = admitted(rig, world)
    refused = publish(
        PublishRequest(RUN, ATTEMPT, READER),
        store,
        run_export_publisher_over(InMemoryObjectStore()),
        rules=RULES,
    )
    assert refused == CommandRefused(
        f"run {RUN} attempt {ATTEMPT}", "the attempt is open and has no export"
    )


# --- the inventory and the threshold ---------------------------------------------------------


def test_the_inventory_is_sealed_at_the_key_its_digest_names_and_lists_the_attempt(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = completed(rig, world)
    memory = InMemoryObjectStore()
    publish(
        PublishRequest(RUN, ATTEMPT, READER), store, run_export_publisher_over(memory), rules=RULES
    )
    version = inputs.context.world_version
    scope = InventoryScope(version, cases.COMMIT, LEDGER)
    written = write_inventory(
        InventoryRequest(scope, cases.COMMIT), store, inventory_publisher_over(memory), rules=RULES
    )
    assert written.key == layout.inventory_key(version, written.digest)
    assert written.outcome is UploadOutcome.CREATED
    held = memory.get(written.key)
    assert held is not None and hashlib.sha256(held.content).hexdigest() == written.digest
    inventory = decode_inventory_bytes(held.content)
    assert inventory == written.inventory
    (listed,) = inventory.attempts
    assert listed.closed and listed.publication is not None
    assert listed.publication.status is PublicationStatus.PUBLISHED
    assert listed.publication.object_identity == published_key(inputs)
    assert inventory.ledger is not None and inventory.ledger.entries[-1].kind == "settled"
    # The identity is the content's, the snapshot's instant included: a read at another
    # instant is another object, and two reads of one state at one instant are one.
    fixed = rig.store(clock=Scripted([AT, AT]))
    later = write_inventory(
        InventoryRequest(scope, cases.COMMIT), fixed, inventory_publisher_over(memory), rules=RULES
    )
    same = write_inventory(
        InventoryRequest(scope, cases.COMMIT), fixed, inventory_publisher_over(memory), rules=RULES
    )
    assert later.outcome is UploadOutcome.CREATED and later.digest != written.digest
    assert same.outcome is UploadOutcome.PRESENT_EQUAL and same.digest == later.digest


def test_the_threshold_command_passes_the_stores_refusal_on_as_a_value(rig: Rig) -> None:
    store = rig.store()
    store.ensure_schema()
    entry = set_threshold(
        ThresholdRequest("ledger-t", 5, "operator:test", cases.COMMIT, PLENTY), store
    )
    assert not isinstance(entry, CommandRefused) and entry.amount_pico_usd == 5
    refused = set_threshold(
        ThresholdRequest("ledger-t", PLENTY + 1, "operator:test", cases.COMMIT, PLENTY), store
    )
    assert isinstance(refused, CommandRefused) and refused.subject == "ledger ledger-t"


# --- the four audits over the real export ----------------------------------------------------


def test_the_evaluators_audits_over_the_real_export_report_no_finding(
    rig: Rig, world: SealedWorld
) -> None:
    """Group 3's audits were built over hand-built exports; this is their first run over
    one the real store and worker produced (the commands group's design pass, fork 13)."""
    store, inputs = completed(rig, world)
    memory = InMemoryObjectStore()
    record = publish(
        PublishRequest(RUN, ATTEMPT, READER), store, run_export_publisher_over(memory), rules=RULES
    )
    assert isinstance(record, PublicationRecord) and record.object_identity is not None
    held = memory.get(record.object_identity)
    assert held is not None
    export = decode_export_bytes(held.content)
    evaluation = evaluate_run(
        world,
        export,
        table=RULES.table,
        redispatch=RULES.redispatch,
        retry=inputs.retry,
        counting_identifiers=dict(inputs.counting_identifiers),
    )
    metrics = evaluation.metrics
    assert metrics.account is not None and metrics.account.findings == ()
    assert metrics.counts.findings == ()
    assert metrics.calls is not None and metrics.calls.findings == ()
    assert metrics.eligibility is not None and not metrics.eligibility.permitted
    assert metrics.ending.findings == ()
