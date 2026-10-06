"""The worker: one process's ownership of one attempt, from the load to the ending it leaves.

A worker is started for a run's attempt and does, in this order, what the event log step's
ruling on recovery and endings (part 4) fixes: it loads the state the log folds to, with
the log consulted before any checkpoint; a closed attempt it leaves at once (publication is
the job's); it compares its effective configuration with the frozen inputs and refuses to
claim on a difference (the ruling on admission, part 3); it claims, which opens the next
segment under the next generation and always wins (the ruling on one writer, part 4); a
recorded stopping failure it finalizes by that failure in its category at its site, and
nothing else; otherwise it runs the skeleton on a checkpoint thread named by the run, the
attempt and its generation, so no process ever reads another's checkpoints (the ruling on
recovery, part 5), invoking until the graph ends or pauses at the approval.

*The effective configuration* is the ``FrozenInputs`` this worker's registration and code
would freeze, built from ``WorkerConfiguration`` with five fields copied from the admission
and nothing else: the run and attempt it was started for, the run's context, the admitted
reservation and the log format version, the last checked against the format this code
writes before it is copied. Equality is byte equality; a difference names field names only.

*The approval* (the worker group's second fork). At the pause the worker reads the log
first, so an approval a kill left behind is reused; absent, the policy decides: an automatic
policy appends the approval as an outside producer under its own identity and the worker
resumes on its thread, since it still owns the attempt (the ruling on the event, part 7); a
human approval ends the segment and the worker exits with the attempt open, for the deliver
command to append and a later work command to claim and replay to the interrupt.

*The handler* sits here, around the invocation and never inside a node (the ruling on
recovery, part 8). A refused append is read from the log and never from its reason: a
generation above this worker's is the fence, closed or an ended segment is left as it is, a
recorded stopping failure is finalized, and anything else is this worker's own illegal
event, a defect at the event-append site. The log unavailable leaves the attempt open with
nothing written. A conflict or a broken invariant is a defect at the same site. A stop
signal writes the segment's end where it can and re-raises. Any other exception closes the
attempt by defect at the ``unhandled`` site, the reason a qualified exception type and a
repository-relative location and never a message. Where recording the defect itself fails
the attempt stays open, and a refused terminalization is read once more for closure and
ownership, never recorded as a second defect.

Nothing here logs. The ending names what happened in kinds and field names, and a job that
prints it prints no scenario content.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from leaveimpact.agent.appender import Appender, AppendRefused, LogCommands
from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.graph import (
    DURABILITY,
    INITIAL,
    Harness,
    ModelClient,
    TokenCounter,
    Turns,
    build,
)
from leaveimpact.agent.log_events import (
    LOG_FORMAT_VERSION,
    ApprovalRequested,
    Approved,
    CommitOverride,
    Failed,
    FrozenInputs,
    Producer,
    SegmentEnded,
    kind_of,
)
from leaveimpact.agent.log_store import (
    LogStoreConflict,
    LogStoreInvariantBroken,
    LogStoreUnavailable,
)
from leaveimpact.agent.log_transition import Appended, AttemptState, Received, Refused, Rules
from leaveimpact.core.attribution import RedispatchPolicy
from leaveimpact.core.call_settings import CallConfiguration
from leaveimpact.core.model_calls import RefusedBy
from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_ending import (
    Approver,
    ClaimAuthor,
    ComposingPolicy,
    HarnessSite,
    HarnessSiteName,
)
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.core.run_record import (
    Caps,
    FailureCategory,
    OutageAssignment,
    PrefetchRule,
    PricingBasis,
    PricingSelection,
    Retrieval,
    System,
)
from leaveimpact.core.run_timing import HarnessRevision

REPOSITORY = Path(__file__).resolve().parents[3]
"""The tree a defect's location is written relative to."""

COPIED_FROM_THE_ADMISSION = (
    "run_id",
    "attempt",
    "context",
    "reservation_pico_usd",
    "log_format_version",
)
"""The frozen fields a worker takes from the admission: what identifies the admitted job and
its durable allowance. Everything else it derives from its own registration and code."""


