"""One run attempt, whole: the artifact the agent writes once and the evaluator grades.

The export is the one serialized object a run attempt leaves behind (the investigator
milestone's second build step, ruling 1): projected from the event log after the
attempt reaches its terminal state, written once by conditional create under the
run-and-attempt identity, and the sole thing the evaluator reads about the run, since
it never re-reads a vendor. It lives in ``core`` as plain data because the agent
writes it and the evaluator reads it and neither may import the other; both speak this
shape and the codec beside it. An export is terminal-only and immutable: a run paused
at an approval or recoverable from a checkpoint is a state of the log, never an export.

Three blocks, each with its own job. The *context* is what changes the evidence
(the scenario, the world version, the leave, ``now``), the reproducibility boundary
``RunContext`` already states. The *record* is provenance, what ran under what. The
*trace* is what the run did, what the grading replays: the model calls with their
dispatches, the reads, the claims and how they were composed. The export is
self-identifying by run id and attempt at its top, beside the format version, so it does
not depend on its object key for identity; its digest is computed from its canonical
bytes by whoever cites it and never stored inside, which would define it circularly.

The format version is the tree's own contract. Structural fields a replay cannot do
without are required per version, an incompatible change bumps the version and an
unknown version refuses; the extensible blocks (the usage counters, the provenance
names) follow a declared append-only order within a version, so a field appended
later reads as unavailable from an older export and the codec learns nothing.

This is format 2 (the contract step's rulings). Format 1 gave a model call one outcome
and one send, a run one process and one duration, a failure one of two anchors, and
costs in nano-dollars; what replaced each is stated where it lives (``model_calls``,
``run_timing``, ``run_ending``, ``run_record``). Nothing reads format 1: its bytes refuse
by version.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.claims import Claim
from leaveimpact.core.model_calls import (
    AsOperation,
    AttributionKind,
    CallState,
    CompleteResponse,
    Dispatch,
    ModelCall,
    Sends,
)
from leaveimpact.core.run_ending import (
    ClaimAuthor,
    Composition,
    DispatchPhase,
    DispatchSite,
    HarnessSite,
    OperationSite,
    ReservationState,
)
from leaveimpact.core.run_record import (
    Failure,
    FailureCategory,
    RunRecord,
    SystemKind,
    TerminalStatus,
)
from leaveimpact.core.run_trace import (
    DefectOutcome,
    ModelCallId,
    ModelOrigin,
    Operation,
    OperationId,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    require_integer,
    require_opaque_id,
)
from leaveimpact.core.worldtime import RunContext

EXPORT_FORMAT_VERSION = 2
"""The format this code writes and reads; a decoder refuses any other."""


@dataclass(frozen=True, slots=True)
class RunTrace:
    """The model calls, the attempted reads, the final claims and their composition.

    Calls and operations keep the order they happened in. Claims are held in claim-id
    order, the claim codec's own, since a claim's position says nothing (its id is its
    identity and the grading matches by key), and one order means the export's bytes
    are a property of the trace and not of the emission. Identifiers are unique within
    their kind.

    The structural facts a replay stands on are held here. Every operation has its
    position, and positions are one order over the whole trace: no two events share one,
    operations are in position order, and so are the calls' first intents. A read the
    model asked for and the tool call that asked for it name each other: the operation's
    origin is a call this trace holds, whose answer has exactly one tool call that became
    that operation, and the read was logged after that call's answer. An input read of a
    dispatch is an operation the trace holds, logged before the dispatch's intent.

    What the record block claims about the trace (the cumulative usage, the observed
    condition) is not enforced here: the evaluator verifies a claim against the trace,
    and a constructor that enforced it would hide the mismatch the verification exists to
    report.
    """

    model_calls: tuple[ModelCall, ...]
    operations: tuple[Operation, ...]
    claims: tuple[Claim, ...]
    composition: Composition

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "claims", tuple(sorted(self.claims, key=lambda claim: claim.claim_id))
        )
        call_ids = [call.id for call in self.model_calls]
        if len(set(call_ids)) != len(call_ids):
            raise ValueError("model call ids are unique within a trace")
        operation_ids = [operation.id for operation in self.operations]
        if len(set(operation_ids)) != len(operation_ids):
            raise ValueError("operation ids are unique within a trace")
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("claim ids are unique within a trace")
        self._require_one_event_order()
        self._require_tool_calls_and_operations_to_agree()
        self._require_reads_to_follow_their_answer()
        self._require_input_reads_to_precede()

    def _require_one_event_order(self) -> None:
        read_at: list[int] = []
        for operation in self.operations:
            if operation.position is None:
                raise ValueError(f"operation {operation.id} of a trace holds no position")
            read_at.append(operation.position)
        if read_at != sorted(read_at):
            raise ValueError("operations are held in position order")
        first_intents = [call.dispatches[0].intent_position for call in self.model_calls]
        if first_intents != sorted(first_intents):
            raise ValueError("model calls are held in the order of their first intents")
        positions = [*read_at]
        for dispatch in self.dispatches:
            positions.append(dispatch.intent_position)
            if dispatch.outcome_position is not None:
                positions.append(dispatch.outcome_position)
        if len(set(positions)) != len(positions):
            raise ValueError("no two events of a trace share a position")

    def _require_tool_calls_and_operations_to_agree(self) -> None:
        asked: dict[OperationId, ModelCallId] = {}
        for call in self.model_calls:
            if call.answer is None:
                continue
            for tool_call in call.answer.tool_calls:
                if not isinstance(tool_call.disposition, AsOperation):
                    continue
                operation = tool_call.disposition.operation
                if operation in asked:
                    raise ValueError(f"operation {operation} is the disposition of two tool calls")
                asked[operation] = call.id
        for operation in self.operations:
            origin = operation.origin
            if not isinstance(origin, ModelOrigin):
                if operation.id in asked:
                    raise ValueError(
                        f"tool call of {asked[operation.id]} became operation {operation.id}, "
                        "which no model call asked for"
                    )
                continue
            if self.model_call_or_none(origin.model_call) is None:
                raise ValueError(
                    f"operation {operation.id} answers model call {origin.model_call!r}, "
                    "which the trace does not hold"
                )
            if asked.get(operation.id) != origin.model_call:
                raise ValueError(
                    f"operation {operation.id} answers model call {origin.model_call!r}, "
                    "whose answer holds no tool call that became it"
                )
        held = set(operation.id for operation in self.operations)
        for operation, call_id in asked.items():
            if operation not in held:
                raise ValueError(
                    f"a tool call of {call_id} became operation {operation}, which the trace "
                    "does not hold"
                )

    def _require_reads_to_follow_their_answer(self) -> None:
        for operation in self.operations:
            origin = operation.origin
            if not isinstance(origin, ModelOrigin):
                continue
            answered_at = self.model_call(origin.model_call).dispatches[-1].outcome_position
            if answered_at is None or operation.position is None:
                continue
            if operation.position < answered_at:
                raise ValueError(
                    f"operation {operation.id} answers model call {origin.model_call!r} and "
                    "was logged before that call's answer"
                )

    def _require_input_reads_to_precede(self) -> None:
        position_of = {operation.id: operation.position for operation in self.operations}
        for call in self.model_calls:
            for dispatch in call.dispatches:
                for read in dispatch.input_reads:
                    logged = position_of.get(read)
                    if logged is None:
                        raise ValueError(
                            f"dispatch {dispatch.number} of {call.id} was shown operation "
                            f"{read}, which the trace does not hold"
                        )
                    if logged > dispatch.intent_position:
                        raise ValueError(
                            f"dispatch {dispatch.number} of {call.id} was shown operation "
                            f"{read}, which was logged after its intent"
                        )

    @property
    def dispatches(self) -> tuple[Dispatch, ...]:
        """Every dispatch of every call, in the calls' order."""
        return tuple(dispatch for call in self.model_calls for dispatch in call.dispatches)

    def model_call(self, id: ModelCallId) -> ModelCall:
        """The model call ``id`` names; ``KeyError`` is a bug, the constructor checked."""
        for call in self.model_calls:
            if call.id == id:
                return call
        raise KeyError(id)

    def operation(self, id: OperationId) -> Operation | None:
        """The operation ``id`` names, or ``None``."""
        for operation in self.operations:
            if operation.id == id:
                return operation
        return None

    def model_call_or_none(self, id: ModelCallId) -> ModelCall | None:
        """The model call ``id`` names, or ``None``."""
        for call in self.model_calls:
            if call.id == id:
                return call
        return None


