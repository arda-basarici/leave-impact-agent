"""Whether a run may be attempted again: one total function over the ways an attempt ends.

A run that is attempted twice is graded on the attempt the registration's rule counts, so
when a second attempt may exist at all decides what the measurement can be made to say.
The question was once answered in two places that were never reconciled, a column of the
attribution table and the registration's retry rule, and neither covered a failure that is
not at a model dispatch (the event log step's ruling on new attempts). It is answered here,
once, and asked by two callers: admission, of what the previous attempt's log holds, and
the evaluator, of a run's exported attempts in order.

The endings are a closed vocabulary, and every one has a rule:

- *completed*, or *reported at its cap*: no. That is the graded result.
- *a defect*, at any site: no. A retry could hide it. The same holds for an attempt whose
  log records a defect, whatever closed it afterwards.
- *infrastructure at a dispatch's send, read by a row of the attribution table*: that
  row's flag, whether or not the call's dispatches were exhausted.
- *the call's dispatches exhausted and the last one unresolved*: yes. No row read it, and
  nothing shows the request ever ran.
- *the input bound exhausted*: yes. The counting requests failed on causes classified as
  transient, and the request they were for was never sent. A counting failure nothing
  classifies is not this ending: it is an infrastructure ending no rule names.
- *abandoned, with no dispatch ever authorized*: yes. No model output existed, so there was
  no answer whose quality a decision to abandon could have been made on.
- *abandoned after a dispatch was authorized*: no. The evidence is the log's and not the
  reason an operator gives: an attempt that may have produced output is resumed, by a
  claim, and never replaced.
- *any other infrastructure ending*: no. A source that is down is a registered condition,
  a database that is down writes no ending at all and the attempt is recovered, and a
  failure of the harness's own composition is a defect.

A rule that grants is not yet a permission. The previous attempt must be closed and the
registered maximum not reached. The category needs no gate of its own: every ending a
rule grants is an infrastructure failure, and the registration's retry rule admits no
other category. A new attempt replaces the outputs of the calls the failed one had already
answered; that is the stated cost of every infrastructure retry, the reason the counted
attempt is the earliest that did not fail by infrastructure, and it is not argued away.

The result names the rule that decided, so an audit can say why an attempt was or was not
permitted and not only whether.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_trace import require_integer, require_opaque_id

# --- How an attempt ended ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Completed:
    """The system produced its final claims."""


@dataclass(frozen=True, slots=True)
class ReportedAtCap:
    """The run reported what it held at its cap."""


@dataclass(frozen=True, slots=True)
class EndedByDefect:
    """A defect of the harness ended the attempt, at whatever site."""


@dataclass(frozen=True, slots=True)
class SendFailure:
    """An infrastructure failure at a model dispatch's send, read by the row ``rule`` of the
    attribution table; ``row_permits`` is that row's flag for a new attempt."""

    rule: str
    row_permits: bool

    def __post_init__(self) -> None:
        require_opaque_id(self.rule, "an attribution rule")


@dataclass(frozen=True, slots=True)
class UnresolvedAtMaximum:
    """A call's dispatches were exhausted and its last has no recorded outcome."""


@dataclass(frozen=True, slots=True)
class InputBoundExhausted:
    """The counting requests for a model request were exhausted on transient failures,
    without a count."""


@dataclass(frozen=True, slots=True)
class Abandoned:
    """An outside decision closed the attempt; ``dispatch_intents`` is how many dispatches
    its log had authorized by then."""

    dispatch_intents: int

    def __post_init__(self) -> None:
        require_integer(self.dispatch_intents, "the dispatch intents logged")


@dataclass(frozen=True, slots=True)
class OtherInfrastructure:
    """An infrastructure failure no rule names, at the site ``site``."""

    site: str

    def __post_init__(self) -> None:
        require_opaque_id(self.site, "a failure site")


type Ending = (
    Completed
    | ReportedAtCap
    | EndedByDefect
    | SendFailure
    | UnresolvedAtMaximum
    | InputBoundExhausted
    | Abandoned
    | OtherInfrastructure
)

DISPATCH_SEND = "dispatch_send"
"""The site of an infrastructure ending at a dispatch's send that no rule names: an unresolved
last dispatch below the maximum, a harness that gave up. Both projections into this vocabulary
(the agent's, from a log; the evaluator's, from an export) name the site by this."""

