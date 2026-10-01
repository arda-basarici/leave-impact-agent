"""The grade's rows: one record per expected or reported claim, the four judgments kept apart.

A report is graded claim by claim, and a claim's grade is not one word. Four different
things are true of it and a table needs each on its own (the matching ruling of the
investigator milestone's third build step):

- *Expectation.* What the oracle holds for the claim's grading key. ``required``: a
  report must hold it, and its absence is a miss. ``optional``: the rules derive it and it
  is true, yet outside the bounded probe set, so a report that holds it is judged and one
  that does not is not penalized. ``unexpected``: the oracle does not expect it.
  ``not_matched``: the report's claim set was structurally invalid, so no key of it was
  matched at all.
- *Presence.* Whether the report holds the claim: a row with no ``claim_id`` is a required
  key the report missed. A row exists for every required key and for every reported
  claim, and for nothing else; an optional key nobody reported has no row.
- *Standing.* For a reported claim the oracle does not expect, which named kind of
  unexpected it is, per claim type. This is where "wrong" is kept from being one bucket:
  a planted distractor, an impact the run could not have established, a conflict that is
  real and beside the point, a gap claimed where the world is complete.
- *Payload.* For a reported claim the oracle can judge, whether what it states is right,
  flag by flag. An impact and a constraint have no payload: their key is the whole fact.

Each claim type has its own frozen record, and each record refuses the combinations that
mean nothing: a missed row holds no reported payload, a standing sits only on a reported
claim the oracle does not expect, a flag is set exactly when both sides of the comparison
exist. Nothing here is a count. Precision, recall and every table are aggregated from the
rows by the step that reports them, so a table can be recut without regrading, and the
rows say which claims matched, which is why an evaluation is stored with the answer key.

A true positive is a required key the report holds with a correct payload; a required key
it does not hold is a false negative; a held key with a wrong payload is never a true
positive. A correct optional claim counts for precision and not for recall.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.claims import (
    AssessmentKey,
    AssessmentReason,
    AuthorityRule,
    ConflictKey,
    ConstraintKey,
    CoverageActionKind,
    ImpactKey,
    UnknownKey,
    UnknownReason,
    Verdict,
)
from leaveimpact.core.ids import ClaimId, EmployeeId
from leaveimpact.core.values import FactValue
from leaveimpact.world.scenario import DistractorReason

Judgment = tuple[Verdict, tuple[AssessmentReason, ...]]
"""A verdict with its reasons: an assessment's payload."""

Resolution = tuple[FactValue, AuthorityRule]
"""A conflict's payload: the value that stands and the rule that chose it."""


class Expectation(StrEnum):
    """What the oracle holds for a claim's grading key; a member is the wire format."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    UNEXPECTED = "unexpected"
    NOT_MATCHED = "not_matched"


class ImpactStanding(StrEnum):
    """Why a reported impact is not an expected one."""

    DISTRACTOR = "distractor"
    """A planted near-miss; the row carries the reason it was planted with."""
    UNSUPPORTED_UNDER_THE_CONDITION = "unsupported_under_the_condition"
    """Whether the leaver holds it is open under the run's condition: the run could not have
    established it. Not a true positive and not factually false; it counts against strict
    precision and is reported apart from the false positives."""
    FALSE_POSITIVE = "false_positive"
    """The rules conclude the leaver does not hold it, or it is another leave's."""
    STRUCTURALLY_INVALID = "structurally_invalid"


class ConstraintStanding(StrEnum):
    """Why a reported constraint is not an expected one. A constraint's scope is authored in
    the key and no fact states it, so the oracle judges no further than this."""

    FALSE_POSITIVE = "false_positive"
    STRUCTURALLY_INVALID = "structurally_invalid"


class AssessmentStanding(StrEnum):
    """Why a reported assessment cannot be judged."""

    ON_AN_UNEXPECTED_IMPACT = "on_an_unexpected_impact"
    NOT_IN_THE_ORGANIZATION = "not_in_the_organization"
    STRUCTURALLY_INVALID = "structurally_invalid"


