"""The job seam's commands: admit, work, review and deliver an approval, abandon, publish,
write the inventory, set the threshold; each a function over plain data and no queue (the
event log step's ruling on the job seam, part 2).

Jobs are started explicitly. A command takes a request type, the store, and what it
composes over (a worker's fillings, a publisher), and returns a result type or a refusal
as a value; nothing here reads a clock, a file or the environment, which is the
command-line entry's. The work command has a terminal-only form, ``finalize``, for an
attempt whose log already holds its ending (the first live run's step, fork 9): the same
request over the configuration, the revision and the rules alone, and no filling. The
store's own refusals and receipts are what the commands pass on: a repeated delivery is
the store's receipt, a closed attempt answers an abandonment with its refusal, and a
request for an attempt that exists is the admission's backstop.

A human's approval is given over a payload the human read (the first live run's step, fork
10): ``review_approval`` returns the frozen review payload of an attempt paused at its
approval request, with the digest the delivery must carry, so a digest alone, which lets
nobody review anything, never stands in for the reading. The payload holds the run's
claims and is printed only where the log is private.

Publication is the one command with an order of its own (the ruling on an export that will
not construct, and the commands group's forks 6 and 7). A published record is returned as
it stands. The export is built by the reader given; a reader that raises is recorded as a
failure with no object. Otherwise the pending record names the key and the digest the
command intends, the put is made, and the record is published on a created object, on one
present with equal bytes, and on one present that the principal could not read back, the
last exactly under the pending record this command wrote for that key and digest, where
nothing else could have been written: a closed log is one, the export is a function of the
log and the reader, and the key names the reader. A conflict is a failed record naming
both digests, and nothing overwrites. A refused put is a failed record; a store that did
not answer leaves the pending record for a retry.

The inventory command reads the store's one snapshot, builds the inventory under the
registered rules, and seals it at the key its digest names; what it holds is the
``core`` type the evaluator reads.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from leaveimpact.adapters.object_store.layout import run_export_key
from leaveimpact.adapters.object_store.read import AccessRefused
from leaveimpact.adapters.wiring import InventoryPublisher, RunExportPublisher, UploadOutcome
from leaveimpact.agent.assets import load_prompt_assets
from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.graph import ModelClient, NoPreparation, Preparation, TokenCounter, Turns
from leaveimpact.agent.inventory import PublicationRecord, inventory_of
from leaveimpact.agent.ledger import LedgerEntry
from leaveimpact.agent.log_events import (
    Abandoned,
    ApprovalRequested,
    Approved,
    CommitOverride,
    Declined,
    Producer,
    log_digest,
)
from leaveimpact.agent.log_reader import export_format_of, export_of
from leaveimpact.agent.log_store import (
    AdmissionRequest,
    AdmissionResult,
    LogStore,
    LogStoreConflict,
)
from leaveimpact.agent.log_transition import Appended, AttemptState, Received, Refused, Rules
from leaveimpact.agent.one_call import OneCallTurns
from leaveimpact.agent.preparations import FullContextPreparation, SingleShotPreparation
from leaveimpact.agent.rules_only import RulesOnlyTurns
from leaveimpact.agent.turns import InvestigatorTurns
from leaveimpact.agent.worker import (
    ApprovalPolicy,
    TerminalWorker,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
)
from leaveimpact.core.inventory import (
    Inventory,
    InventoryScope,
    PublicationStatus,
    inventory_bytes,
    inventory_digest,
)
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.run_ending import AbandonmentReason, Approver
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_export_json import export_bytes
from leaveimpact.core.run_parts_json import review_payload, review_payload_digest
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_timing import HarnessRevision, require_commit
from leaveimpact.core.run_trace import require_digest, require_integer, require_opaque_id
from leaveimpact.core.tools import Role

Reader = Callable[[AttemptState], RunExport]
"""Builds a closed attempt's export from its state: ``export_of``, or a test's stand-in."""


@dataclass(frozen=True, slots=True)
class CommandRefused:
    """The command did nothing, and why; the subject names the run and attempt or the ledger."""

    subject: str
    reason: str


# --- admit -------------------------------------------------------------------------------


def admit(request: AdmissionRequest, store: LogStore) -> AdmissionResult:
    """The admission as the store makes it: one transaction, a recorded request returned as
    recorded, the attempt number's backstop (the ruling on admission and the job seam's
    three identities). The request carries the run's full context in its frozen inputs;
    nothing here decodes a scenario."""
    return store.admit(request)


# --- work --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkRequest:
    """One worker execution over an admitted attempt: the attempt, the process nonce of
    this claim, the launch identity recorded for provenance, and an operator's commit
    override if one was given."""

    run_id: str
    attempt: int
    nonce: str
    launch: str
    override: CommitOverride | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        require_opaque_id(self.nonce, "a process nonce")
        require_opaque_id(self.launch, "a launch identity")


@dataclass(frozen=True, slots=True)
class WorkerComposition:
    """What a worker is composed over, as the composition root supplies it: the effective
    configuration compared with the admission's, the harness revision, the registered
    rules, the system's three protocols (its turns, its preparation and the model client),
    the token counter, the read ports, the approval policy and the checkpoint saver. The
    real fillings are the system's own and the live clients'; a test composes scripted
    ones."""

    configuration: WorkerConfiguration
    harness: HarnessRevision
    rules: Rules
    turns: Turns
    preparation: Preparation
    client: ModelClient
    counter: TokenCounter
    ports: ReadPorts
    approval: ApprovalPolicy
    saver: BaseCheckpointSaver[Any]


def system_content(kind: SystemKind) -> tuple[Turns, Preparation]:
    """The system's content behind the skeleton's two content protocols, by kind (the
    baselines step, fork 15): the investigator's turns over its assets with no preparation;
    the one-call turns over the reader's assets with the single-shot's one search or full
    context's one enumeration; the rules-only turns, which ask nothing, with no preparation
    (the first live run's step, fork 4). The composition root and a probe that mirrors it
    compose from here, so the two cannot drift."""
    match kind:
        case SystemKind.AGENT:
            return InvestigatorTurns(load_prompt_assets(Role.INVESTIGATOR)), NoPreparation()
        case SystemKind.SINGLE_SHOT:
            return OneCallTurns(load_prompt_assets(Role.READER)), SingleShotPreparation()
        case SystemKind.FULL_CONTEXT:
            return OneCallTurns(load_prompt_assets(Role.READER)), FullContextPreparation()
        case SystemKind.RULES_ONLY:
            return RulesOnlyTurns(), NoPreparation()


def work(request: WorkRequest, store: LogStore, composition: WorkerComposition) -> WorkerEnding:
    """Bring the attempt as far as one process can, as the worker does: load, compare the
    configuration, claim, run the graph, and end at one of the worker's endings."""
    worker = Worker(
        store,
        composition.configuration,
        composition.harness,
        request.launch,
        composition.rules,
        composition.turns,
        composition.preparation,
        composition.client,
        composition.counter,
        composition.ports,
        composition.approval,
        composition.saver,
    )
    return worker.work(
        request.run_id, request.attempt, nonce=request.nonce, override=request.override
    )


@dataclass(frozen=True, slots=True)
class TerminalComposition:
    """What the terminal-only path is composed over: the effective configuration compared
    with the admission's, the harness revision and the registered rules; no content, no
    client, no port and no saver, since nothing of the skeleton runs."""

    configuration: WorkerConfiguration
    harness: HarnessRevision
    rules: Rules


def finalize(
    request: WorkRequest, store: LogStore, composition: TerminalComposition
) -> WorkerEnding:
    """Close an attempt whose log holds a recorded stopping failure by that failure, as the
    terminal worker does: load, compare the configuration, claim, close; nothing beyond the
    run log is touched (the first live run's step, fork 9)."""
    worker = TerminalWorker(
        store,
        composition.configuration,
        composition.harness,
        request.launch,
        composition.rules,
    )
    return worker.finalize(
        request.run_id, request.attempt, nonce=request.nonce, override=request.override
    )


# --- review an approval request ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    """Read the review payload an attempt's approval request froze."""

    run_id: str
    attempt: int

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)