INPUT_BOUND = "input_bound"
"""The site of an infrastructure ending at the input bound that no rule names: an unclassified
counting failure, or a harness that gave up below the maximum."""


# --- The decision --------------------------------------------------------------------------


class EligibilityRule(StrEnum):
    """The rule that decided whether a new attempt is permitted; a member is the wire
    format."""

    PREDECESSOR_OPEN = "predecessor_open"
    GRADED_RESULT = "graded_result"
    DEFECT = "defect"
    RECORDED_DEFECT = "recorded_defect"
    SEND_ROW = "send_row"
    UNRESOLVED_AT_MAXIMUM = "unresolved_at_maximum"
    INPUT_BOUND_EXHAUSTED = "input_bound_exhausted"
    ABANDONED_BEFORE_ANY_INTENT = "abandoned_before_any_intent"
    ABANDONED_AFTER_AN_INTENT = "abandoned_after_an_intent"
    NO_RULE_NAMES_THE_ENDING = "no_rule_names_the_ending"
    MAXIMUM_REACHED = "maximum_reached"


@dataclass(frozen=True, slots=True)
class Eligibility:
    """Whether a new attempt is permitted, and the rule that decided. For a send failure
    ``row`` is the attribution row whose flag was read."""

    permitted: bool
    rule: EligibilityRule
    row: str | None = None


def _by_ending(ending: Ending) -> Eligibility:
    match ending:
        case Completed() | ReportedAtCap():
            return Eligibility(False, EligibilityRule.GRADED_RESULT)
        case EndedByDefect():
            return Eligibility(False, EligibilityRule.DEFECT)
        case SendFailure():
            return Eligibility(ending.row_permits, EligibilityRule.SEND_ROW, ending.rule)
        case UnresolvedAtMaximum():
            return Eligibility(True, EligibilityRule.UNRESOLVED_AT_MAXIMUM)
        case InputBoundExhausted():
            return Eligibility(True, EligibilityRule.INPUT_BOUND_EXHAUSTED)
        case Abandoned():
            if ending.dispatch_intents:
                return Eligibility(False, EligibilityRule.ABANDONED_AFTER_AN_INTENT)
            return Eligibility(True, EligibilityRule.ABANDONED_BEFORE_ANY_INTENT)
        case OtherInfrastructure():
            return Eligibility(False, EligibilityRule.NO_RULE_NAMES_THE_ENDING)


def new_attempt_eligibility(
    ending: Ending | None, *, recorded_defect: bool, attempt: int, retry: RetryRule
) -> Eligibility:
    """Whether attempt ``attempt`` of a run, ended as ``ending``, permits an attempt after it.

    ``ending`` is ``None`` while the attempt is open, which permits nothing.
    ``recorded_defect`` says the attempt's log holds a defect whatever its ending names.
    ``retry`` is the registered rule: the category retried after, and the most attempts a
    run has, the first included.

    >>> from leaveimpact.core.run_record import FailureCategory
    >>> rule = RetryRule(FailureCategory.INFRASTRUCTURE, 3)
    >>> lost = UnresolvedAtMaximum()
    >>> new_attempt_eligibility(lost, recorded_defect=False, attempt=1, retry=rule).permitted
    True
    >>> new_attempt_eligibility(lost, recorded_defect=False, attempt=3, retry=rule).rule.value
    'maximum_reached'
    """
    require_integer(attempt, "an attempt number", minimum=1)
    if ending is None:
        return Eligibility(False, EligibilityRule.PREDECESSOR_OPEN)
    if recorded_defect and not isinstance(ending, EndedByDefect):
        return Eligibility(False, EligibilityRule.RECORDED_DEFECT)
    decided = _by_ending(ending)
    if not decided.permitted:
        return decided
    if attempt >= retry.max_attempts:
        return Eligibility(False, EligibilityRule.MAXIMUM_REACHED, decided.row)
    return decided


__all__ = [
    "DISPATCH_SEND",
    "INPUT_BOUND",
    "Abandoned",
    "Completed",
    "Eligibility",
    "EligibilityRule",
    "EndedByDefect",
    "Ending",
    "InputBoundExhausted",
    "OtherInfrastructure",
    "ReportedAtCap",
    "SendFailure",
    "UnresolvedAtMaximum",
    "new_attempt_eligibility",
]