class ActionStanding(StrEnum):
    """Why a reported coverage action cannot be judged."""

    ON_AN_UNEXPECTED_IMPACT = "on_an_unexpected_impact"
    STRUCTURALLY_INVALID = "structurally_invalid"


class ConflictStanding(StrEnum):
    """Why a reported conflict is not an expected one."""

    RELEVANCE_ERROR = "relevance_error"
    """The sources do disagree in the oracle's view, on a fact this investigation did not
    need: real, and beside the point. Its payload is still judged."""
    UNSUPPORTED = "unsupported"
    """The oracle's view holds no such disagreement."""
    STRUCTURALLY_INVALID = "structurally_invalid"


class UnknownStanding(StrEnum):
    """Why a reported unknown is not an expected one."""

    RESOLVED_IN_THE_ORACLE = "resolved_in_the_oracle"
    """A gap claimed where the world is complete: the oracle settles the fact."""
    NOT_ASKED_BY_THE_RULES = "not_asked_by_the_rules"
    """The fact is open in the oracle too, and no assessment needed it: a true gap beside the
    point, the unknown's counterpart of a conflict's relevance error."""
    STRUCTURALLY_INVALID = "structurally_invalid"


def _require_axes(
    row: str, expectation: Expectation, claim_id: ClaimId | None, standing: object | None
) -> None:
    """The combinations of the three shared axes that mean something.

    Required: reported or missed, never with a standing. Optional: reported, no standing.
    Unexpected and not-matched: reported, with a standing, and not-matched goes with the
    structurally-invalid standing and nothing else.
    """
    invalid = getattr(standing, "value", None) == "structurally_invalid"
    match expectation:
        case Expectation.REQUIRED:
            if standing is not None:
                raise ValueError(f"{row}: a required key has no standing")
        case Expectation.OPTIONAL:
            if claim_id is None or standing is not None:
                raise ValueError(f"{row}: an optional row is a reported claim with no standing")
        case Expectation.UNEXPECTED:
            if claim_id is None or standing is None or invalid:
                raise ValueError(
                    f"{row}: an unexpected row is a reported claim with the standing that says "
                    "why, other than structurally invalid"
                )
        case Expectation.NOT_MATCHED:
            if claim_id is None or not invalid:
                raise ValueError(
                    f"{row}: a claim that was not matched is reported and structurally invalid"
                )


def _require_flag(row: str, name: str, flag: bool | None, *sides: object | None) -> None:
    """A payload flag is set exactly when both sides it compares exist."""
    comparable = all(side is not None for side in sides)
    if (flag is not None) != comparable:
        raise ValueError(f"{row}: {name} is judged exactly when both payloads exist")


@dataclass(frozen=True, slots=True)
class ImpactRow:
    """One expected or reported impact. The key is the whole fact, so there is no payload.

    ``near_miss_of`` is the expected impact a reported one shares its artifact with while
    naming another subtype; it earns no credit and explains the assessments and actions
    that land on an unexpected impact behind it.
    """

    key: ImpactKey
    expectation: Expectation
    claim_id: ClaimId | None
    standing: ImpactStanding | None = None
    distractor_reason: DistractorReason | None = None
    near_miss_of: ImpactKey | None = None

    def __post_init__(self) -> None:
        _require_axes("an impact row", self.expectation, self.claim_id, self.standing)
        if self.expectation is Expectation.OPTIONAL:
            raise ValueError("an impact row: an impact is required or unexpected, never optional")
        if (self.distractor_reason is not None) != (self.standing is ImpactStanding.DISTRACTOR):
            raise ValueError("an impact row: a distractor carries its planted reason, and only it")
        if self.near_miss_of is not None and self.expectation is not Expectation.UNEXPECTED:
            raise ValueError("an impact row: only an unexpected impact is a near miss of another")