@dataclass(frozen=True, slots=True)
class RunExport:
    """The export of one run attempt: identity, context, record, trace.

    The constructor checks what makes the tree one object: the format is this code's,
    the identity is usable, a recorded failure points at what the trace holds for its
    site, every role the trace's calls name has a configuration in the record, every
    dispatch ran in a segment the record holds, a complete response nobody parsed is the
    failure's own, the cumulative cost is absent exactly when no dispatch was priced, a
    reservation is reconciled only when every send was priced whole, and a rules-only
    export holds no model call. What the record claims about the trace's numbers is left
    to the evaluator to verify, since a mismatch there is a finding and not a
    construction error.
    """

    format_version: int
    run_id: str
    attempt: int
    context: RunContext
    record: RunRecord
    trace: RunTrace

    def __post_init__(self) -> None:
        require_integer(self.format_version, "the format version")
        if self.format_version != EXPORT_FORMAT_VERSION:
            raise ValueError(
                f"this code builds export format {EXPORT_FORMAT_VERSION}, got {self.format_version}"
            )
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt", minimum=1)
        if self.record.system.kind is SystemKind.RULES_ONLY:
            _require_a_rules_only_trace(self.trace)
        _require_one_order_with_the_approval(self.record, self.trace)
        if self.record.status is not TerminalStatus.FAILED:
            for call in self.trace.model_calls:
                if call.state is CallState.UNRESOLVED:
                    raise ValueError(
                        f"model call {call.id} is unresolved in an attempt that did not fail; "
                        "an unresolved call is asked again or ends the attempt"
                    )
        failure = self.record.failure
        if failure is not None:
            _require_failure_at_its_fault(failure, self.trace)
        configured = {role for role, _ in self.record.model_configurations}
        segments = len(self.record.timing.segments)
        for call in self.trace.model_calls:
            if call.role not in configured:
                raise ValueError(
                    f"model call {call.id} ran as {call.role!r}, a role with no recorded "
                    "model configuration"
                )
            for dispatch in call.dispatches:
                if dispatch.segment > segments:
                    raise ValueError(
                        f"dispatch {dispatch.number} of {call.id} ran in segment "
                        f"{dispatch.segment}, which the record does not hold"
                    )
            _require_an_unparsed_response_to_be_the_failure(call, failure)
        dispatches = self.trace.dispatches
        priced = any(dispatch.cost is not None for dispatch in dispatches)
        if (self.record.cost is None) == priced:
            raise ValueError("a cumulative cost is recorded exactly when a dispatch was priced")
        reservation = self.record.reservation
        if reservation is not None and reservation.state is ReservationState.RECONCILED:
            if self.record.cost is not None and not self.record.cost.complete:
                raise ValueError(
                    "an incomplete cumulative cost never carries a reconciled reservation"
                )
            for dispatch in dispatches:
                if dispatch.sends is not Sends.NONE and (
                    dispatch.cost is None or not dispatch.cost.complete
                ):
                    raise ValueError(
                        "a reservation is reconciled only when every send was priced whole; "
                        f"dispatch {dispatch.number} at position {dispatch.intent_position} "
                        "was not"
                    )


