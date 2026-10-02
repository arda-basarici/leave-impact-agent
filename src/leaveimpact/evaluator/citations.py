"""Citation quality: for each evidence reference a claim carries, whether it names something the
sealed world holds, whether the run read it, and whether the claim's proof rests on it.

Three axes, stored as they are and never folded into one status (the investigator
milestone's fourth build step, ruling 4). They are independent. A record the sealed world
does not hold still derives facts when a read returns it, so a citation can fail to
resolve and be retrieved and used; a citation can resolve and never have been read.

- *Resolves*: the sealed world holds the cited record, comment or section, by its kind and
  id. Checked against the sealed index and not against what was returned, which would
  make it the next axis. A citation that does not resolve is said to not resolve, and no
  more: a returned record the world does not hold points at contamination or a harness
  defect, not at invention.
- *Retrieved*: a completed read returned the cited record, or a ticket or a document that
  holds the cited comment or section. Identity only: a part that came back altered was
  still retrieved, and the content gate has already kept its sealed fact out of the view.
- *Used*: the cited target is a citable witness of the proof the claim was reproduced by,
  or the record a witnessing comment or section is read inside. The reverse does not
  hold: a cited comment supports no structured fact of its ticket. A claim's witnesses
  are its own proof's and those of the premises its replay consumed, transitively, one
  rule for every claim type; an action is the case with none of its own that a citation
  can name, an assignment having no witness and a conclusion about everyone only the
  enumeration of the candidates. Only a
  reproduced premise lends its witnesses, and the walk stops at one that is not: a
  contradicted assessment's proof is what the rules hold against it, and an action that
  rests on it is not supported by that evidence. Evaluated only when the citation was
  retrieved and the claim is reproduced, so "retrieved and unused" stays apart from "use
  not evaluated".

A citable witness is something a citation can name: the record a fact or a gap was read
from, and a record whose return settled a negative. An enumeration or a window that closed
a negative, and a source left unclosed, name no record. So a negative settled only by an
enumeration has nothing to cite, and the limit runs the other way for a conclusion about
everyone, which rests on every candidate's assessment: nearly any record read counts as
used there.

One record per evidence reference as the claim carries it, the field included and not
judged: a field metric needs a relation over a fact's fields (an event's schedule comes
from its start and its end together), which this milestone does not define, and the raw
reference is kept so that table can be cut later without grading again. A claim that cites
nothing has no record here. That is neither perfect nor zero, and the tables say how many
claims cite at all beside the quality of the citations made.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from leaveimpact.core.claims import Claim
from leaveimpact.core.closure import Consulted, Witness
from leaveimpact.core.coverage import RecordSlice, SliceStatus
from leaveimpact.core.ids import ClaimId
from leaveimpact.core.refs import EntityRef, EvidenceRef
from leaveimpact.evaluator.observed_view import ObservedRun
from leaveimpact.evaluator.replay import ClaimGrounding, Standing
from leaveimpact.evaluator.world_index import WorldIndex


@dataclass(frozen=True, slots=True)
class CitationRecord:
    """One evidence reference of one claim on the three axes. ``used`` is ``None`` when it was
    not evaluated: the citation was not retrieved, or the claim was not reproduced."""

    claim_id: ClaimId
    evidence: EvidenceRef
    resolves: bool
    retrieved: bool
    used: bool | None

    def __post_init__(self) -> None:
        if self.used is not None and not self.retrieved:
            raise ValueError(f"{self.claim_id}: use is judged only of a citation that was read")


def judge_citations(
    claims: Sequence[Claim],
    groundings: Sequence[ClaimGrounding],
    observed: ObservedRun,
    index: WorldIndex,
) -> tuple[CitationRecord, ...]:
    """Every evidence reference of ``claims`` on the three axes, in claim order and, within a
    claim, in the order the claim holds them. ``groundings`` are the replay's records of the
    same claims."""
    by_id = {record.claim_id: record for record in groundings}
    returned = observed.coverage.returned
    records: list[CitationRecord] = []
    for claim in claims:
        grounding = by_id[claim.claim_id]
        reproduced = grounding.standing is Standing.REPRODUCED
        witnesses = (
            cited_witnesses(grounding, by_id, index) if reproduced else frozenset[EntityRef]()
        )
        for evidence in claim.evidence_refs:
            target = evidence.target
            retrieved = target in returned
            records.append(
                CitationRecord(
                    claim_id=claim.claim_id,
                    evidence=evidence,
                    resolves=target in index.records or target in index.parts,
                    retrieved=retrieved,
                    used=target in witnesses if retrieved and reproduced else None,
                )
            )
    return tuple(records)


def cited_witnesses(
    grounding: ClaimGrounding, by_id: Mapping[ClaimId, ClaimGrounding], index: WorldIndex
) -> frozenset[EntityRef]:
    """What a citation of this claim may name and count as used: the citable witnesses of its
    proof and of every reproduced premise under it, and the record each witnessing part is
    read inside. Empty for a claim that was not reproduced: it has no proof to be cited by."""
    named: set[EntityRef] = set()
    seen: set[ClaimId] = set()
    pending = [grounding]
    while pending:
        record = pending.pop()
        if record.claim_id in seen or record.standing is not Standing.REPRODUCED:
            continue
        seen.add(record.claim_id)
        named.update(citable_witnesses(record))
        pending.extend(by_id[premise] for premise in record.premises if premise in by_id)
    parents = {index.parts[part].parent for part in named if part in index.parts}
    return frozenset(named | parents)


def citable_witnesses(grounding: ClaimGrounding) -> frozenset[EntityRef]:
    """The records the claim's own proof can be cited by: what each fact and each gap was read
    from, and each record whose return settled a negative."""
    return frozenset(target for witness in grounding.proof if (target := _citable(witness)))


def _citable(witness: Witness) -> EntityRef | None:
    if isinstance(witness, Consulted):
        covered = witness.status is SliceStatus.COVERED
        return witness.where.record if covered and isinstance(witness.where, RecordSlice) else None
    return witness.evidence.target


__all__ = ["CitationRecord", "citable_witnesses", "cited_witnesses", "judge_citations"]
