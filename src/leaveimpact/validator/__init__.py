"""Read-only verification that projection realized the declared world.

Re-reads the live systems through the adapters built from the projected manifest and
proves, in three layered checks, that they realize the sealed world spec: every closed
enumeration the investigator can see holds exactly the planted identities, missing and
foreign both refused; every record read back equals its planting; and the facts a run
could observe at the two ends of each scenario's stable interval, derived from reads
made the way the investigator reads, equal the facts the plantings yield. It validates
the projected systems rather than the generator's intermediate objects on purpose: the
projection seam is under test too, and a shared generation bug cannot yield an
evaluation that agrees with a wrong world. It reads the world spec, the scenario specs,
the world manifest and the live systems, and never the truth manifest; what truth expects
of the plantings was proven before sealing by the whole-world re-verification in
``world``, so the two proofs compose: live systems realize the sealed spec, and the
sealed spec implies the sealed truth, without the validator ever seeing a key.

That chain is complete for the structured tier. The pre-seal verification runs over the
truth base, which includes the facts only prose can carry; the view check here covers
derived facts alone, so for the prose-carried facts of later tiers the proof runs
through the materializer's containment gates and the corpus adapter's read fidelity, not
through this validator. Its verdict is its own artifact and never touches the manifest:
``projected`` there means the projection lifecycle completed, approval is the validator's
separate word, and serving requires both.

Boundary: its own package so that read-only is enforceable by the import law — inside
``generator`` nothing could stop a validator module from importing a projector. Imports
``world``, ``adapters`` and ``core``; never ``generator``.
"""

from leaveimpact.validator import checks
from leaveimpact.validator.checks import (
    CheckStatus,
    IdentityExactness,
    RecordMismatch,
    ViewDisagreement,
    boundary_instants,
    compare_identities,
    compare_records,
    compare_views,
    derive_stamped,
    events_overlapping,
    leaves_overlapping,
    observable_dates,
    view_at,
    window_instants,
    world_horizon,
)

__all__ = [
    "checks",
    "CheckStatus",
    "IdentityExactness",
    "RecordMismatch",
    "ViewDisagreement",
    "boundary_instants",
    "compare_identities",
    "compare_records",
    "compare_views",
    "derive_stamped",
    "events_overlapping",
    "leaves_overlapping",
    "observable_dates",
    "view_at",
    "window_instants",
    "world_horizon",
]
