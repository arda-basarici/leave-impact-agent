"""One run attempt, whole: the artifact the agent writes once and the evaluator grades.

The export is the one serialized object a run attempt leaves behind (the investigator
milestone's second build step, ruling 1): projected from the event log after the
attempt reaches its terminal state, written once by conditional create under the
run-and-attempt identity, and the sole thing the evaluator reads about the run, since
it never re-reads a vendor. It lives in ``core`` as plain data because the agent
writes it and the evaluator reads it and neither may import the other; both speak this
shape and the codec beside it.

Three blocks, each with its own job. The *context* is what changes the evidence
(the scenario, the world version, the leave, ``now``), the reproducibility boundary
``RunContext`` already states. The *record* is provenance, what ran under what. The
*trace* is what the run did, what the grading replays. The export is self-identifying
by run id and attempt at its top, beside the format version, so it does not depend on
its object key for identity; its digest is computed from its canonical bytes by
whoever cites it and never stored inside, which would define it circularly.

The format version is the tree's own contract. Structural fields a replay cannot do
without are required per version, an incompatible change bumps the version and an
unknown version refuses; the extensible blocks (the usage counters, the provenance
names) follow a declared append-only order within a version, so a field appended
later reads as unavailable from an older export and the codec learns nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.run_record import FailureCategory, RunRecord, SystemKind
from leaveimpact.core.run_trace import (
    DefectOutcome,
    ModelCallId,
    ModelCallOutcome,
    OperationId,
    RunTrace,
    is_completed_read,
    require_integer,
    require_opaque_id,
)
from leaveimpact.core.worldtime import RunContext

EXPORT_FORMAT_VERSION = 1
"""The format this code writes and reads; a decoder refuses any other."""


@dataclass(frozen=True, slots=True)
class RunExport:
    """The export of one run attempt: identity, context, record, trace.

    The constructor checks what makes the tree one object: the format is this code's,
    the identity is usable, a recorded failure points at the trace entry of its own
    kind (a defect at the operation the fault was found at, an infrastructure fault at
    a model call the provider failed), every role the trace's calls name has a
    configuration in the record, the cumulative cost is absent exactly when no call was
    priced, and a rules-only export holds no model call. What the record claims about
    the trace's numbers is left to the evaluator to verify, since a mismatch there is a
    finding and not a construction error.
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
        if self.record.system.kind is SystemKind.RULES_ONLY and self.trace.model_calls:
            raise ValueError("a rules-only export holds no model call")
        failure = self.record.failure
        if failure is not None:
            _require_failure_at_its_fault(failure.category, failure.at, self.trace)
        configured = {role for role, _ in self.record.model_configurations}
        for call in self.trace.model_calls:
            if call.role not in configured:
                raise ValueError(
                    f"model call {call.id} ran as {call.role!r}, a role with no recorded "
                    "model configuration"
                )
        priced = any(call.cost is not None for call in self.trace.model_calls)
        if (self.record.cost is None) == priced:
            raise ValueError("a cumulative cost is recorded exactly when a call was priced")


def _require_failure_at_its_fault(category: FailureCategory, at: str, trace: RunTrace) -> None:
    # A defect is found at an operation that read something: a record the adapter could
    # not translate, or a completed read whose records the harness could not accept (the
    # source contradicting the run's premise, a record no fact can be made from; the
    # investigator milestone's fifth build step, ruling 4). An unreachable or a refused
    # operation read nothing and anchors no defect.
    if category is FailureCategory.DEFECT:
        operation = trace.operation(OperationId(at))
        if operation is None or not (
            isinstance(operation.outcome, DefectOutcome) or is_completed_read(operation.outcome)
        ):
            raise ValueError(
                "a defect failure names an operation that read a malformed record or a "
                f"completed read the harness could not accept, got {at!r}"
            )
        return
    call = trace.model_call_or_none(ModelCallId(at))
    if call is None or call.outcome is not ModelCallOutcome.PROVIDER_FAULT:
        raise ValueError(
            f"an infrastructure failure names a model call the provider failed, got {at!r}"
        )
