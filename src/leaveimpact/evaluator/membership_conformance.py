"""Membership conformance: whether a run's reads outside the frozen prefetch are the ones its
system's registered contract allows and obliges, read off the export and the sealed world.

Every system opens with the same prefetch, which ``prefetch_conformance`` holds it to. What
each system may read after it is the system's contract (the baselines step, note 18; the
outage step, fork 6 as amended by the external read): rules only reads nothing else; the agent
reads through its tools and issues no harness read; the single-shot baseline issues exactly
one harness search of the registered query at the registered limit, and the full-context
baseline exactly one harness enumeration of its level's documents, each between the prefetch
and the one model call, and neither makes a model-origin read. The one read is also named
among every dispatch's declared inputs: a read the harness fetched and the request did not
render is a request-composition fault that a comparison would read as the baseline's own
weakness (group 2's external read). The log refuses most of these at the append, since the
harness itself knows the policies; this is the evaluator saying so from the trace, for every
export that decodes, a failed attempt as much as a completed one.
Every finding is a harness finding: the one-call systems' model is shown no read tool, so it
cannot cause one, and nothing here is filled from sealed truth but the level's membership.

When the one read is obliged is derived from the recorded history, never from the assigned
condition or the report, and without the harness's own preconditions, which live where the
evaluator may not import. Three statements:

- *At most one, always.* A second harness read under the policy, one under another policy, or
  any harness read by a system that issues none is a finding whatever the ending.
- *Exactly one when the trace holds a dispatch.* The preparation precedes the model call, so a
  one-call run that dispatched shows its read, positioned after the last prefetch read and
  before the first intent.
- *Zero or one when the trace holds no dispatch*, and zero when the opening read returned no
  leave of the id asked, the same condition the prefetch check ends the plan on. A run that
  ended before its call, by abstention, by a defect the record's failure names, by an
  abandonment or by an infrastructure failure between the read and the call, carries no count
  finding.

The known limit: the second abstention, the employee universe not covered, is derived by the
harness's preconditions and not here, so a harness read issued after it shows as a count of one
with no dispatch and passes this check. The log's transition refuses that read at the append,
asking the same derivation the preparation node asks before it issues one
(``agent.log_transition``, the harness-read case; group 2's external read found the graph
alone holding it), so no export of a log the transition kept holds the history.

What the read contains is compared in one canonical form through the code the harness renders
with (the step-6 lesson on a planned value against a recorded one): the single-shot's query is
rendered by ``core.query_protocol.render_query`` over the prefetch-origin records in trace
order and the leave the opening read returned, and compared with the operation's arguments by
the key-order-free form the prefetch check uses. The registered protocol and limit are inputs,
since the record carries neither (step 12's fork 12); without them the query comparison is not
evaluated and every other check still runs. Full context's enumeration takes no argument, and
when it returned records the document references returned are compared with the level's
sealed membership as sorted duplicate-free sets: a member not returned and a reference returned
twice are findings here, a reference outside the level the level check's. A read that returned
nothing, unreachable under the corpus's outage, leaves the membership comparison not applicable.
Positions are the attempt's event order; an operation built outside a trace has none, and the
order check is then not made.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import EntityKind
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.query_protocol import QueryProtocol, render_query
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import HARNESS_READ_POLICIES, SystemKind
from leaveimpact.core.run_trace import (
    HarnessOrigin,
    ModelOrigin,
    Operation,
    OperationId,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    records_of,
)
from leaveimpact.evaluator.prefetch_conformance import asked, opening_leave, thawed_arguments
from leaveimpact.evaluator.sealed_world import SealedWorld


class MembershipFindingKind(StrEnum):
    """How a run's reads outside the prefetch differ from its system's contract; a member is
    the wire format."""

    MODEL_READ = "model_read"
    """A model-origin operation by a system whose model is shown no read tool."""
    FOREIGN_HARNESS_READ = "foreign_harness_read"
    """A harness read under a policy the system does not issue, or by a system that issues none."""
    SECOND_HARNESS_READ = "second_harness_read"
    """A further read under a policy that issues one."""
    MISSING_HARNESS_READ = "missing_harness_read"
    """The trace holds a dispatch and no read under the system's policy."""
    READ_AFTER_ABSENT_LEAVE = "read_after_absent_leave"
    """A harness read though the opening read returned no leave of the id asked."""
    OUT_OF_ORDER = "out_of_order"
    """The harness read is positioned before a prefetch read or after the first intent."""
    READ_NOT_SHOWN = "read_not_shown"
    """A dispatch's declared inputs do not name the harness read: fetched and not rendered.
    Named once for the run, since the dispatches of the one call restate one request."""
    WRONG_TOOL = "wrong_tool"
    """The harness read is not the policy's tool."""
    WRONG_ARGUMENTS = "wrong_arguments"
    """The harness read's arguments are not the registered query and limit, or not empty."""
    MEMBERSHIP_MISSING = "membership_missing"
    """A document of the level the enumeration did not return."""
    MEMBERSHIP_DUPLICATE = "membership_duplicate"
    """A document the enumeration returned more than once."""


