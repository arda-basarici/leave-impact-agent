"""The ending check: what a record states about how its attempt ran and ended, held to what
the export itself holds.

Export format 2 lets a record say three things about its own ending that nothing recomputed
(the contract step's ruling on time and approval): the segments the attempt ran in, each
with its harness revision; the two instants its elapsed time runs between; and the digest of
the review payload its approval was asked over. Each is the harness's own statement, and
each can be read against something else in the same export, which is what this does. It is
the cost check's kind of thing: nothing raises, nothing is corrected, and a difference is a
finding about the harness, never about the system it ran.

- *The timing as a table needs it.* How many segments, and whether every one's end was
  recorded. A killed segment's tail is unknown, so the evidenced active time of a run whose
  timing is incomplete is a lower bound, and a latency table marks it with the number of
  segments beside it, so an interrupted run never reads as an unusually fast one.
- *Active time above elapsed.* Execution the log can show cannot outlast the wall clock
  from admission to the terminal event. The record admits it all the same, since a wall
  clock can step; it is reported here and not refused there. The two are different
  clocks compared in whole milliseconds, the elapsed time rounded down, so a run that
  never waited and whose two clocks disagree by less than a millisecond can carry the
  finding. No tolerance is applied, none having a value that could be defended before a
  harness has stamped a run with real clocks; how often it fires on such runs is read off
  the first of them.
- *Commits differ.* A run a report may use ran every segment on one commit. An attempt
  recovered by a process on another commit is one export of two programs. Whether such a
  run leaves the tables is the artifact's to say, under a bound registration; the finding
  is made for every run, with the commits, and the analysis reports each such attempt
  as a provenance incident whatever became of the run (``incidents``).
- *The approval's digest.* An approval that was requested holds the digest of its frozen
  review payload: the claims, who composed them under which policy, and the diagnostics
  the composition left. An export is terminal-only and holds all of it, so the digest is
  computed again by the function the harness computed it with (``core``'s
  ``review_payload_digest``) and compared. A difference says the claims exported are not
  the ones the approval was asked over.

Needs the export alone. Two neighbours are not here: whether a tree was dirty is read where
eligibility is decided, and the reservation and the token cap are audited with the ledger
that defines what an allocation retains and which tokens a counting rule counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.core.run_timing import Timing, elapsed_ms, evidenced_active_ms, timing_complete


class EndingFinding(StrEnum):
    """What a record's ending can state that its export does not bear out; a member is the
    wire format. The order is append-only: a finding added later sits after every earlier
    one, so an older artifact's findings read under the same order."""

    ACTIVE_EXCEEDS_ELAPSED = "active_exceeds_elapsed"
    COMMITS_DIFFER = "commits_differ"
    APPROVAL_DIGEST_DIFFERS = "approval_digest_differs"
    TERMINAL_BEFORE_ADMISSION = "terminal_before_admission"
    """The log's clock read an earlier instant at the terminal event than at the admission;
    no elapsed duration is stated and the comparison with active time is not made."""
    ABANDONMENT_GENERATION_DIFFERS = "abandonment_generation_differs"
    """The abandon command fenced another generation than the number of segments the record
    holds, though a claim is the only thing that raises either."""


@dataclass(frozen=True, slots=True)
class EndingCheck:
    """An attempt's segments and elapsed time as its record gives them, and where the export
    does not bear the record's ending out.

    ``timing_complete`` is false when a segment's end was never recorded, and the run's
    evidenced active time (the cost check's ``duration_ms``) is then a lower bound.
    ``elapsed_ms`` is ``None`` when the terminal instant is before the admission, which the
    findings then say. ``commits`` are the harness commits the segments ran on, each once,
    in the order the segments first ran on them. ``findings`` are in the declared order of
    the kinds.
    """

    segments: int
    timing_complete: bool
    elapsed_ms: int | None
    commits: tuple[str, ...]
    findings: tuple[EndingFinding, ...]


def commits_of(timing: Timing) -> tuple[str, ...]:
    """The harness commits the segments of ``timing`` ran on, each once, in segment order."""
    return tuple(dict.fromkeys(segment.harness.commit for segment in timing.segments))


def commits_differ(timing: Timing) -> bool:
    """Whether the segments of ``timing`` ran on more than one harness commit."""
    return len(commits_of(timing)) > 1


def check_ending(export: RunExport) -> EndingCheck:
    """The ending the record of ``export`` states, held to the export. Raises nothing for
    what the record states."""
    record, trace = export.record, export.trace
    timing = record.timing
    elapsed = elapsed_ms(timing)
    recorded = record.approval.payload_digest
    abandonment = record.abandonment
    found = {
        EndingFinding.ACTIVE_EXCEEDS_ELAPSED: (
            elapsed is not None and evidenced_active_ms(timing) > elapsed
        ),
        EndingFinding.COMMITS_DIFFER: commits_differ(timing),
        EndingFinding.APPROVAL_DIGEST_DIFFERS: (
            recorded is not None
            and recorded != review_payload_digest(trace.claims, trace.composition)
        ),
        EndingFinding.TERMINAL_BEFORE_ADMISSION: elapsed is None,
        EndingFinding.ABANDONMENT_GENERATION_DIFFERS: (
            abandonment is not None and abandonment.ownership_generation != len(timing.segments)
        ),
    }
    return EndingCheck(
        len(timing.segments),
        timing_complete(timing),
        elapsed,
        commits_of(timing),
        tuple(kind for kind, holds in found.items() if holds),
    )


__all__ = ["EndingCheck", "EndingFinding", "check_ending", "commits_differ", "commits_of"]
