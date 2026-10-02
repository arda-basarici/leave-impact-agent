"""The grounding replay: for each claim of a report, whether the rules, fed only what the run
read, conclude what the claim says.

Answer grading compares a report with the truth. This asks something else, and needs no
expected answer: does the report assert beyond its evidence. Each claim is replayed
through the same rule the oracle runs, over the observed-run view, and gets one of three
standings (the investigator milestone's fourth build step, ruling 3). *Reproduced*: the
rules conclude the claim's payload. *Contradicted*: they conclude a different one.
*Unsupported*: they cannot conclude from what was read, with a typed reason. A claim can be
right and unsupported (the run guessed, or read too little) and wrong and reproduced (the
systems showed it something the truth does not hold); neither is this module's question.

Nothing here comes from the sealed truth except through what the run read. The leaver and
the leave's span are read off the view, from the absence the leave record the claim names
derives. An assessment is replayed with the report's own constraint claims, an action with
the report's own assessments, and a conclusion about everyone with the candidates the run
itself enumerated. The one sealed thing consulted directly is a requirement clause's scope,
which is not a fact the rules can derive: it is admitted when the clause came back with the
sealed text, as a prose fact is, and the world index has shown that text states it.

*Premises.* A standing is local: it takes the claims a replay consumed as given. An
assessment's replay consumes its impact claim, the report's constraints that apply and,
when it comes out unknown, the unknown claims for the questions it stopped on. An action's
consumes its impact, those constraints and the assessments its outcome needs. Each record
names the premises consumed, by claim id, and the ones the replay needed and the report
does not hold. Whether a claim is grounded end to end is derived from those and stored
nowhere, so one failure is one stored fact however many claims rest on it.

*Proofs.* Every record keeps the witnesses of the rules' own conclusion, whatever the
standing: what supports a reproduced claim, what contradicts a contradicted one, what was
seen and what stopped the answer for an unsupported one. Citations and source discipline
read them. The absence the leave record derives is a witness wherever a replay took the
leaver or the span from it: of every impact, and of an assessment whose window is the
leave's span, which is every need but a meeting's, that one being free over its own day.
An assignment has no witness of its own; it rests on its premises. A conclusion about
everyone has one: the enumeration of the employees, since the replay takes from it who
everyone is, covered when the run listed them and unread or failed when that is what
stopped the answer. No citation can name an enumeration, so it changes nothing a citation
is judged on; it is what lets the read that listed the candidates be credited.

An unknown claim names a subject and a fact and no value or window, so it is replayed
against the questions the replay of the report's own claims stopped on for that subject
and fact. With none, closure is asked directly when the fact is single-valued, the subject
and the fact then being the whole question, and a multi-valued fact is unsupported: nothing
fixes what the claim is about.

A reason only an agent can give (ambiguous, conflicting) is not set aside as a class. It is
contradicted when the rules establish the fact from the run's own reads, and unsupported,
as a reason no rule derives, only when they too leave the question open. The case that
decides it is the one the adversarial tier plants: a runbook names a stale owner, the
tracker's record resolves it by authority, and a report that stops at "conflicting" there
is refuted by what the run read. Filing it as not replayable would say less than the
replay knows. How many unknowns carry an agent's reason is read off the claims
themselves and needs no standing to hold it.

Nothing a report states raises. A constraint whose clause was read and states no
requirement is not fed to a replay, since the rule cannot apply it: it is contradicted
itself and stays a premise of what cited it. An event read and holding no schedule gives
no need to assess against.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.authority import conflicts_in
from leaveimpact.core.claims import (
    AssessmentKey,
    CandidateAssessment,
    Claim,
    ClaimType,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    GradingKey,
    Impact,
    ImpactKey,
    SourceConflict,
    Unknown,
    UnknownKey,
    UnknownReason,
    Verdict,
    require_well_formed,
)
from leaveimpact.core.closure import (
    Consulted,
    KnownFalse,
    Proof,
    Unresolved,
    establish,
    proof_of,
)
from leaveimpact.core.coverage import KindSlice, SliceStatus
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import Fact, FactView
from leaveimpact.core.grounding import Grounded, Ungrounded, ground_impact
from leaveimpact.core.ids import ClaimId, EmployeeId, LeaveId
from leaveimpact.core.plans import ViolationKind
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import EntityRef, clause_ref, leave_ref
from leaveimpact.core.viability import assess_impact, need_of
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.evaluator.observed_view import ObservedRun
from leaveimpact.evaluator.plan_reading import PlanUnreadable, read_plan
from leaveimpact.evaluator.world_index import WorldIndex

_DERIVED_REASONS = frozenset(
    {UnknownReason.ABSENT, UnknownReason.INACCESSIBLE, UnknownReason.INSUFFICIENT}
)
"""The reasons closure derives; the other two are an agent's to give."""


