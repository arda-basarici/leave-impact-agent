"""The count check: every bound a dispatch rested on held to the counting operation it names,
every counting operation to its own outcome, and every group of counting requests to the
rule they were retried under.

A dispatch is authorized on an upper bound of its input tokens, and the one registered
method establishes it by asking the provider to count the request before it is sent
(``core.input_bound``; the event log step's ruling on counting). The export states the bound
beside the dispatch and holds every counting operation the attempt made, the failed ones
included, each with the request digest it covers, the identifier it was asked of, its
outcome and the worker's reading of it. The export's constructor enforces identity and
reference alone: a dispatch's count is one the trace holds. Everything the bound claims
about that count is checked here, since a harness that got it wrong should leave an export
with a finding and not none.

Per dispatch, against the counting operation its bound names: the count did not count; its
outcome was logged after the dispatch's intent, so the bound was committed before its
evidence existed; the count or the bound covers another request than the one dispatched;
the bound is not the number the count returned; the bound's method or identifier is not the
count's. Per counting operation: the worker's reading is not what the method's
specification gives its outcome (``read_outcome``), the comparison that makes a denial
misread as transient leave a trace; and the method is not the caps'. Per group of counting
operations under one reuse key, the request digest with the identifier and the method:
replayed in order with ``count_decision`` over the readings before each, an operation made
when the decision was not to count again is a finding carrying that decision, a count after
a durable count, after a refusal or after an unclassified failure, or at the maximum. An
attempt that failed at the input bound names the last counting operation for that request:
a site that is not its group's last, and an attempt ended while the group's decision was
still to count, are findings about the ending. And the converse, since a refusal ends the
attempt by defect, an unclassified failure ends it at once and an exhausted maximum ends
it by infrastructure: a group that stopped is the recorded failure, named at its last
operation, and nothing is logged after it, no dispatch intent, no other count's start, no
entry into finalization. A group that stopped and is not the failure, and work after a
stopping count, are each a finding carrying the decision the group stopped with.

The replay and the ending read every outcome again through the method's specification;
the worker's stored reading is compared with that re-reading and plays no other part, so a
denial the worker misread as transient is reported as a misreading and still counts as the
refusal it is. The same holds in the eligibility check, which projects an ending at the
input bound from the re-read outcomes.

Two parts need the registration and are marked by ``registration_evaluated``, as the
attribution check marks its bound: the group replay, whose maximum is the re-dispatch
policy's, which a registration applies to counting by reference; and the identifier,
checked for a count a dispatch references against the registered counting identifier of
that dispatch's role, and for a count nothing references, a failed one or one for a request
never dispatched, against the set of every role's identifier, the weaker check of the two
since a counting operation names no role.

Evaluated for every export; a rules-only export reads zero operations and zero dispatches
and carries no finding. Raises nothing for what a record states.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.attribution import RedispatchPolicy
from leaveimpact.core.counting_operations import Counted, CountingOperation, read_outcome
from leaveimpact.core.input_bound import (
    CountDecision,
    CountResult,
    RegisteredInputBound,
    count_decision,
)
from leaveimpact.core.run_ending import InputBoundSite
from leaveimpact.core.run_export import RunExport, RunTrace
from leaveimpact.core.run_trace import CountingOperationId, ModelCallId

type ReuseKey = tuple[str, str, RegisteredInputBound]
"""What a durable count is reused under: the request digest, the counting identifier and the
method."""


class CountFindingKind(StrEnum):
    """What the check can find; a member is the wire format. The order is append-only."""

    COUNT_DID_NOT_COUNT = "count_did_not_count"
    COUNT_AFTER_INTENT = "count_after_intent"
    COUNT_COVERS_ANOTHER_REQUEST = "count_covers_another_request"
    BOUND_NOT_THE_COUNT = "bound_not_the_count"
    BOUND_METHOD_DIFFERS = "bound_method_differs"
    BOUND_IDENTIFIER_DIFFERS = "bound_identifier_differs"
    READING_NOT_THE_OUTCOMES = "reading_not_the_outcomes"
    METHOD_NOT_THE_CAPS = "method_not_the_caps"
    COUNT_NOT_PERMITTED = "count_not_permitted"
    SITE_NOT_THE_LAST_COUNT = "site_not_the_last_count"
    ENDED_WHILE_COUNT_PERMITTED = "ended_while_count_permitted"
    IDENTIFIER_NOT_REGISTERED = "identifier_not_registered"
    STOPPING_COUNT_NOT_THE_FAILURE = "stopping_count_not_the_failure"
    WORK_AFTER_A_STOPPING_COUNT = "work_after_a_stopping_count"


@dataclass(frozen=True, slots=True)
class CountFinding:
    """One finding, by kind and where: the call and dispatch whose bound it is about, when it
    is about a bound; the counting operation, when it is about one. ``decision`` is held
    for a count made when the decision was not to count."""

    kind: CountFindingKind
    model_call: ModelCallId | None = None
    dispatch: int | None = None
    counting_operation: CountingOperationId | None = None
    decision: CountDecision | None = None


@dataclass(frozen=True, slots=True)
class CountCheck:
    """How many counting operations and dispatches were read, whether the two registration
    parts were evaluated, and the findings: the dispatches' first in the trace's order, then
    the operations', then the groups', then the ending's."""

    operations: int
    dispatches: int
    registration_evaluated: bool
    findings: tuple[CountFinding, ...]