@dataclass(frozen=True, slots=True)
class ConstraintRow:
    """One expected or reported constraint. The key is the whole fact, so there is no payload."""

    key: ConstraintKey
    expectation: Expectation
    claim_id: ClaimId | None
    standing: ConstraintStanding | None = None

    def __post_init__(self) -> None:
        _require_axes("a constraint row", self.expectation, self.claim_id, self.standing)
        if self.expectation is Expectation.OPTIONAL:
            raise ValueError("a constraint row: a constraint is required or unexpected")


@dataclass(frozen=True, slots=True)
class AssessmentRow:
    """One expected or reported assessment: a candidate for an impact.

    ``expected`` is the oracle's verdict and reasons whenever it has them (a required or an
    optional row), ``reported`` the report's. The two flags are set exactly when both
    exist, and the payload is correct when both flags are true.
    """

    key: AssessmentKey
    expectation: Expectation
    claim_id: ClaimId | None
    standing: AssessmentStanding | None = None
    expected: Judgment | None = None
    reported: Judgment | None = None
    verdict_matches: bool | None = None
    reasons_match: bool | None = None

    def __post_init__(self) -> None:
        _require_axes("an assessment row", self.expectation, self.claim_id, self.standing)
        if (self.reported is not None) != (self.claim_id is not None):
            raise ValueError("an assessment row: a reported payload exactly for a reported claim")
        judged = self.expectation in (Expectation.REQUIRED, Expectation.OPTIONAL)
        if (self.expected is not None) != judged:
            raise ValueError(
                "an assessment row: the oracle's judgment exactly for a required or optional key"
            )
        for name, flag in (("verdict", self.verdict_matches), ("reasons", self.reasons_match)):
            _require_flag("an assessment row", name, flag, self.expected, self.reported)

    @property
    def payload_correct(self) -> bool | None:
        """Whether verdict and reasons are both right; ``None`` when the row is not judged."""
        if self.verdict_matches is None or self.reasons_match is None:
            return None
        return self.verdict_matches and self.reasons_match


@dataclass(frozen=True, slots=True)
class ActionRow:
    """One expected or reported coverage action, keyed by its impact.

    ``outcome_matches`` compares the action kind with the outcome the oracle expects; it is
    the outcome judgment and not a verdict on the plan, since whom an assign names is
    judged by the plan checks. No assignee set is truth, so ``assignees`` is what the
    report named and nothing is expected of it here.
    """

    key: ImpactKey
    expectation: Expectation
    claim_id: ClaimId | None
    standing: ActionStanding | None = None
    expected: CoverageActionKind | None = None
    reported: CoverageActionKind | None = None
    assignees: tuple[EmployeeId, ...] = ()
    outcome_matches: bool | None = None

    def __post_init__(self) -> None:
        _require_axes("an action row", self.expectation, self.claim_id, self.standing)
        if self.expectation is Expectation.OPTIONAL:
            raise ValueError("an action row: an action is required or unexpected, never optional")
        if (self.reported is not None) != (self.claim_id is not None):
            raise ValueError("an action row: a reported action exactly for a reported claim")
        if (self.expected is not None) != (self.expectation is Expectation.REQUIRED):
            raise ValueError("an action row: the expected outcome exactly for a required key")
        if self.assignees and self.claim_id is None:
            raise ValueError("an action row: a missed action names nobody")
        _require_flag(
            "an action row", "outcome", self.outcome_matches, self.expected, self.reported
        )