class Standing(StrEnum):
    """What the rules make of a claim over what the run read; a member is the wire format."""

    REPRODUCED = "reproduced"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"


class UnsupportedReason(StrEnum):
    """Why the rules could not conclude a claim from what was read."""

    LEAVE_NOT_READ = "leave_not_read"
    NOT_CONCLUDED = "not_concluded"
    CLAUSE_NOT_READ = "clause_not_read"
    NEED_NOT_READABLE = "need_not_readable"
    UNKNOWN_WITHOUT_QUESTION = "unknown_without_question"
    NON_REPLAYABLE_UNKNOWN_REASON = "non_replayable_unknown_reason"
    OBSERVATION_NOT_READ = "observation_not_read"
    PLAN_NOT_READABLE = "plan_not_readable"
    ASSIGNEE_NOT_ASSESSED = "assignee_not_assessed"
    UNIVERSE_NOT_READ = "universe_not_read"
    UNIVERSE_NOT_ASSESSED = "universe_not_assessed"


@dataclass(frozen=True, slots=True)
class MissingPremise:
    """A claim a replay needed and the report does not hold: its type and its grading key."""

    claim_type: ClaimType
    key: GradingKey


@dataclass(frozen=True, slots=True)
class ClaimGrounding:
    """One claim's local standing, with what it rests on.

    ``reason`` is set exactly for an unsupported standing. ``proof`` holds the witnesses of
    the rules' own conclusion. ``premises`` are the claims the replay consumed and
    ``missing_premises`` the ones it needed and the report lacks; the standing takes the
    first as given and is unsupported, with its reason, when one of the second stops it.
    """

    claim_id: ClaimId
    claim_type: ClaimType
    standing: Standing
    reason: UnsupportedReason | None = None
    proof: Proof = ()
    premises: tuple[ClaimId, ...] = ()
    missing_premises: tuple[MissingPremise, ...] = ()

    def __post_init__(self) -> None:
        if (self.reason is not None) != (self.standing is Standing.UNSUPPORTED):
            raise ValueError(
                f"{self.claim_id}: an unsupported standing states its reason, and only it does"
            )


def replay(
    observed: ObservedRun,
    index: WorldIndex,
    claims: Sequence[Claim],
    reference_timezone: str,
) -> tuple[ClaimGrounding, ...]:
    """Every claim's local standing over what ``observed`` holds, in ``claims``' order.

    ``claims`` is a structurally valid set, the replay's precondition as it is the plan
    checks': a caller holding an invalid one records grounding as not evaluated.
    """
    require_well_formed(claims)
    run = _Run(observed, index, claims, reference_timezone)
    done: dict[ClaimId, ClaimGrounding] = {}
    # Unknowns last: they are replayed against the questions the other replays stopped on.
    for claim in sorted(claims, key=lambda claim: isinstance(claim, Unknown)):
        match claim:
            case Impact():
                done[claim.claim_id] = run.impact(claim)
            case Constraint():
                done[claim.claim_id] = run.constraint(claim)
            case CandidateAssessment():
                done[claim.claim_id] = run.assessment(claim)
            case SourceConflict():
                done[claim.claim_id] = run.conflict(claim)
            case CoverageAction():
                done[claim.claim_id] = run.action(claim)
            case Unknown():
                done[claim.claim_id] = run.unknown(claim)
    return tuple(done[claim.claim_id] for claim in claims)