def reuse_key(count: CountingOperation) -> ReuseKey:
    """The key ``count``'s result is reused under."""
    return (count.request_digest, count.counting_identifier, count.method)


def check_counts(
    export: RunExport,
    policy: RedispatchPolicy | None,
    counting_identifiers: Mapping[str, str] | None,
) -> CountCheck:
    """The counting operations and bounds of the run ``export`` records, held to each other
    and, when ``policy`` and ``counting_identifiers`` (by role) are both given, to the
    registration. Raises nothing for what the record states."""
    kinds = CountFindingKind
    record, trace = export.record, export.trace
    registered = policy is not None and counting_identifiers is not None
    findings: list[CountFinding] = []

    referenced: set[CountingOperationId] = set()
    for call in trace.model_calls:
        for dispatch in call.dispatches:
            bound = dispatch.bound
            count = trace.counting_operation(bound.evidence)
            if count is None:
                continue  # the constructor refuses this; held so the check is total
            referenced.add(count.id)
            at = (call.id, dispatch.number, count.id)
            if not isinstance(count.outcome, Counted):
                findings.append(CountFinding(kinds.COUNT_DID_NOT_COUNT, *at))
            elif count.outcome.input_tokens != bound.input_tokens:
                findings.append(CountFinding(kinds.BOUND_NOT_THE_COUNT, *at))
            if count.outcome_position is not None and (
                count.outcome_position > dispatch.intent_position
            ):
                findings.append(CountFinding(kinds.COUNT_AFTER_INTENT, *at))
            asked = dispatch.request.request_digest
            if count.request_digest != asked or bound.request_digest != asked:
                findings.append(CountFinding(kinds.COUNT_COVERS_ANOTHER_REQUEST, *at))
            if bound.method != count.method:
                findings.append(CountFinding(kinds.BOUND_METHOD_DIFFERS, *at))
            if bound.counting_identifier != count.counting_identifier:
                findings.append(CountFinding(kinds.BOUND_IDENTIFIER_DIFFERS, *at))
            if counting_identifiers is not None and (
                counting_identifiers.get(call.role) != count.counting_identifier
            ):
                findings.append(CountFinding(kinds.IDENTIFIER_NOT_REGISTERED, *at))

    known = None if counting_identifiers is None else set(counting_identifiers.values())
    for count in trace.counting_operations:
        if count.reading is not read_outcome(count.method, count.outcome):
            findings.append(
                CountFinding(kinds.READING_NOT_THE_OUTCOMES, counting_operation=count.id)
            )
        if count.method != record.caps.input_bound:
            findings.append(CountFinding(kinds.METHOD_NOT_THE_CAPS, counting_operation=count.id))
        if (
            known is not None
            and count.id not in referenced
            and (count.counting_identifier not in known)
        ):
            findings.append(
                CountFinding(kinds.IDENTIFIER_NOT_REGISTERED, counting_operation=count.id)
            )

    # The replay and the ending read every outcome again: a stored reading is the worker's
    # statement, compared above, and a misread denial must not authorize anything here.
    groups: dict[ReuseKey, list[CountingOperation]] = {}
    for count in trace.counting_operations:
        groups.setdefault(reuse_key(count), []).append(count)
    if policy is not None:
        for group in groups.values():
            readings = [read_outcome(count.method, count.outcome) for count in group]
            for index, count in enumerate(group):
                decision = count_decision(readings[:index], policy.max_dispatches)
                if decision is not CountDecision.COUNT:
                    findings.append(
                        CountFinding(
                            kinds.COUNT_NOT_PERMITTED,
                            counting_operation=count.id,
                            decision=decision,
                        )
                    )

    failure = record.failure
    named = (
        trace.counting_operation(failure.site.counting_operation)
        if failure is not None and isinstance(failure.site, InputBoundSite)
        else None
    )
    if named is not None:
        group = groups[reuse_key(named)]
        if group[-1].id != named.id:
            findings.append(
                CountFinding(kinds.SITE_NOT_THE_LAST_COUNT, counting_operation=named.id)
            )
        if policy is not None:
            decision = _decision_of(group, policy)
            if decision is CountDecision.COUNT:
                findings.append(
                    CountFinding(
                        kinds.ENDED_WHILE_COUNT_PERMITTED,
                        counting_operation=named.id,
                        decision=decision,
                    )
                )

    # The converse: a group that stopped the attempt is the recorded failure, and nothing
    # was logged after it.
    for group in groups.values():
        last = group[-1]
        decision = _stopping_decision(group, policy)
        if decision is None:
            continue
        if named is None or named.id != last.id:
            findings.append(
                CountFinding(
                    kinds.STOPPING_COUNT_NOT_THE_FAILURE,
                    counting_operation=last.id,
                    decision=decision,
                )
            )
        if _work_after(trace, last):
            findings.append(
                CountFinding(
                    kinds.WORK_AFTER_A_STOPPING_COUNT,
                    counting_operation=last.id,
                    decision=decision,
                )
            )

    return CountCheck(
        len(trace.counting_operations), len(trace.dispatches), registered, tuple(findings)
    )