class Comparison(StrEnum):
    """Whether a comparison this check can make was made for a run; a member is the wire
    format."""

    NOT_APPLICABLE = "not_applicable"
    NOT_EVALUATED = "not_evaluated"
    EVALUATED = "evaluated"


@dataclass(frozen=True, slots=True)
class MembershipFinding:
    """One discrepancy between a run's reads outside the prefetch and its system's contract.

    ``operation`` is absent for a missing read, which has none; ``document`` is set for the
    two membership kinds alone, the document the finding is about.
    """

    kind: MembershipFindingKind
    operation: OperationId | None
    document: EntityRef | None = None

    def __post_init__(self) -> None:
        if (self.operation is None) != (self.kind is MembershipFindingKind.MISSING_HARNESS_READ):
            raise ValueError("every finding names its operation, and only a missing read has none")
        membership = self.kind in (
            MembershipFindingKind.MEMBERSHIP_MISSING,
            MembershipFindingKind.MEMBERSHIP_DUPLICATE,
        )
        if (self.document is None) == membership:
            raise ValueError("a membership finding names its document, and no other does")


@dataclass(frozen=True, slots=True)
class MembershipConformance:
    """What one export shows of its reads outside the prefetch.

    ``query`` says whether the single-shot's query was compared with the registered protocol
    (not applicable to another system, not evaluated without the protocol and the limit);
    ``membership`` whether full context's enumeration was compared with the level's sealed
    membership (not applicable to another system or to a read that returned nothing, not
    evaluated for a level the world seals no membership for). ``findings`` are in the order
    the checks are made: the model reads and the foreign and further harness reads in the
    trace's order, then the one read's count, place, showing, tool, arguments and membership.
    """

    query: Comparison
    membership: Comparison
    findings: tuple[MembershipFinding, ...]


