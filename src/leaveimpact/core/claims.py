"""The claim vocabulary: six typed claims, their grading keys, and the well-formed claim set.

The report and the answer key speak this one vocabulary (DESIGN, "The answer-key
contract"): impacts say what the leave affects, constraints what a valid response must
obey, candidate assessments who could satisfy a need, coverage actions what the plan
does, conflicts and unknowns where the evidence chain could not be established. Each
claim computes its *grading key* from its own fields — the identity of the world fact
it states, the same in the agent's report and in the answer key — while ``claim_id``
is minted by whichever emitter wrote the report and links claims only inside that
report, through ``derived_from_claim_ids``. A key computed from the payload can never
disagree with it; a stored one could. ``entity_refs``, what a claim is about, is
derived from the key for the same reason.

A frozen keyword-only base declares the shared fields once; the six subclasses add
their own, and ``Claim`` — the union, not the base — is what functions accept, so a
``match`` over it with ``assert_never`` makes a forgotten type a type error. The class
attribute ``claim_type`` is the serialization tag: never a stored field, because a
stored tag could disagree with the Python class. Each subclass validates its own
payload at construction — a viable assessment carries no reasons, an assign action
names at least one assignee, a conflict observes at least two sources inside the
predicate's evidence domain — so a malformed claim fails where it is built, and the
JSON codec decodes through these constructors so validation has one home. A repeated
field whose order has no domain meaning — evidence, derivations, reasons, observations,
assignees — is put in canonical order at construction, so two claims stating the same
thing are equal in memory as well as in bytes, and the codec never has to sort.

Clause-backed requirements become constraint claims: a constraint's rule is its
clause, and a constraint the agent cannot trace to a clause cannot be expressed.
Deterministic domain rules (the cover may not itself be on leave) constrain validity
inside the viability rule without becoming claims. An impact *is* the coverage need —
cardinality and eligibility come from constraints and rules — so assessments and
coverage actions key on the impact's key, which carries the leave because an impact's
identity is world-wide ("this leave affects this artifact"), not per report.

``structural_problems`` is the set-level check the evaluator runs on a report before
grading it: unique ids, references that resolve, an acyclic provenance graph, one claim
per grading key and type. The semantic chain — an unknown assessment rests on an
unknown claim — belongs to the rules, which define the chain.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar

from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import ClaimId, ClauseId, EmployeeId, LeaveId, is_numbered_id
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import (
    EntityRef,
    EvidenceRef,
    FactValue,
    Observation,
    clause_ref,
    employee_ref,
    leave_ref,
    require_id,
    with_article,
)


class ClaimType(StrEnum):
    """The six claim types; a member is the JSON tag and the class attribute ``claim_type``."""

    IMPACT = "impact"
    CONSTRAINT = "constraint"
    CANDIDATE_ASSESSMENT = "candidate_assessment"
    SOURCE_CONFLICT = "source_conflict"
    UNKNOWN = "unknown"
    COVERAGE_ACTION = "coverage_action"


class ImpactSubtype(StrEnum):
    """What kind of thing the leave affects.

    A ``dependency`` subtype waits for a scenario class that needs it.
    """

    DEADLINE = "deadline"
    MEETING = "meeting"
    RESPONSIBILITY = "responsibility"


class Verdict(StrEnum):
    """Whether a person can satisfy a need: relational, never a preference."""

    VIABLE = "viable"
    NON_VIABLE = "non_viable"
    UNKNOWN = "unknown"


class AssessmentReason(StrEnum):
    """Why a candidate is non-viable — the criteria the viability rule checks.

    Seeded from what DESIGN and the vision already name; the viability rule closes the
    vocabulary at the rules step, and a member it never emits is pruned there.
    """

    SKILL = "skill"
    COMPONENT = "component"
    AVAILABILITY = "availability"
    LOAD = "load"
    HARD_RULE = "hard_rule"


class UnknownReason(StrEnum):
    """Why a required fact could not be established (DESIGN, the closed-world rule)."""

    ABSENT = "absent"
    INACCESSIBLE = "inaccessible"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"


class CoverageActionKind(StrEnum):
    """A positive conclusion, a negative one, and an epistemic limit — kept apart on purpose."""

    ASSIGN = "assign"
    UNCOVERED = "uncovered"
    UNKNOWN = "unknown"


class AuthorityRule(StrEnum):
    """The rule that resolved a conflict, cited so precedence is testable, never intuited."""

    SYSTEM_OF_RECORD_WINS = "system_of_record_wins"


ARTIFACT_KINDS: Mapping[ImpactSubtype, frozenset[EntityKind]] = MappingProxyType(
    {
        ImpactSubtype.DEADLINE: frozenset({EntityKind.WORK_ITEM}),
        ImpactSubtype.MEETING: frozenset({EntityKind.EVENT}),
        # An existing obligation attached to the leaver may be a ticket or a runbook
        # paragraph naming a client contact.
        ImpactSubtype.RESPONSIBILITY: frozenset({EntityKind.WORK_ITEM, EntityKind.CLAUSE}),
    }
)
"""Which kinds of artifact each impact subtype can be about."""

CLAIM_ID_PREFIX = "claim"


def _require_claim_id(value: str) -> None:
    if not is_numbered_id(value) or value.rsplit("_", 1)[0] != CLAIM_ID_PREFIX:
        raise ValueError(f"a claim id has the form {CLAIM_ID_PREFIX}_NNN, got {value!r}")


def _require_subject_of(name: PredicateName, entity: EntityRef) -> None:
    expected = predicate(name).subject
    if entity.kind is not expected:
        raise ValueError(
            f"{name.value} is a fact about {with_article(expected.value)}, "
            f"got {with_article(entity.kind.value)}"
        )


type _Order[T] = Callable[[T], tuple[str, ...]]


def _canonical[T](items: tuple[T, ...], order: _Order[T]) -> tuple[T, ...]:
    return tuple(sorted(items, key=order))


def _by_text(item: object) -> tuple[str, ...]:
    return (str(item),)


def _by_source(observation: Observation) -> tuple[str, ...]:
    return (observation.source.value,)


def _evidence_order(evidence: EvidenceRef) -> tuple[str, ...]:
    return (
        evidence.source.value,
        evidence.target.kind.value,
        evidence.target.id,
        evidence.field or "",
    )


def _set_canonical[T](claim: ClaimBase, name: str, items: tuple[T, ...], order: _Order[T]) -> None:
    # A frozen dataclass refuses assignment; canonical order is the one write the
    # constructor makes on its own field before the object is seen by anyone.
    object.__setattr__(claim, name, _canonical(items, order))


# --- Grading keys -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ImpactKey:
    """The identity of an impact: this leave, this kind of effect, this artifact.

    Shared by the impact, the assessments of who could cover it, and the coverage
    action that answers it.

    >>> from leaveimpact.core.refs import work_item_ref
    >>> from leaveimpact.core.ids import LeaveId, WorkItemId
    >>> ticket = work_item_ref(WorkItemId("ticket_042"))
    >>> ImpactKey(LeaveId("leave_005"), ImpactSubtype.MEETING, ticket)
    Traceback (most recent call last):
    ...
    ValueError: a meeting impact is about an event, got a work_item
    """

    leave_id: LeaveId
    subtype: ImpactSubtype
    artifact: EntityRef

    def __post_init__(self) -> None:
        require_id(EntityKind.LEAVE, self.leave_id)
        allowed = ARTIFACT_KINDS[self.subtype]
        if self.artifact.kind not in allowed:
            raise ValueError(
                f"a {self.subtype.value} impact is about "
                f"{' or '.join(with_article(kind.value) for kind in sorted(allowed))}, "
                f"got {with_article(self.artifact.kind.value)}"
            )


@dataclass(frozen=True, slots=True)
class ConstraintKey:
    """The identity of a constraint: the clause that states it and what it applies to."""

    clause_id: ClauseId
    applies_to: EntityRef

    def __post_init__(self) -> None:
        require_id(EntityKind.CLAUSE, self.clause_id)


@dataclass(frozen=True, slots=True)
class AssessmentKey:
    """The identity of an assessment: a person *for* a need — relational by construction."""

    impact_key: ImpactKey
    employee_id: EmployeeId

    def __post_init__(self) -> None:
        require_id(EntityKind.EMPLOYEE, self.employee_id)


@dataclass(frozen=True, slots=True)
class ConflictKey:
    """The identity of a conflict: an entity *and* a predicate, never two fields that look alike."""

    entity: EntityRef
    predicate: PredicateName

    def __post_init__(self) -> None:
        _require_subject_of(self.predicate, self.entity)


@dataclass(frozen=True, slots=True)
class UnknownKey:
    """The identity of a gap: the subject and the fact about it that could not be established."""

    subject: EntityRef
    required_fact: PredicateName

    def __post_init__(self) -> None:
        _require_subject_of(self.required_fact, self.subject)


GradingKey = ImpactKey | ConstraintKey | AssessmentKey | ConflictKey | UnknownKey
"""Every grading identity; a key is compared only against keys of the same claim type."""


# --- Claims ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaimBase:
    """The fields every claim shares; never accepted by a function — ``Claim`` is.

    ``__post_init__`` puts the order-free repeated fields in canonical order (the shared
    ones here, the subclass's own through ``_canonicalize``), validates the shared fields,
    builds ``key`` so a payload that cannot form its identity fails at construction, then
    runs the subclass's ``_check``. Subclasses implement the two hooks rather than
    chaining ``__post_init__``: a slotted dataclass is a fresh class, and zero-argument
    ``super()`` inside one does not resolve.
    """

    claim_type: ClassVar[ClaimType]

    claim_id: ClaimId
    evidence_refs: tuple[EvidenceRef, ...]
    derived_from_claim_ids: tuple[ClaimId, ...] = ()

    def __post_init__(self) -> None:
        _set_canonical(self, "evidence_refs", self.evidence_refs, _evidence_order)
        _set_canonical(self, "derived_from_claim_ids", self.derived_from_claim_ids, _by_text)
        self._canonicalize()
        _require_claim_id(self.claim_id)
        for other in self.derived_from_claim_ids:
            _require_claim_id(other)
        if len(set(self.derived_from_claim_ids)) != len(self.derived_from_claim_ids):
            raise ValueError(f"{self.claim_id}: a claim is derived from another once, not twice")
        if self.claim_id in self.derived_from_claim_ids:
            raise ValueError(f"{self.claim_id}: a claim cannot be derived from itself")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError(f"{self.claim_id}: an evidence reference is cited once, not twice")
        _ = self.key
        self._check()

    @property
    def key(self) -> GradingKey:
        """The grading identity, computed from the payload."""
        raise NotImplementedError

    @property
    def entity_refs(self) -> tuple[EntityRef, ...]:
        """What the claim is about, derived from the key."""
        raise NotImplementedError

    def _canonicalize(self) -> None:
        """Put the subclass's own order-free repeated fields in canonical order; none here."""

    def _check(self) -> None:
        """The subclass's own payload invariants; the base has none."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Impact(ClaimBase):
    """What the leave affects: a deadline, a meeting, or an obligation of the leaver's."""

    claim_type: ClassVar[ClaimType] = ClaimType.IMPACT

    leave_id: LeaveId
    subtype: ImpactSubtype
    artifact: EntityRef

    @property
    def key(self) -> ImpactKey:
        return ImpactKey(self.leave_id, self.subtype, self.artifact)

    @property
    def entity_refs(self) -> tuple[EntityRef, ...]:
        return (leave_ref(self.leave_id), self.artifact)


@dataclass(frozen=True, slots=True, kw_only=True)
class Constraint(ClaimBase):
    """What a valid response must obey, cited from the clause that states it."""

    claim_type: ClassVar[ClaimType] = ClaimType.CONSTRAINT

    clause_id: ClauseId
    applies_to: EntityRef

    @property
    def key(self) -> ConstraintKey:
        return ConstraintKey(self.clause_id, self.applies_to)

    @property
    def entity_refs(self) -> tuple[EntityRef, ...]:
        return (clause_ref(self.clause_id), self.applies_to)


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateAssessment(ClaimBase):
    """Whether a person could satisfy a need, and why not when not.

    ``reasons`` is non-empty exactly when the verdict is non-viable: a viable person
    has nothing to explain, and an unknown verdict's reason lives in the unknown claim
    it derives from (DESIGN, "the unknowns chain").
    """

    claim_type: ClassVar[ClaimType] = ClaimType.CANDIDATE_ASSESSMENT

    impact_key: ImpactKey
    employee_id: EmployeeId
    verdict: Verdict
    reasons: tuple[AssessmentReason, ...] = ()

    @property
    def key(self) -> AssessmentKey:
        return AssessmentKey(self.impact_key, self.employee_id)

    @property
    def entity_refs(self) -> tuple[EntityRef, ...]:
        return (
            employee_ref(self.employee_id),
            leave_ref(self.impact_key.leave_id),
            self.impact_key.artifact,
        )

    def _canonicalize(self) -> None:
        _set_canonical(self, "reasons", self.reasons, _by_text)

    def _check(self) -> None:
        if len(set(self.reasons)) != len(self.reasons):
            raise ValueError(f"{self.claim_id}: a reason is given once, not twice")
        if self.verdict is Verdict.NON_VIABLE and not self.reasons:
            raise ValueError(f"{self.claim_id}: a non-viable assessment states its reasons")
        if self.verdict is not Verdict.NON_VIABLE and self.reasons:
            raise ValueError(
                f"{self.claim_id}: {with_article(self.verdict.value)} assessment carries no reasons"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceConflict(ClaimBase):
    """Two sources disagree about a fact, and the authority rule resolved it.

    At least two observations from distinct sources, each inside the predicate's
    declared evidence domain; the resolved value is one of the observed ones. Which
    observation *should* win is the authority table's judgement, checked by the rules,
    not here.
    """

    claim_type: ClassVar[ClaimType] = ClaimType.SOURCE_CONFLICT

    entity: EntityRef
    predicate: PredicateName
    observations: tuple[Observation, ...]
    resolved_value: FactValue
    authority_rule: AuthorityRule

    @property
    def key(self) -> ConflictKey:
        return ConflictKey(self.entity, self.predicate)

    @property
    def entity_refs(self) -> tuple[EntityRef, ...]:
        return (self.entity,)

    def _canonicalize(self) -> None:
        _set_canonical(self, "observations", self.observations, _by_source)

    def _check(self) -> None:
        sources = [observation.source for observation in self.observations]
        if len(sources) < 2:
            raise ValueError(f"{self.claim_id}: a conflict needs at least two observations")
        if len(set(sources)) != len(sources):
            raise ValueError(f"{self.claim_id}: a conflict observes each source once")
        domain = predicate(self.predicate).evidence_domain
        outside = sorted(source.value for source in set(sources) - domain)
        if outside:
            raise ValueError(
                f"{self.claim_id}: {', '.join(outside)} is outside the evidence domain of "
                f"{self.predicate.value}"
            )
        if self.resolved_value not in {observation.value for observation in self.observations}:
            raise ValueError(f"{self.claim_id}: the resolved value is one of the observed values")


@dataclass(frozen=True, slots=True, kw_only=True)
class Unknown(ClaimBase):
    """A required fact that could not be established, and why."""

    claim_type: ClassVar[ClaimType] = ClaimType.UNKNOWN

    subject: EntityRef
    required_fact: PredicateName
    reason: UnknownReason

    @property
    def key(self) -> UnknownKey:
        return UnknownKey(self.subject, self.required_fact)

    @property
    def entity_refs(self) -> tuple[EntityRef, ...]:
        return (self.subject,)


@dataclass(frozen=True, slots=True, kw_only=True)
class CoverageAction(ClaimBase):
    """What the plan does about one impact: assign people, declare it uncovered, or declare a limit.

    Assignees are plural because a cardinality clause can require two, and the action
    is unique per impact key so two people cannot be two actions. ``rationale`` is the
    only text the LLM judge reads; it stays outside the key and the deterministic
    checks, and ``None`` is absence, not an empty rationale.
    """

    claim_type: ClassVar[ClaimType] = ClaimType.COVERAGE_ACTION

    impact_key: ImpactKey
    action: CoverageActionKind
    assignee_ids: tuple[EmployeeId, ...] = ()
    rationale: str | None = None

    @property
    def key(self) -> ImpactKey:
        return self.impact_key

    @property
    def entity_refs(self) -> tuple[EntityRef, ...]:
        return (
            leave_ref(self.impact_key.leave_id),
            self.impact_key.artifact,
            *(employee_ref(assignee) for assignee in self.assignee_ids),
        )

    def _canonicalize(self) -> None:
        _set_canonical(self, "assignee_ids", self.assignee_ids, _by_text)

    def _check(self) -> None:
        for assignee in self.assignee_ids:
            require_id(EntityKind.EMPLOYEE, assignee)
        if len(set(self.assignee_ids)) != len(self.assignee_ids):
            raise ValueError(f"{self.claim_id}: an assignee is named once, not twice")
        if self.action is CoverageActionKind.ASSIGN and not self.assignee_ids:
            raise ValueError(f"{self.claim_id}: an assign action names at least one assignee")
        if self.action is not CoverageActionKind.ASSIGN and self.assignee_ids:
            raise ValueError(
                f"{self.claim_id}: {with_article(self.action.value)} action names nobody"
            )
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError(f"{self.claim_id}: a rationale is text or None, never blank")


Claim = Impact | Constraint | CandidateAssessment | SourceConflict | Unknown | CoverageAction
"""The vocabulary as a union: what functions accept, so a ``match`` can be exhaustive."""


# --- The claim set ----------------------------------------------------------------


def structural_problems(claims: Sequence[Claim]) -> tuple[str, ...]:
    """Every structural defect of ``claims`` as a report, empty when the set is well-formed.

    A report, not an exception, because a malformed agent report is a graded outcome
    the evaluator records rather than a crash; ``require_well_formed`` is the raising
    form for code paths that must not continue. Checked: claim ids unique, every
    ``derived_from`` id resolves to a claim in the set, the provenance graph is acyclic,
    and no two claims of one type share a grading key.

    >>> from leaveimpact.core.ids import ClaimId, ClauseId, WorkItemId
    >>> from leaveimpact.core.refs import work_item_ref
    >>> a = Constraint(claim_id=ClaimId("claim_001"), evidence_refs=(),
    ...                clause_id=ClauseId("clause_011"),
    ...                applies_to=work_item_ref(WorkItemId("ticket_042")),
    ...                derived_from_claim_ids=(ClaimId("claim_002"),))
    >>> structural_problems((a,))
    ('claim_001 is derived from claim_002, which is not in the set',)
    """
    problems: list[str] = []
    by_id: dict[ClaimId, Claim] = {}
    for claim in claims:
        if claim.claim_id in by_id:
            problems.append(f"{claim.claim_id} is used by two claims")
        by_id.setdefault(claim.claim_id, claim)
    for claim in claims:
        for other in claim.derived_from_claim_ids:
            if other not in by_id:
                problems.append(
                    f"{claim.claim_id} is derived from {other}, which is not in the set"
                )
    problems.extend(_provenance_cycles(by_id))
    seen: dict[tuple[ClaimType, GradingKey], ClaimId] = {}
    for claim in claims:
        identity = (claim.claim_type, claim.key)
        if identity in seen:
            problems.append(
                f"{claim.claim_id} and {seen[identity]} are two {claim.claim_type.value} "
                f"claims with one grading key"
            )
        seen.setdefault(identity, claim.claim_id)
    return tuple(problems)


def _provenance_cycles(by_id: Mapping[ClaimId, Claim]) -> list[str]:
    """One message per cycle found walking ``derived_from`` edges that resolve."""
    messages: list[str] = []
    finished: set[ClaimId] = set()
    for start in by_id:
        if start in finished:
            continue
        path: list[ClaimId] = []
        on_path: set[ClaimId] = set()
        stack: list[tuple[ClaimId, int]] = [(start, 0)]
        while stack:
            current, next_edge = stack[-1]
            if next_edge == 0:
                path.append(current)
                on_path.add(current)
            edges = [other for other in by_id[current].derived_from_claim_ids if other in by_id]
            if next_edge < len(edges):
                stack[-1] = (current, next_edge + 1)
                other = edges[next_edge]
                if other in on_path:
                    cycle = path[path.index(other) :] + [other]
                    messages.append(f"provenance cycle: {' -> '.join(cycle)}")
                elif other not in finished:
                    stack.append((other, 0))
                continue
            stack.pop()
            path.pop()
            on_path.discard(current)
            finished.add(current)
    return messages


def require_well_formed(claims: Sequence[Claim]) -> None:
    """Raise ``ValueError`` listing every structural problem of ``claims``; return on none."""
    problems = structural_problems(claims)
    if problems:
        raise ValueError("the claim set is not well-formed:\n  " + "\n  ".join(problems))