@dataclass(frozen=True, slots=True)
class ReviewPayload:
    """The frozen payload as the human reads it, the position of the request that froze it,
    whether an approval is already given, and the digest a delivery must carry."""

    run_id: str
    attempt: int
    position: int
    approved: bool
    payload: JsonObject
    digest: str


def review_approval(
    request: ReviewRequest, store: LogStore, *, rules: Rules
) -> ReviewPayload | CommandRefused:
    """The review payload of the attempt's approval request (``core.review_payload``), or a
    refusal for a closed attempt or one with no request; an approval already given is
    reported beside the payload, not refused, since reading harms nothing."""
    subject = f"run {request.run_id} attempt {request.attempt}"
    state = store.load(request.run_id, request.attempt, rules=rules)
    if state.closed is not None:
        return CommandRefused(subject, f"the attempt is closed at position {state.closed.position}")
    requested = state.approval_requested
    if requested is None:
        return CommandRefused(subject, "no approval is requested")
    assert isinstance(requested.event, ApprovalRequested)
    claims, composition = requested.event.claims, requested.event.composition
    return ReviewPayload(
        request.run_id,
        request.attempt,
        requested.position,
        state.approved is not None,
        review_payload(claims, composition),
        review_payload_digest(claims, composition),
    )


# --- deliver an approval -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApprovalDelivery:
    """A human's approval of the review payload: who, for which attempt, and the digest of
    the payload they saw, which must be the logged request's."""

    run_id: str
    attempt: int
    approver: str
    payload_digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        require_opaque_id(self.approver, "an approver's identity")
        require_digest(self.payload_digest, "the review payload's digest")