# --- The effective configuration -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkerConfiguration:
    """Every frozen input but the five copied from the admission, as this worker's
    registration and code give them; the field names are ``FrozenInputs``'s."""

    preregistration_commit: str
    system: System
    retrieval: Retrieval
    caps: Caps
    model_configurations: tuple[tuple[str, CallConfiguration], ...]
    pricing_selections: tuple[tuple[str, PricingSelection], ...]
    counting_identifiers: tuple[tuple[str, str], ...]
    pricing: PricingBasis
    prompt_digests: tuple[tuple[str, str, str], ...]
    tool_surface_digests: tuple[tuple[str, str], ...]
    attribution_table: str | None
    redispatch: RedispatchPolicy | None
    retry: RetryRule
    prefetch_rule: PrefetchRule
    composing_policy: ComposingPolicy
    claim_author: ClaimAuthor
    parser: RefusedBy
    outage: OutageAssignment
    corpus_level: str

    def frozen_for(self, admitted: FrozenInputs) -> FrozenInputs:
        """The inputs this configuration would freeze for ``admitted``'s job: the five copied
        fields from the admission, the rest from here. The log format is checked against the
        one this code writes before it is copied (the ruling on recovery, part 7)."""
        if admitted.log_format_version != LOG_FORMAT_VERSION:
            raise ValueError(
                f"this worker writes log format {LOG_FORMAT_VERSION}; the attempt holds "
                f"{admitted.log_format_version}"
            )
        own = {f.name: getattr(self, f.name) for f in fields(self)}
        copied = {name: getattr(admitted, name) for name in COPIED_FROM_THE_ADMISSION}
        return FrozenInputs(**own, **copied)

    @classmethod
    def of(cls, inputs: FrozenInputs) -> WorkerConfiguration:
        """The configuration that would freeze ``inputs`` again: every field but the copied
        five, read off them. For a composition root that holds the admitted inputs, and
        for tests."""
        return cls(**{f.name: getattr(inputs, f.name) for f in fields(cls)})


def configuration_difference(admitted: FrozenInputs, effective: FrozenInputs) -> tuple[str, ...]:
    """The names of the frozen fields on which the two differ, in declaration order; empty
    when the worker selected the admitted inputs."""
    return tuple(
        f.name
        for f in fields(FrozenInputs)
        if getattr(admitted, f.name) != getattr(effective, f.name)
    )


# --- The approval policy ---------------------------------------------------------------------


class ApprovalPolicy(Protocol):
    """Who approves at the pause: the outside producer an automatic policy appends under,
    or ``None`` when a human decides later and the worker is to end its segment."""

    def approver(self, state: AttemptState) -> Producer | None: ...


@dataclass(frozen=True, slots=True)
class AutomaticApproval:
    """The measurement convention: every requested payload is approved at once, under the
    policy's identity (``agent/approval.py`` says why this authorizes nothing)."""

    identity: str = "policy:automatic"

    def approver(self, state: AttemptState) -> Producer | None:
        return Producer(self.identity)


@dataclass(frozen=True, slots=True)
class HumanApproval:
    """A human decides outside this process: the worker ends its segment and waits."""

    def approver(self, state: AttemptState) -> Producer | None:
        return None


# --- The ending ------------------------------------------------------------------------------


class WorkerEndingKind(StrEnum):
    """What one worker's execution left behind."""

    CLOSED_ALREADY = "closed_already"
    """The attempt was closed before this worker could act, at the load or by another."""
    CONFIGURATION_MISMATCH = "configuration_mismatch"
    """The effective configuration differs from the frozen inputs; nothing was claimed."""
    CLAIM_REFUSED = "claim_refused"
    """The claim was refused; no segment opened."""
    CLOSED = "closed"
    """This worker closed the attempt; the detail is the closing event's kind."""
    AWAITING_APPROVAL = "awaiting_approval"
    """The segment ended at the approval request for a human to decide."""
    FENCED = "fenced"
    """A later claim took the attempt; this worker wrote nothing after it."""
    SEGMENT_ENDED = "segment_ended"
    """The segment had ended when an append was tried; nothing more was written."""
    LEFT_OPEN = "left_open"
    """The log was unavailable, or recording the ending failed; the attempt stays open."""


@dataclass(frozen=True, slots=True)
class WorkerEnding:
    """The worker's result: kinds, the generation it ran under when it claimed, and a detail
    of field names or kinds. No content of the run is in it."""

    kind: WorkerEndingKind
    run_id: str
    attempt: int
    generation: int | None
    detail: str


