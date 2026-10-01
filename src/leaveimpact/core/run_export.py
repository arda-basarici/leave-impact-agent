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

from leaveimpact.core.run_record import RunRecord, SystemKind
from leaveimpact.core.run_trace import RunTrace, require_opaque_id
from leaveimpact.core.worldtime import RunContext

EXPORT_FORMAT_VERSION = 1
"""The format this code writes and reads; a decoder refuses any other."""


@dataclass(frozen=True, slots=True)
class RunExport:
    """The export of one run attempt: identity, context, record, trace.

    The constructor checks what makes the tree one object: the format is this code's,
    the identity is usable, a recorded failure points into the trace, and a rules-only
    export holds no model call. What the record claims about the trace is left to the
    evaluator to verify, since a mismatch there is a finding and not a construction error.
    """

    format_version: int
    run_id: str
    attempt: int
    context: RunContext
    record: RunRecord
    trace: RunTrace

    def __post_init__(self) -> None:
        if self.format_version != EXPORT_FORMAT_VERSION:
            raise ValueError(
                f"this code builds export format {EXPORT_FORMAT_VERSION}, got {self.format_version}"
            )
        require_opaque_id(self.run_id, "a run id")
        if isinstance(self.attempt, bool) or self.attempt < 1:
            raise ValueError(f"attempts are numbered from one, got {self.attempt!r}")
        failure = self.record.failure
        if failure is not None and not self.trace.holds(failure.at):
            raise ValueError(
                f"the failure names {failure.at!r}, no operation or model call of the trace"
            )
        if self.record.system.kind is SystemKind.RULES_ONLY and self.trace.model_calls:
            raise ValueError("a rules-only export holds no model call")