@dataclass(frozen=True, slots=True)
class ApprovalDelivered:
    """The approval is in the log at ``position``; the next work command resumes from it."""

    run_id: str
    attempt: int
    position: int


def deliver_approval(
    delivery: ApprovalDelivery, store: LogStore, *, rules: Rules
) -> ApprovalDelivered | CommandRefused:
    """Append the human's approval as an outside producer (the worker group's handoff).
    Refused on a closed attempt, with no approval requested, with one already given under
    another digest, and with a digest that is not the logged request's; a repeat with the
    same digest is the store's receipt."""
    subject = f"run {delivery.run_id} attempt {delivery.attempt}"
    state = store.load(delivery.run_id, delivery.attempt, rules=rules)
    if state.closed is not None:
        return CommandRefused(subject, f"the attempt is closed at position {state.closed.position}")
    request = state.approval_requested
    if request is None:
        return CommandRefused(subject, "no approval is requested")
    assert isinstance(request.event, ApprovalRequested)
    expected = review_payload_digest(request.event.claims, request.event.composition)
    if delivery.payload_digest != expected:
        return CommandRefused(subject, "the digest given is not the requested payload's")
    given = state.approved
    if given is not None:
        assert isinstance(given.event, Approved)
        if given.event.payload_digest == delivery.payload_digest:
            return ApprovalDelivered(delivery.run_id, delivery.attempt, given.position)
        return CommandRefused(subject, f"an approval is already given at position {given.position}")
    result = store.append(
        delivery.run_id,
        delivery.attempt,
        Producer(delivery.approver),
        Approved(Approver.HUMAN, delivery.payload_digest),
        rules=rules,
        state=state,
    )
    match result:
        case Appended(after):
            return ApprovalDelivered(delivery.run_id, delivery.attempt, after.last_position)
        case Received(position):
            return ApprovalDelivered(delivery.run_id, delivery.attempt, position)
        case Refused(reason):
            return CommandRefused(subject, reason)