@dataclass(frozen=True, slots=True)
class ConflictRow:
    """One expected or reported source conflict.

    ``expected`` is the oracle's resolution whenever the disagreement is real in its view:
    a required key, or a reported conflict that is a relevance error, whose payload is
    still judged. ``observations_hold`` says every observation the report cites is a value
    that source holds in the oracle's view, and is set for every reported conflict.
    """

    key: ConflictKey
    expectation: Expectation
    claim_id: ClaimId | None
    standing: ConflictStanding | None = None
    expected: Resolution | None = None
    reported: Resolution | None = None
    value_matches: bool | None = None
    rule_matches: bool | None = None
    observations_hold: bool | None = None

    def __post_init__(self) -> None:
        _require_axes("a conflict row", self.expectation, self.claim_id, self.standing)
        if self.expectation is Expectation.OPTIONAL:
            raise ValueError("a conflict row: a conflict is required or unexpected")
        if (self.reported is not None) != (self.claim_id is not None):
            raise ValueError("a conflict row: a reported resolution exactly for a reported claim")
        real = self.expectation is Expectation.REQUIRED or (
            self.standing is ConflictStanding.RELEVANCE_ERROR
        )
        if (self.expected is not None) != real:
            raise ValueError(
                "a conflict row: the oracle's resolution exactly when the disagreement is real"
            )
        for name, flag in (("value", self.value_matches), ("rule", self.rule_matches)):
            _require_flag("a conflict row", name, flag, self.expected, self.reported)
        matched = self.claim_id is not None and self.expectation is not Expectation.NOT_MATCHED
        if (self.observations_hold is not None) != matched:
            raise ValueError("a conflict row: observations are checked for every matched report")

    @property
    def payload_correct(self) -> bool | None:
        """Whether the resolved value and the rule are both right; ``None`` when not judged."""
        if self.value_matches is None or self.rule_matches is None:
            return None
        return self.value_matches and self.rule_matches


@dataclass(frozen=True, slots=True)
class UnknownRow:
    """One expected or reported unknown: a fact about a subject that could not be settled.

    ``expected`` is the reason the oracle gives whenever the fact is open in its view: a
    required or optional key, or a reported unknown the rules did not ask about.
    """

    key: UnknownKey
    expectation: Expectation
    claim_id: ClaimId | None
    standing: UnknownStanding | None = None
    expected: UnknownReason | None = None
    reported: UnknownReason | None = None
    reason_matches: bool | None = None

    def __post_init__(self) -> None:
        _require_axes("an unknown row", self.expectation, self.claim_id, self.standing)
        if (self.reported is not None) != (self.claim_id is not None):
            raise ValueError("an unknown row: a reported reason exactly for a reported claim")
        open_in_the_oracle = self.expectation in (Expectation.REQUIRED, Expectation.OPTIONAL) or (
            self.standing is UnknownStanding.NOT_ASKED_BY_THE_RULES
        )
        if (self.expected is not None) != open_in_the_oracle:
            raise ValueError(
                "an unknown row: the oracle's reason exactly when the fact is open in its view"
            )
        _require_flag("an unknown row", "reason", self.reason_matches, self.expected, self.reported)


@dataclass(frozen=True, slots=True)
class ClaimRows:
    """Every row of one graded report, by claim type, and the structural findings.

    ``structural_problems`` is empty for a report whose claim set is well-formed. When it
    is not, nothing was matched: every required key is a missed row, every reported claim
    a not-matched row with the structurally-invalid standing.
    """

    impacts: tuple[ImpactRow, ...]
    constraints: tuple[ConstraintRow, ...]
    assessments: tuple[AssessmentRow, ...]
    actions: tuple[ActionRow, ...]
    conflicts: tuple[ConflictRow, ...]
    unknowns: tuple[UnknownRow, ...]
    structural_problems: tuple[str, ...] = ()

    @property
    def structurally_valid(self) -> bool:
        return not self.structural_problems


__all__ = [
    "ActionRow",
    "ActionStanding",
    "AssessmentRow",
    "AssessmentStanding",
    "ClaimRows",
    "ConflictRow",
    "ConflictStanding",
    "ConstraintRow",
    "ConstraintStanding",
    "Expectation",
    "ImpactRow",
    "ImpactStanding",
    "Judgment",
    "Resolution",
    "UnknownRow",
    "UnknownStanding",
]