class _Run:
    """One replay: the view, the report's claims by key, and the questions it stopped on."""

    def __init__(
        self,
        observed: ObservedRun,
        index: WorldIndex,
        claims: Sequence[Claim],
        reference_timezone: str,
    ) -> None:
        self.observed = observed
        self.view: FactView = observed.view
        self.index = index
        self.timezone = reference_timezone
        self.impacts = {c.key: c for c in claims if isinstance(c, Impact)}
        self.constraints = [c for c in claims if isinstance(c, Constraint)]
        self.assessments = [c for c in claims if isinstance(c, CandidateAssessment)]
        self.unknowns = {c.key: c for c in claims if isinstance(c, Unknown)}
        self.stopped: dict[UnknownKey, list[Unresolved]] = {}
        # A clause read and stating no requirement cannot be applied by the rule.
        self.appliable = [
            constraint.key
            for constraint in self.constraints
            if not isinstance(self._requirement(constraint), KnownFalse)
        ]

    # --- What the run read ---------------------------------------------------------------

    def _leave(self, leave_id: LeaveId) -> tuple[EmployeeId, DateSpan, Fact] | None:
        """The leaver and the span of ``leave_id`` as the run read them, with the fact that
        says so, or ``None`` when the run did not read that leave."""
        record = leave_ref(leave_id)
        for fact in self.view.facts_of(PredicateName.ON_LEAVE):
            if fact.evidence.target == record and isinstance(fact.value, DateSpan):
                return EmployeeId(fact.subject.id), fact.value, fact
        return None

    def _universe(self) -> tuple[tuple[EmployeeId, ...] | None, Consulted]:
        """The candidates the run enumerated, or ``None`` when it never listed them whole, with
        what the run's coverage says of that enumeration: the witness of who everyone is."""
        everyone = KindSlice(EntityKind.EMPLOYEE)
        asked = Consulted(everyone, self.observed.coverage.status(everyone))
        if asked.status is not SliceStatus.COVERED:
            return None, asked
        listed = tuple(
            sorted(
                EmployeeId(ref.id)
                for ref in self.observed.coverage.returned
                if ref.kind is EntityKind.EMPLOYEE
            )
        )
        return listed, asked

    def _requirement(self, constraint: Constraint) -> object:
        return establish(self.view, clause_ref(constraint.clause_id), PredicateName.REQUIRES)

    def _stop(self, question: Unresolved) -> None:
        key = UnknownKey(question.subject, question.predicate)
        self.stopped.setdefault(key, []).append(question)

    # --- Premises ------------------------------------------------------------------------

    def _impact_premise(
        self, impact: ImpactKey
    ) -> tuple[tuple[ClaimId, ...], tuple[MissingPremise, ...]]:
        held = self.impacts.get(impact)
        if held is None:
            return (), (MissingPremise(ClaimType.IMPACT, impact),)
        return (held.claim_id,), ()

    def _constraints_about(self, scope: set[EntityRef]) -> tuple[ClaimId, ...]:
        """The report's constraint claims that name something in ``scope``."""
        return tuple(c.claim_id for c in self.constraints if c.applies_to in scope)

    def _scope_of(self, impact: ImpactKey, span: DateSpan) -> set[EntityRef]:
        """What a constraint may name to apply to ``impact``: the artifact, and its component
        when the run read it."""
        scope = {impact.artifact}
        try:
            need = need_of(self.view, impact, span, self.timezone)
        except ValueError:
            return scope
        if not isinstance(need, Unresolved) and isinstance(need.component, EntityRef):
            scope.add(need.component)
        return scope

    # --- The six replays -----------------------------------------------------------------

    def impact(self, claim: Impact) -> ClaimGrounding:
        leave = self._leave(claim.leave_id)
        if leave is None:
            return _unsupported(claim, UnsupportedReason.LEAVE_NOT_READ)
        leaver, span, read = leave
        grounding = ground_impact(self.view, claim.key, leaver, span, self.timezone)
        # Who is leaving and when is a premise of the question, read off the leave record.
        proof = proof_of((read,), grounding.proof)
        match grounding:
            case Grounded():
                return ClaimGrounding(
                    claim.claim_id, claim.claim_type, Standing.REPRODUCED, proof=proof
                )
            case Ungrounded():
                return ClaimGrounding(
                    claim.claim_id, claim.claim_type, Standing.CONTRADICTED, proof=proof
                )
            case Unresolved():
                self._stop(grounding)
                return _unsupported(claim, UnsupportedReason.NOT_CONCLUDED, proof)

    def constraint(self, claim: Constraint) -> ClaimGrounding:
        clause = clause_ref(claim.clause_id)
        stated = establish(self.view, clause, PredicateName.REQUIRES)
        if clause not in self.observed.read_as_sealed:
            return _unsupported(claim, UnsupportedReason.CLAUSE_NOT_READ, stated.proof)
        # The clause came back with the sealed text, which the index has shown names its
        # scope: the sealed pairing is what the run read.
        same = self.index.scope.get(claim.clause_id) == claim.applies_to
        standing = Standing.REPRODUCED if same else Standing.CONTRADICTED
        return ClaimGrounding(claim.claim_id, claim.claim_type, standing, proof=stated.proof)

    def assessment(self, claim: CandidateAssessment) -> ClaimGrounding:
        impact = claim.impact_key
        premises, missing = self._impact_premise(impact)
        leave = self._leave(impact.leave_id)
        if leave is None:
            return _unsupported(
                claim, UnsupportedReason.LEAVE_NOT_READ, premises=premises, missing=missing
            )
        _, span, read = leave
        premises += self._constraints_about(self._scope_of(impact, span))
        try:
            (rule,) = assess_impact(
                self.view, impact, (claim.employee_id,), self.appliable, span, self.timezone
            )
        except ValueError:
            return _unsupported(
                claim, UnsupportedReason.NEED_NOT_READABLE, premises=premises, missing=missing
            )
        # A meeting is covered on its own day; every other need over the leave's span.
        over_the_leave = impact.artifact.kind is not EntityKind.EVENT
        proof = proof_of((read,), rule.proof) if over_the_leave else rule.proof
        for question in rule.unresolved:
            self._stop(question)
        if (rule.verdict, rule.reasons) != (claim.verdict, claim.reasons):
            if rule.verdict is Verdict.UNKNOWN:
                return _unsupported(
                    claim, UnsupportedReason.NOT_CONCLUDED, proof, premises, missing
                )
            return ClaimGrounding(
                claim.claim_id,
                claim.claim_type,
                Standing.CONTRADICTED,
                proof=proof,
                premises=premises,
                missing_premises=missing,
            )
        for question in rule.unresolved:
            key = UnknownKey(question.subject, question.predicate)
            behind = self.unknowns.get(key)
            if behind is None:
                missing += (MissingPremise(ClaimType.UNKNOWN, key),)
            elif behind.claim_id not in premises:
                premises += (behind.claim_id,)
        return ClaimGrounding(
            claim.claim_id,
            claim.claim_type,
            Standing.REPRODUCED,
            proof=proof,
            premises=premises,
            missing_premises=missing,
        )

    def conflict(self, claim: SourceConflict) -> ClaimGrounding:
        held = self.view.facts_about(claim.entity, claim.predicate)
        found = next(
            (
                finding
                for finding in conflicts_in(self.view)
                if (finding.subject, finding.predicate) == (claim.entity, claim.predicate)
            ),
            None,
        )
        if found is None:
            read = {fact.source for fact in held}
            if any(observation.source not in read for observation in claim.observations):
                return _unsupported(claim, UnsupportedReason.OBSERVATION_NOT_READ, held)
            return ClaimGrounding(
                claim.claim_id, claim.claim_type, Standing.CONTRADICTED, proof=held
            )
        same = (
            frozenset(found.observations) == frozenset(claim.observations)
            and found.resolution.value == claim.resolved_value
            and found.resolution.rule is claim.authority_rule
        )
        standing = Standing.REPRODUCED if same else Standing.CONTRADICTED
        return ClaimGrounding(claim.claim_id, claim.claim_type, standing, proof=found.facts)

    def action(self, claim: CoverageAction) -> ClaimGrounding:
        impact = claim.impact_key
        premises, missing = self._impact_premise(impact)
        leave = self._leave(impact.leave_id)
        if leave is None:
            return _unsupported(
                claim, UnsupportedReason.LEAVE_NOT_READ, premises=premises, missing=missing
            )
        _, span, _ = leave
        premises += self._constraints_about(self._scope_of(impact, span))
        about_everyone = claim.action is not CoverageActionKind.ASSIGN
        universe: tuple[EmployeeId, ...] | None = None
        proof: Proof = ()
        if about_everyone:
            universe, listed = self._universe()
            proof = (listed,)
            if universe is None:
                return _unsupported(
                    claim, UnsupportedReason.UNIVERSE_NOT_READ, proof, premises, missing
                )
        plan = read_plan(
            claim,
            [constraint.key for constraint in self.constraints],
            self.assessments,
            self.view,
            span,
            self.timezone,
            universe,
        )
        if isinstance(plan, PlanUnreadable):
            return _unsupported(
                claim, UnsupportedReason.PLAN_NOT_READABLE, proof, premises, missing
            )
        needed = claim.assignee_ids if universe is None else universe
        assessed = {a.employee_id: a.claim_id for a in self.assessments if a.impact_key == impact}
        premises += tuple(assessed[employee] for employee in needed if employee in assessed)
        if about_everyone:
            # The unassessed are named by the coverage gap; here their absence is the reason.
            if plan.unassessed:
                return _unsupported(
                    claim, UnsupportedReason.UNIVERSE_NOT_ASSESSED, proof, premises, missing
                )
            standing = (
                Standing.REPRODUCED if plan.expected is claim.action else Standing.CONTRADICTED
            )
        else:
            unassessed = tuple(e for e in claim.assignee_ids if e not in assessed)
            if unassessed:
                missing += tuple(
                    MissingPremise(ClaimType.CANDIDATE_ASSESSMENT, AssessmentKey(impact, employee))
                    for employee in unassessed
                )
                return _unsupported(
                    claim,
                    UnsupportedReason.ASSIGNEE_NOT_ASSESSED,
                    premises=premises,
                    missing=missing,
                )
            failed = [v for v in plan.violations if v.kind is not ViolationKind.MISSING_ASSESSMENT]
            standing = Standing.CONTRADICTED if failed else Standing.REPRODUCED
        return ClaimGrounding(
            claim.claim_id,
            claim.claim_type,
            standing,
            proof=proof,
            premises=premises,
            missing_premises=missing,
        )

    def unknown(self, claim: Unknown) -> ClaimGrounding:
        derived = claim.reason in _DERIVED_REASONS
        stopped = self.stopped.get(claim.key, [])
        if stopped:
            proof = proof_of(*(question.proof for question in stopped))
            if not derived:
                return _unsupported(claim, UnsupportedReason.NON_REPLAYABLE_UNKNOWN_REASON, proof)
            same = any(question.reason is claim.reason for question in stopped)
            standing = Standing.REPRODUCED if same else Standing.CONTRADICTED
            return ClaimGrounding(claim.claim_id, claim.claim_type, standing, proof=proof)
        if predicate(claim.required_fact).multi_valued:
            return _unsupported(claim, UnsupportedReason.UNKNOWN_WITHOUT_QUESTION)
        answer = establish(self.view, claim.subject, claim.required_fact)
        if isinstance(answer, Unresolved):
            if not derived:
                return _unsupported(
                    claim, UnsupportedReason.NON_REPLAYABLE_UNKNOWN_REASON, answer.proof
                )
            if answer.reason is claim.reason:
                return ClaimGrounding(
                    claim.claim_id, claim.claim_type, Standing.REPRODUCED, proof=answer.proof
                )
        return ClaimGrounding(
            claim.claim_id, claim.claim_type, Standing.CONTRADICTED, proof=answer.proof
        )


def _unsupported(
    claim: Claim,
    reason: UnsupportedReason,
    proof: Proof = (),
    premises: tuple[ClaimId, ...] = (),
    missing: tuple[MissingPremise, ...] = (),
) -> ClaimGrounding:
    return ClaimGrounding(
        claim.claim_id, claim.claim_type, Standing.UNSUPPORTED, reason, proof, premises, missing
    )


__all__ = [
    "ClaimGrounding",
    "MissingPremise",
    "Standing",
    "UnsupportedReason",
    "replay",
]