# --- The worker ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Worker:
    """One worker's composition: the log, its configuration and provenance, the system's
    fillings and the seams. ``work`` is the command."""

    store: LogCommands
    configuration: WorkerConfiguration
    harness: HarnessRevision
    launch: str
    rules: Rules
    turns: Turns
    client: ModelClient
    counter: TokenCounter
    ports: ReadPorts
    approval: ApprovalPolicy
    saver: BaseCheckpointSaver[Any]
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    boundary: Callable[[str], None] = lambda name: None
    """Named points of the approval handoff a crash check kills at, beside the store's own
    boundaries and the saver's seams; a no-op in production."""

    def work(
        self, run_id: str, attempt: int, *, nonce: str, override: CommitOverride | None = None
    ) -> WorkerEnding:
        """Bring the attempt as far as this process can: see the module for the order."""
        try:
            state = self.store.load(run_id, attempt, rules=self.rules)
        except LogStoreUnavailable:
            return WorkerEnding(
                WorkerEndingKind.LEFT_OPEN, run_id, attempt, None, "log unavailable"
            )
        inputs = state.inputs
        assert inputs is not None
        if state.closed is not None:
            return WorkerEnding(
                WorkerEndingKind.CLOSED_ALREADY,
                run_id,
                attempt,
                state.generation,
                _closing_kind(state),
            )
        differing = configuration_difference(inputs, self.configuration.frozen_for(inputs))
        if differing:
            return WorkerEnding(
                WorkerEndingKind.CONFIGURATION_MISMATCH,
                run_id,
                attempt,
                state.generation,
                ", ".join(differing),
            )
        try:
            claimed = self.store.claim(
                run_id,
                attempt,
                harness=self.harness,
                nonce=nonce,
                launch=self.launch,
                rules=self.rules,
                override=override,
                state=state,
            )
        except LogStoreUnavailable:
            return WorkerEnding(
                WorkerEndingKind.LEFT_OPEN, run_id, attempt, None, "log unavailable"
            )
        match claimed:
            case Refused():
                return WorkerEnding(
                    WorkerEndingKind.CLAIM_REFUSED,
                    run_id,
                    attempt,
                    state.generation,
                    "claim refused",
                )
            case Received():
                raise RuntimeError("a fresh nonce was received as a repeated claim")
            case Appended(state=after):
                pass
        appender = Appender.after_claim(
            self.store, after, rules=self.rules, monotonic=self.monotonic
        )
        return self._run(appender)

    # --- the run and its handler -------------------------------------------------------

    def _run(self, appender: Appender) -> WorkerEnding:
        try:
            if appender.state.stopped is not None:
                return self._finalize(appender)
            harness = Harness(
                appender,
                self.turns,
                self.client,
                self.counter,
                self.ports,
                self.sleep,
                self.boundary,
            )
            graph = build(harness, self.saver)
            config = self._thread(appender)
            graph.invoke(INITIAL, config, durability=DURABILITY)
            while graph.get_state(config).interrupts:
                ending = self._approve(appender)
                if ending is not None:
                    return ending
                self.boundary("approval:delivered")
                graph.invoke(
                    Command(resume=_requested_digest(appender.state)), config, durability=DURABILITY
                )
            if appender.state.closed is None:
                raise RuntimeError("the graph ended without closing the attempt")
            return self._ending(appender, WorkerEndingKind.CLOSED, _closing_kind(appender.state))
        except AppendRefused as refused:
            return self._refused(appender, refused)
        except LogStoreUnavailable:
            return self._ending(appender, WorkerEndingKind.LEFT_OPEN, "log unavailable")
        except (LogStoreConflict, LogStoreInvariantBroken) as fault:
            return self._record_defect(appender, HarnessSiteName.EVENT_APPEND, fault)
        except (KeyboardInterrupt, SystemExit):
            self._end_segment(appender)
            raise
        except Exception as exc:
            return self._record_defect(appender, HarnessSiteName.UNHANDLED, exc)

    def _thread(self, appender: Appender) -> RunnableConfig:
        thread = f"{appender.run_id}/{appender.attempt}/{appender.generation}"
        return {"configurable": {"thread_id": thread}}

    def _approve(self, appender: Appender) -> WorkerEnding | None:
        """At the pause: the logged approval reused, else the policy's, else the segment's end."""
        state = appender.state
        if state.approved is not None:
            return None
        producer = self.approval.approver(state)
        if producer is None:
            appender.append(SegmentEnded())
            return self._ending(appender, WorkerEndingKind.AWAITING_APPROVAL, "approval requested")
        event = Approved(Approver.AUTOMATIC, _requested_digest(state))
        appended = self.store.append(
            appender.run_id, appender.attempt, producer, event, rules=self.rules, state=state
        )
        match appended:
            case Appended(state=after):
                appender.state = after
            case Received():
                appender.state = self.store.load(
                    appender.run_id, appender.attempt, rules=self.rules
                )
            case Refused():
                raise AppendRefused(appended, event)
        return None

    def _refused(self, appender: Appender, refused: AppendRefused) -> WorkerEnding:
        """The first fork: what the log says a refusal meant."""
        try:
            latest = self.store.load(appender.run_id, appender.attempt, rules=self.rules)
        except LogStoreUnavailable:
            return self._ending(appender, WorkerEndingKind.LEFT_OPEN, "log unavailable")
        settled = self._settled_elsewhere(appender, latest)
        if settled is not None:
            return settled
        appender.state = latest
        if latest.stopped is not None:
            return self._finalize(appender)
        return self._record_defect(appender, HarnessSiteName.EVENT_APPEND, refused)

    def _settled_elsewhere(self, appender: Appender, latest: AttemptState) -> WorkerEnding | None:
        if latest.closed is not None:
            return self._ending(appender, WorkerEndingKind.CLOSED_ALREADY, _closing_kind(latest))
        if latest.generation != appender.generation:
            return self._ending(
                appender, WorkerEndingKind.FENCED, f"generation {latest.generation}"
            )
        current = latest.current_segment
        if current is not None and current.ended:
            return self._ending(appender, WorkerEndingKind.SEGMENT_ENDED, "segment ended")
        return None

    def _finalize(self, appender: Appender) -> WorkerEnding:
        stopped = appender.state.stopped
        assert stopped is not None
        closing = Failed(stopped.category, stopped.site, stopped.reason, None)
        return self._close(appender, closing)

    def _record_defect(
        self, appender: Appender, site: HarnessSiteName, fault: BaseException
    ) -> WorkerEnding:
        closing = Failed(FailureCategory.DEFECT, HarnessSite(site), _reason(fault), None)
        return self._close(appender, closing)

    def _close(self, appender: Appender, closing: Failed) -> WorkerEnding:
        """The closing event, once; a refusal is read for closure and ownership and never
        recorded as a second defect; a store fault leaves the attempt open."""
        try:
            appender.close(closing)
        except AppendRefused:
            try:
                latest = self.store.load(appender.run_id, appender.attempt, rules=self.rules)
            except LogStoreUnavailable:
                return self._ending(appender, WorkerEndingKind.LEFT_OPEN, "log unavailable")
            settled = self._settled_elsewhere(appender, latest)
            if settled is not None:
                return settled
            return self._ending(appender, WorkerEndingKind.LEFT_OPEN, "terminalization refused")
        except (LogStoreUnavailable, LogStoreConflict, LogStoreInvariantBroken):
            return self._ending(appender, WorkerEndingKind.LEFT_OPEN, "recording failed")
        return self._ending(appender, WorkerEndingKind.CLOSED, kind_of(closing).value)

    def _end_segment(self, appender: Appender) -> None:
        """Best effort on a stop signal: the segment's end where an append is still possible."""
        try:
            appender.append(SegmentEnded())
        except (AppendRefused, LogStoreUnavailable, LogStoreConflict, LogStoreInvariantBroken):
            return

    def _ending(self, appender: Appender, kind: WorkerEndingKind, detail: str) -> WorkerEnding:
        return WorkerEnding(kind, appender.run_id, appender.attempt, appender.generation, detail)