# --- decline -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeclineDelivery:
    """A human's refusal of the review payload: who, for which attempt, and the digest of
    the payload they saw, which must be the logged request's."""

    run_id: str
    attempt: int
    decider: str
    payload_digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        require_opaque_id(self.decider, "a decider's identity")
        require_digest(self.payload_digest, "the review payload's digest")


@dataclass(frozen=True, slots=True)
class AttemptDeclined:
    """The attempt is closed by the decline at ``position``, its reservation settled."""

    run_id: str
    attempt: int
    position: int


def decline(
    delivery: DeclineDelivery, store: LogStore, *, rules: Rules
) -> AttemptDeclined | CommandRefused:
    """Close the attempt with the human's refusal as an outside producer (the demo
    milestone's live-path step, ruling 4); the store closes and settles in one transaction.
    Refused on an attempt closed by anything but this decline, with no approval requested,
    after an approval was given, and with a digest that is not the logged request's; a
    repeat with the same digest is the decline already made, whether it raced this one at
    the store or came later, since a visitor's second click consumes nothing (ruling 4's
    idempotent admission, read onto the decision). The capability and the deadline that
    gate it on the public surface are the commands step's."""
    subject = f"run {delivery.run_id} attempt {delivery.attempt}"
    state = store.load(delivery.run_id, delivery.attempt, rules=rules)
    closed = state.closed
    if closed is not None:
        held = closed.event
        if isinstance(held, Declined) and held.payload_digest == delivery.payload_digest:
            return AttemptDeclined(delivery.run_id, delivery.attempt, closed.position)
        return CommandRefused(subject, f"the attempt is closed at position {closed.position}")
    request = state.approval_requested
    if request is None:
        return CommandRefused(subject, "no approval is requested")
    given = state.approved
    if given is not None:
        return CommandRefused(subject, f"an approval is already given at position {given.position}")
    assert isinstance(request.event, ApprovalRequested)
    expected = review_payload_digest(request.event.claims, request.event.composition)
    if delivery.payload_digest != expected:
        return CommandRefused(subject, "the digest given is not the requested payload's")
    result = store.close_attempt(
        delivery.run_id,
        delivery.attempt,
        Producer(delivery.decider),
        Declined(delivery.payload_digest, None),
        rules=rules,
        state=state,
    )
    match result:
        case Appended(after):
            return AttemptDeclined(delivery.run_id, delivery.attempt, after.last_position)
        case Received(position):
            return AttemptDeclined(delivery.run_id, delivery.attempt, position)
        case Refused(reason):
            return CommandRefused(subject, reason)


# --- abandon -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AbandonRequest:
    """An operator's decision to close an attempt: who, which, and why."""

    run_id: str
    attempt: int
    authority: str
    reason: AbandonmentReason

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        require_opaque_id(self.authority, "the abandoning authority")


@dataclass(frozen=True, slots=True)
class AttemptAbandoned:
    """The attempt is closed by the abandonment at ``position``; a worker holding
    ``generation_fenced`` stops at its next append."""

    run_id: str
    attempt: int
    generation_fenced: int
    position: int


def abandon(
    request: AbandonRequest, store: LogStore, *, rules: Rules
) -> AttemptAbandoned | CommandRefused:
    """Close the attempt with an abandonment under the authority's identity, fencing the
    generation the load shows; the store closes and settles in one transaction. A closed
    attempt is refused with its position; a repeat is the store's receipt."""
    subject = f"run {request.run_id} attempt {request.attempt}"
    state = store.load(request.run_id, request.attempt, rules=rules)
    if state.closed is not None:
        return CommandRefused(subject, f"the attempt is closed at position {state.closed.position}")
    closing = Abandoned(state.generation, request.reason, None)
    result = store.close_attempt(
        request.run_id,
        request.attempt,
        Producer(request.authority),
        closing,
        rules=rules,
        state=state,
    )
    match result:
        case Appended(after):
            return AttemptAbandoned(
                request.run_id, request.attempt, state.generation, after.last_position
            )
        case Received(position):
            return AttemptAbandoned(request.run_id, request.attempt, state.generation, position)
        case Refused(reason):
            return CommandRefused(subject, reason)