def membership_conformance(
    world: SealedWorld,
    export: RunExport,
    *,
    query_protocol: QueryProtocol | None = None,
    search_limit: int | None = None,
) -> MembershipConformance:
    """Whether the reads ``export`` records outside the prefetch are the ones its system's
    contract allows and obliges; ``query_protocol`` and ``search_limit`` are the registered
    single-shot values when the run was made under the registration at hand.

    Raises nothing for what the run did.
    """
    kind = export.record.system.kind
    operations = export.trace.operations
    policies = HARNESS_READ_POLICIES[kind]
    findings: list[MembershipFinding] = []
    if kind is not SystemKind.AGENT:
        findings.extend(
            MembershipFinding(MembershipFindingKind.MODEL_READ, operation.id)
            for operation in operations
            if isinstance(operation.origin, ModelOrigin)
        )
    harness_reads = [op for op in operations if isinstance(op.origin, HarnessOrigin)]
    own: list[Operation] = []
    for operation in harness_reads:
        assert isinstance(operation.origin, HarnessOrigin)
        if operation.origin.policy in policies:
            own.append(operation)
        else:
            findings.append(
                MembershipFinding(MembershipFindingKind.FOREIGN_HARNESS_READ, operation.id)
            )
    findings.extend(
        MembershipFinding(MembershipFindingKind.SECOND_HARNESS_READ, operation.id)
        for operation in own[1:]
    )
    query = Comparison.NOT_APPLICABLE
    membership = Comparison.NOT_APPLICABLE
    if not policies:
        return MembershipConformance(query, membership, tuple(findings))

    prefetched = [op for op in operations if isinstance(op.origin, PrefetchOrigin)]
    leave = opening_leave(export.context, prefetched)
    dispatched = any(call.dispatches for call in export.trace.model_calls)
    if dispatched and not own:
        findings.append(MembershipFinding(MembershipFindingKind.MISSING_HARNESS_READ, None))
    if not own:
        return MembershipConformance(query, membership, tuple(findings))

    read = own[0]
    if leave is None:
        findings.append(MembershipFinding(MembershipFindingKind.READ_AFTER_ABSENT_LEAVE, read.id))
    if _out_of_order(read, prefetched, export):
        findings.append(MembershipFinding(MembershipFindingKind.OUT_OF_ORDER, read.id))
    if any(read.id not in sent.input_reads for sent in export.trace.dispatches):
        findings.append(MembershipFinding(MembershipFindingKind.READ_NOT_SHOWN, read.id))
    expected_tool = "search" if kind is SystemKind.SINGLE_SHOT else "documents"
    if read.tool != expected_tool:
        findings.append(MembershipFinding(MembershipFindingKind.WRONG_TOOL, read.id))
        return MembershipConformance(query, membership, tuple(findings))

    if kind is SystemKind.SINGLE_SHOT:
        if query_protocol is None or search_limit is None or leave is None:
            query = Comparison.NOT_EVALUATED
        else:
            query = Comparison.EVALUATED
            returned = tuple(
                record for operation in prefetched for record in records_of(operation.outcome)
            )
            rendered = render_query(query_protocol, returned, leave)
            expected: JsonObject = {"query": rendered, "limit": search_limit}
            if asked(read.tool, thawed_arguments(read)) != asked(expected_tool, expected):
                findings.append(MembershipFinding(MembershipFindingKind.WRONG_ARGUMENTS, read.id))
        return MembershipConformance(query, membership, tuple(findings))

    if dict(read.arguments):
        findings.append(MembershipFinding(MembershipFindingKind.WRONG_ARGUMENTS, read.id))
    if not isinstance(read.outcome, RecordOutcome | RecordsOutcome):
        return MembershipConformance(query, membership, tuple(findings))
    members = world.level_documents(export.record.corpus_level)
    if members is None:
        return MembershipConformance(query, Comparison.NOT_EVALUATED, tuple(findings))
    membership = Comparison.EVALUATED
    returned_refs = Counter(
        record.ref for record in records_of(read.outcome) if record.ref.kind is EntityKind.DOCUMENT
    )
    findings.extend(
        MembershipFinding(MembershipFindingKind.MEMBERSHIP_DUPLICATE, read.id, ref)
        for ref, times in sorted(returned_refs.items(), key=lambda item: item[0].id)
        if times > 1
    )
    findings.extend(
        MembershipFinding(MembershipFindingKind.MEMBERSHIP_MISSING, read.id, ref)
        for ref in sorted(members - returned_refs.keys(), key=lambda ref: ref.id)
    )
    return MembershipConformance(query, membership, tuple(findings))


def _out_of_order(read: Operation, prefetched: list[Operation], export: RunExport) -> bool:
    """Whether ``read`` sits before a prefetch read or after the first intent, by the
    attempt's event positions; never, when the read carries no position."""
    if read.position is None:
        return False
    after_a_prefetch_read = any(
        op.position is not None and op.position > read.position for op in prefetched
    )
    intents = [
        dispatch.intent_position
        for call in export.trace.model_calls
        for dispatch in call.dispatches
    ]
    before_the_first_intent = bool(intents) and min(intents) < read.position
    return after_a_prefetch_read or before_the_first_intent


__all__ = [
    "Comparison",
    "MembershipConformance",
    "MembershipFinding",
    "MembershipFindingKind",
    "membership_conformance",
]