# --- Readers ---------------------------------------------------------------------------------


def _closing_kind(state: AttemptState) -> str:
    closing = state.closing
    assert closing is not None
    return kind_of(closing).value


def _requested_digest(state: AttemptState) -> str:
    request = state.approval_requested
    assert request is not None and isinstance(request.event, ApprovalRequested)
    return review_payload_digest(request.event.claims, request.event.composition)


def _reason(fault: BaseException) -> str:
    """The qualified type and the innermost repository-relative location of ``fault``; for a
    refused append, the refused event's kind beside them. No message, excerpt or local."""
    qualified = f"{type(fault).__module__}.{type(fault).__qualname__}"
    located = "outside the repository"
    for frame in traceback.extract_tb(fault.__traceback__):
        path = Path(frame.filename)
        if path.is_relative_to(REPOSITORY):
            located = f"{path.relative_to(REPOSITORY).as_posix()}:{frame.lineno}"
    reason = f"{qualified} at {located}"
    if isinstance(fault, AppendRefused):
        reason = f"{reason}: {kind_of(fault.event).value} refused"
    return reason


__all__ = [
    "COPIED_FROM_THE_ADMISSION",
    "ApprovalPolicy",
    "AutomaticApproval",
    "HumanApproval",
    "Worker",
    "WorkerConfiguration",
    "WorkerEnding",
    "WorkerEndingKind",
    "configuration_difference",
]