# --- publish -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PublishRequest:
    """Publish one closed attempt's export as the reader at ``reader_commit`` builds it."""

    run_id: str
    attempt: int
    reader_commit: str

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        require_commit(self.reader_commit, "the reader's commit")


def publish(
    request: PublishRequest,
    store: LogStore,
    publisher: RunExportPublisher,
    *,
    rules: Rules,
    reader: Reader = export_of,
) -> PublicationRecord | CommandRefused:
    """The publication in the order the module describes; the record as it stands after
    this command, or a refusal for an open attempt."""
    subject = f"run {request.run_id} attempt {request.attempt}"
    state = store.load(request.run_id, request.attempt, rules=rules)
    if state.closed is None:
        return CommandRefused(subject, "the attempt is open and has no export")
    held = store.publication_of(request.run_id, request.attempt)
    if held is not None and held.state is PublicationStatus.PUBLISHED:
        return held
    closed_log = log_digest(state.events)
    inputs = state.inputs
    assert inputs is not None, "a closed attempt was admitted"
    try:
        export = reader(state)
        content = export_bytes(export)
    except ValueError as exc:
        return store.publication_unbuilt(
            request.run_id,
            request.attempt,
            reader_commit=request.reader_commit,
            export_format=export_format_of(inputs.log_format_version),
            log_digest=closed_log,
            incident=f"the reader could not build the export: {type(exc).__name__}",
        )
    digest = hashlib.sha256(content).hexdigest()
    intended = run_export_key(
        inputs.context.world_version, request.run_id, request.attempt, request.reader_commit
    )
    pending = store.publication_pending(
        request.run_id,
        request.attempt,
        reader_commit=request.reader_commit,
        export_format=export.format_version,
        log_digest=closed_log,
        object_identity=intended,
        object_digest=digest,
    )
    if pending.state is PublicationStatus.PUBLISHED:
        return pending
    try:
        upload = publisher(
            inputs.context.world_version,
            request.run_id,
            request.attempt,
            request.reader_commit,
            content,
        )
    except AccessRefused as exc:
        return store.publication_failed(
            request.run_id,
            request.attempt,
            reader_commit=request.reader_commit,
            object_identity=intended,
            incident=f"the put was refused: {type(exc).__name__}",
        )
    assert upload.key == intended, "the publisher and the command share one key function"
    match upload.outcome:
        case UploadOutcome.CREATED | UploadOutcome.PRESENT_EQUAL:
            return store.publication_published(
                request.run_id, request.attempt, object_identity=intended, object_digest=digest
            )
        case UploadOutcome.PRESENT_UNVERIFIED:
            if (pending.object_identity, pending.object_digest) != (intended, digest):
                return store.publication_failed(
                    request.run_id,
                    request.attempt,
                    reader_commit=request.reader_commit,
                    object_identity=intended,
                    incident="an object is present that this command could not read back, "
                    "under a pending record intending another digest",
                )
            return store.publication_published(
                request.run_id, request.attempt, object_identity=intended, object_digest=digest
            )
        case UploadOutcome.CONFLICT:
            return store.publication_failed(
                request.run_id,
                request.attempt,
                reader_commit=request.reader_commit,
                object_identity=intended,
                incident=(
                    f"the key holds other bytes: sha256 {upload.existing_digest} against {digest}"
                ),
            )


# --- write the inventory -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InventoryRequest:
    """Write the inventory for ``scope`` as the code at ``builder_commit``."""

    scope: InventoryScope
    builder_commit: str

    def __post_init__(self) -> None:
        require_commit(self.builder_commit, "the builder's commit")


@dataclass(frozen=True, slots=True)
class InventoryWritten:
    """The inventory sealed: its identity, its key, what the put did, and the inventory."""

    digest: str
    key: str
    outcome: UploadOutcome
    inventory: Inventory


