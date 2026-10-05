"""The attribution check: each dispatch's recorded reading held to the registered table, and
each logical call to the bound it may be dispatched under.

A dispatch records what arrived and, apart from it, how the measurement reads it: a kind
and the identifier of the rule that decided (the contract step's ruling on dispatches). The
rule is a row of the registered attribution table, and reading an observation is one
function of ``core``'s (``attribute``), so the evaluator reads every observation again and
compares. Which failures count against a system was fixed before any result existed; this
is where a record is held to that.

*What the export cannot give back.* A defect is read only with a cause, something the
harness established about its own request, and a dispatch records the rule and not the
cause it supplied. So an observation is read again under no cause and under each cause of
the closed list, and the recorded rule must be one of the rules that gives. A record that
names a defect row is thereby held to the row's match and taken at its word for the cause:
where and why is the failure the export records at that dispatch. The reverse, a harness
that had established a cause and named the row for none, leaves no trace in an export and
is not found here.

Two findings about the reading:

- *The rule is not the table's.* The recorded rule is none the table gives this
  observation: a row that does not exist, one whose match does not take it, or one an
  earlier row takes it before.
- *The reading is not the rule's.* The rule is one the table gives, and the kind recorded
  beside it is not that row's reading.

And two about what followed, since no layer beneath a dispatch retries and a second send is
a new dispatch the table has to allow:

- *Dispatched again against its row.* A dispatch that was followed by another was read
  by a row that does not allow one. The row is the table's for the observation and not
  whatever the record names: the recorded rule where it is one the table gives, and
  otherwise the row the table gives under no cause, so a misnamed rule neither hides a
  re-dispatch the table forbids nor invents one it allows. A dispatch with no recorded
  outcome is read by no row and may always be followed: nothing shows it was sent. Its
rule is the one name the dispatch type admits for it, so no finding is made of it here.
- *More dispatches than the bound.* A logical call holds more dispatches than the
  registered re-dispatch policy's maximum. Evaluated when the policy is set
  (``bound_evaluated``); the policy and the table are two values of the registration and
  either may still be pending.

The whole check is evaluated only for a run whose record names the digest of the table
given, a rules-only record naming none. A run made under another table is out of the
tables for its settings and is held to no rows here. The record does not name the
re-dispatch policy at all, so the caller gives a table and a policy only for a run made
under the registration they are from.

The findings are the harness's: a model cannot make a record disagree with the table.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.attribution import (
    AttributionRow,
    AttributionTable,
    Cause,
    RedispatchPolicy,
    attribute,
)
from leaveimpact.core.model_calls import Dispatch, ModelCall, NoRecordedOutcome
from leaveimpact.core.run_trace import ModelCallId


class AttributionFindingKind(StrEnum):
    """How a record can differ from the registered table; a member is the wire format."""

    RULE_NOT_THE_TABLES = "rule_not_the_tables"
    READING_NOT_THE_RULES = "reading_not_the_rules"
    REDISPATCHED_AGAINST_ITS_ROW = "redispatched_against_its_row"
    MORE_DISPATCHES_THAN_THE_BOUND = "more_dispatches_than_the_bound"


@dataclass(frozen=True, slots=True)
class AttributionFinding:
    """One difference, by kind and where: the call and the dispatch's number, or the call
    alone for one that holds more dispatches than the bound."""

    kind: AttributionFindingKind
    model_call: ModelCallId
    dispatch: int | None = None


@dataclass(frozen=True, slots=True)
class AttributionCheck:
    """What reading the dispatches again found: how many were read, whether the calls were
    held to a re-dispatch bound, and every difference in the trace's order, a call's
    dispatches first and its bound last."""

    dispatches: int
    bound_evaluated: bool
    findings: tuple[AttributionFinding, ...]


def check_attributions(
    table: AttributionTable, policy: RedispatchPolicy | None, calls: Sequence[ModelCall]
) -> AttributionCheck:
    """The dispatches of ``calls`` read again by ``table``, and each call held to ``policy``
    when one is given. Raises nothing for what the record states."""
    kinds = AttributionFindingKind
    findings: list[AttributionFinding] = []
    read = 0
    for call in calls:
        for dispatch in call.dispatches:
            read += 1
            found, row = _read_again(table, dispatch)
            if found is not None:
                findings.append(AttributionFinding(found, call.id, dispatch.number))
            followed = dispatch.number != call.dispatches[-1].number
            if followed and row is not None and not row.redispatch:
                findings.append(
                    AttributionFinding(kinds.REDISPATCHED_AGAINST_ITS_ROW, call.id, dispatch.number)
                )
        if policy is not None and len(call.dispatches) > policy.max_dispatches:
            findings.append(AttributionFinding(kinds.MORE_DISPATCHES_THAN_THE_BOUND, call.id))
    return AttributionCheck(read, policy is not None, tuple(findings))


def _read_again(
    table: AttributionTable, dispatch: Dispatch
) -> tuple[AttributionFindingKind | None, AttributionRow | None]:
    """How the recorded attribution of ``dispatch`` differs from every reading ``table``
    gives its observation, under no cause and under each cause a harness can supply, and
    the row that read it: the one the record names where the table gives it, the one the
    table gives under no cause otherwise, ``None`` for no recorded outcome."""
    recorded = dispatch.attribution
    given = [attribute(table, dispatch.observation, cause) for cause in (None, *Cause)]
    row = next((row for reading, row in given if reading.rule == recorded.rule), given[0][1])
    if isinstance(dispatch.observation, NoRecordedOutcome):
        row = None
    if recorded in [reading for reading, _ in given]:
        return None, row
    if recorded.rule in {reading.rule for reading, _ in given}:
        return AttributionFindingKind.READING_NOT_THE_RULES, row
    return AttributionFindingKind.RULE_NOT_THE_TABLES, row


__all__ = [
    "AttributionCheck",
    "AttributionFinding",
    "AttributionFindingKind",
    "check_attributions",
]