def _decision_of(group: Sequence[CountingOperation], policy: RedispatchPolicy) -> CountDecision:
    """The decision after every operation of ``group``, each outcome read again."""
    readings = [read_outcome(count.method, count.outcome) for count in group]
    return count_decision(readings, policy.max_dispatches)


def _stopping_decision(
    group: Sequence[CountingOperation], policy: RedispatchPolicy | None
) -> CountDecision | None:
    """The decision ``group`` stopped the attempt with, or ``None`` for a group that did not:
    a refusal or an unclassified failure among its outcomes read again, which need no
    maximum, or the maximum exhausted under ``policy`` when one is given."""
    readings = [read_outcome(count.method, count.outcome) for count in group]
    if CountResult.REFUSED in readings:
        return CountDecision.DEFECT
    if CountResult.UNCLASSIFIED in readings:
        return CountDecision.UNCLASSIFIED
    if policy is None:
        return None
    decision = count_decision(readings, policy.max_dispatches)
    return decision if decision is CountDecision.EXHAUSTED else None


def _work_after(trace: RunTrace, count: CountingOperation) -> bool:
    """Whether the trace holds an event after ``count``'s last position: a dispatch intent,
    another counting operation's start, or the entry into finalization."""
    after = count.positions[-1]
    if any(dispatch.intent_position > after for dispatch in trace.dispatches):
        return True
    if any(other.start_position > after for other in trace.counting_operations):
        return True
    return trace.finalization_entered is not None and trace.finalization_entered > after


__all__ = [
    "CountCheck",
    "CountFinding",
    "CountFindingKind",
    "ReuseKey",
    "check_counts",
    "reuse_key",
]