def write_inventory(
    request: InventoryRequest, store: LogStore, publisher: InventoryPublisher, *, rules: Rules
) -> InventoryWritten:
    """One snapshot of the store, the inventory built from it under ``rules``, sealed at the
    key its digest names; ``ValueError`` for a store whose logs the builder cannot read."""
    snapshot = store.snapshot(request.scope.ledger_id)
    inventory = inventory_of(
        snapshot, request.scope, builder_commit=request.builder_commit, rules=rules
    )
    content = inventory_bytes(inventory)
    digest = inventory_digest(content)
    upload = publisher(request.scope.world_version, content)
    if upload.outcome is UploadOutcome.CONFLICT:
        raise ValueError(
            f"the key {upload.key} holds other bytes than the inventory whose digest names it"
        )
    return InventoryWritten(digest, upload.key, upload.outcome, inventory)


# --- set the threshold -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ThresholdRequest:
    """Set a ledger's spend threshold: the amount, who sets it, under which registration, and
    the registered limit it may not exceed, which the caller reads from the registration."""

    ledger_id: str
    amount_pico_usd: int
    authority: str
    registration_commit: str
    limit_pico_usd: int

    def __post_init__(self) -> None:
        require_opaque_id(self.ledger_id, "a ledger id")
        require_integer(self.amount_pico_usd, "the threshold in pico-dollars")
        require_opaque_id(self.authority, "the authority")
        require_commit(self.registration_commit, "the registration commit")
        require_integer(self.limit_pico_usd, "the registered limit in pico-dollars")


@dataclass(frozen=True, slots=True)
class ImportRequest:
    """Add spend made outside the log to a ledger's total: the request identity the caller
    holds across its retries, the amount, who established it and from what (the authority
    string carries the provenance, the entry having no attempt to point at), and the
    registration commit it is imported under."""

    request_id: str
    ledger_id: str
    amount_pico_usd: int
    authority: str
    registration_commit: str

    def __post_init__(self) -> None:
        require_opaque_id(self.request_id, "an import request id")
        require_opaque_id(self.ledger_id, "a ledger id")
        require_integer(self.amount_pico_usd, "the imported spend in pico-dollars", minimum=1)
        require_opaque_id(self.authority, "the authority")
        require_commit(self.registration_commit, "the registration commit")


def import_spend(request: ImportRequest, store: LogStore) -> LedgerEntry | CommandRefused:
    """The ledger's ``imported`` entry for spend the log never saw, or the entry a replay
    under the same identity already wrote; the store's conflict, other content under a
    recorded identity, as a value."""
    try:
        return store.import_spend(
            request.ledger_id,
            request.amount_pico_usd,
            request_id=request.request_id,
            authority=request.authority,
            registration_commit=request.registration_commit,
        )
    except LogStoreConflict as exc:
        return CommandRefused(f"import request {request.request_id}", str(exc))


def set_threshold(request: ThresholdRequest, store: LogStore) -> LedgerEntry | CommandRefused:
    """The ledger's threshold entry, or the store's refusal as a value (above the limit, or
    below the committed total)."""
    try:
        return store.set_threshold(
            request.ledger_id,
            request.amount_pico_usd,
            authority=request.authority,
            registration_commit=request.registration_commit,
            limit_pico_usd=request.limit_pico_usd,
        )
    except ValueError as exc:
        return CommandRefused(f"ledger {request.ledger_id}", str(exc))


__all__ = [
    "AbandonRequest",
    "ApprovalDelivered",
    "ApprovalDelivery",
    "AttemptAbandoned",
    "AttemptDeclined",
    "CommandRefused",
    "DeclineDelivery",
    "ImportRequest",
    "InventoryRequest",
    "InventoryWritten",
    "PublishRequest",
    "Reader",
    "ReviewPayload",
    "ReviewRequest",
    "TerminalComposition",
    "ThresholdRequest",
    "WorkRequest",
    "WorkerComposition",
    "abandon",
    "admit",
    "decline",
    "deliver_approval",
    "finalize",
    "import_spend",
    "publish",
    "review_approval",
    "set_threshold",
    "work",
    "write_inventory",
]