def _require_a_rules_only_trace(trace: RunTrace) -> None:
    """Rules only is the frozen prefetch and the shared rules: no model call, no read of any
    other origin, and claims the rules composed."""
    if trace.model_calls:
        raise ValueError("a rules-only export holds no model call")
    for operation in trace.operations:
        if not isinstance(operation.origin, PrefetchOrigin):
            raise ValueError(
                f"operation {operation.id} of a rules-only export is not the prefetch's"
            )
    if trace.composition.author is not ClaimAuthor.RULES:
        raise ValueError("a rules-only export's claims were composed by the rules")


def _require_one_order_with_the_approval(record: RunRecord, trace: RunTrace) -> None:
    """The approval's two stamps are events of the same order as the reads and the
    dispatches: no position shared, and whatever carries a segment (a dispatch's intent, a
    stamp) never goes back to an earlier segment as positions rise."""
    stamps = [
        stamp
        for stamp in (record.timing.approval_requested, record.timing.approval_resumed)
        if stamp is not None
    ]
    taken = {operation.position for operation in trace.operations}
    for dispatch in trace.dispatches:
        taken.add(dispatch.intent_position)
        taken.add(dispatch.outcome_position)
    for stamp in stamps:
        if stamp.position in taken:
            raise ValueError(
                f"the approval's stamp at position {stamp.position} shares it with another "
                "event of the trace"
            )
    in_segments = sorted(
        [(dispatch.intent_position, dispatch.segment) for dispatch in trace.dispatches]
        + [(stamp.position, stamp.segment) for stamp in stamps]
    )
    for (_, earlier), (position, later) in zip(in_segments, in_segments[1:], strict=False):
        if later < earlier:
            raise ValueError(
                f"the event at position {position} ran in segment {later}, after one of "
                f"segment {earlier}"
            )


