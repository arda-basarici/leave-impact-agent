"""What the replay's records add up to: which claims are grounded end to end, under which
reading, and where the failures start.

The replay stores, per claim, a local standing and the premises it consumed. Everything a
table needs beyond that is derived here and stored nowhere, so the three numbers a report
of grounding shows cannot disagree with the records or with one another (the investigator
milestone's fourth build step, ruling 3: premise accounting):

- *Local failures*: the claims whose own replay did not reproduce them, or that lack a
  premise. These are the roots. A wrong constraint under twelve assessments is one root.
- *Grounded end to end*: locally reproduced, no premise missing, and every premise
  grounded end to end. The same wrong constraint leaves thirteen claims ungrounded.
- *Strictly grounded*: grounded end to end with no source left unclosed anywhere in what
  the claim rests on. The operational reading lets a negative stand when the only part
  unobserved is prose no read can enumerate; the strict one does not, and is derived from
  the proofs the operational replay already carries, so there is one replay and not two
  (ruling 2: one judgment stored, the strict reading derived). The word grounded, alone,
  is never used for a result with an unclosed source.

The premise graph is acyclic by the claim set's own structure check, and a premise is
always a claim of the same report, so the walk terminates.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from leaveimpact.core.closure import Consulted
from leaveimpact.core.coverage import Slice
from leaveimpact.core.ids import ClaimId
from leaveimpact.evaluator.replay import ClaimGrounding, Standing


def local_failures(records: Sequence[ClaimGrounding]) -> frozenset[ClaimId]:
    """The claims that fail on their own: not reproduced, or a premise the report lacks."""
    return frozenset(
        record.claim_id
        for record in records
        if record.standing is not Standing.REPRODUCED or record.missing_premises
    )


def grounded_end_to_end(records: Sequence[ClaimGrounding]) -> frozenset[ClaimId]:
    """The claims reproduced with every premise, transitively, reproduced: the operational
    reading, which lets a waived unclosed source stand."""
    return _resting_on(records, local_failures(records))


def strictly_grounded(records: Sequence[ClaimGrounding]) -> frozenset[ClaimId]:
    """The claims grounded end to end on proofs that leave no source unclosed, their
    premises' proofs included."""
    failing = local_failures(records) | {
        record.claim_id for record in records if unclosed_slices(record)
    }
    return _resting_on(records, failing)


def unclosed_slices(record: ClaimGrounding) -> tuple[Slice, ...]:
    """The slices the claim's own conclusion stood without: no read observes them whole, and
    the answer was reached all the same. An unclosable slice in an answer something else
    stopped is not one; that answer does not rest on it."""
    return tuple(
        witness.where
        for witness in record.proof
        if isinstance(witness, Consulted) and witness.waived
    )


def _resting_on(
    records: Sequence[ClaimGrounding], failing: frozenset[ClaimId] | set[ClaimId]
) -> frozenset[ClaimId]:
    """The claims that neither fail nor rest, through any chain of premises, on one that does."""
    by_id: Mapping[ClaimId, ClaimGrounding] = {record.claim_id: record for record in records}
    settled: dict[ClaimId, bool] = {}

    def holds(claim_id: ClaimId) -> bool:
        if claim_id not in settled:
            record = by_id.get(claim_id)
            # A premise outside the records cannot happen for a replayed set; read as failing.
            settled[claim_id] = (
                record is not None
                and claim_id not in failing
                and all(holds(premise) for premise in record.premises)
            )
        return settled[claim_id]

    return frozenset(record.claim_id for record in records if holds(record.claim_id))


__all__ = [
    "grounded_end_to_end",
    "local_failures",
    "strictly_grounded",
    "unclosed_slices",
]