def _require_an_unparsed_response_to_be_the_failure(
    call: ModelCall, failure: Failure | None
) -> None:
    last = call.dispatches[-1]
    if call.answer is not None or not isinstance(last.observation, CompleteResponse):
        return
    site = None if failure is None else failure.site
    if (
        not isinstance(site, DispatchSite)
        or site.model_call != call.id
        or site.dispatch != last.number
        or site.phase not in (DispatchPhase.PARSE, DispatchPhase.RECORD)
    ):
        raise ValueError(
            f"model call {call.id} holds a complete response and no answer; a response is "
            "left unparsed only by the failure that ended the attempt there"
        )


def _require_failure_at_its_fault(failure: Failure, trace: RunTrace) -> None:
    site = failure.site
    match site:
        case OperationSite():
            # A fault at an operation is a defect, found at one that returned something: a
            # record the adapter could not translate, or returned records the harness could
            # not accept (the source contradicting the run's premise, a record no fact can
            # be made from; the investigator milestone's fifth build step, ruling 4). An
            # unreachable or a refused operation read nothing, and an absent answer is
            # evidence, not a fault: none of them anchors a defect.
            operation = trace.operation(site.operation)
            if (
                failure.category is not FailureCategory.DEFECT
                or operation is None
                or not isinstance(operation.outcome, DefectOutcome | RecordOutcome | RecordsOutcome)
            ):
                raise ValueError(
                    "a failure at an operation is a defect at one that read a malformed "
                    "record or returned records the harness could not accept, got "
                    f"{failure.category.value} at {site.operation!r}"
                )
        case DispatchSite():
            call = trace.model_call_or_none(site.model_call)
            if call is None or site.dispatch > len(call.dispatches):
                raise ValueError(
                    f"a failure names dispatch {site.dispatch} of model call "
                    f"{site.model_call!r}, which the trace does not hold"
                )
            at = call.dispatches[site.dispatch - 1]
            arrived = isinstance(at.observation, CompleteResponse)
            if site.phase in (DispatchPhase.PARSE, DispatchPhase.RECORD):
                # A fault found while reading or recording a response is found at one that
                # arrived, which the dispatch preserves.
                if not arrived:
                    raise ValueError(
                        f"a failure at the {site.phase.value} of a dispatch names one whose "
                        "response arrived"
                    )
                return
            if site.phase is not DispatchPhase.SEND:
                return
            # At the send the failure is the observation's own: it is the call's last
            # dispatch, nothing whole arrived, and its category is the reading the dispatch
            # already holds. An unresolved history that exhausted the re-dispatch bound
            # fails by infrastructure, anchored at its last dispatch.
            if site.dispatch != len(call.dispatches) or arrived:
                raise ValueError(
                    "a failure at the send names a call's last dispatch, one no complete "
                    "response arrived for"
                )
            read_as = at.attribution.kind
            expected = (
                (AttributionKind.DEFECT,)
                if failure.category is FailureCategory.DEFECT
                else (AttributionKind.INFRASTRUCTURE, AttributionKind.UNRESOLVED)
            )
            if read_as not in expected:
                raise ValueError(
                    f"a failure by {failure.category.value} at the send of a dispatch read "
                    f"as {read_as.value}"
                )
        case HarnessSite():
            return
