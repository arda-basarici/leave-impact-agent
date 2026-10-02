"""Retrieval targets: the statements of prose a scenario's answer depends on under a condition,
and what each one moves.

Some of what the rules conclude rests on facts only prose carries: what a clause requires,
whom a runbook names, a skill a ticket comment shows. Whether a run found that prose is the
retrieval question, and it needs a definition of "that prose" which is neither a guess nor
a label somebody wrote. Here it is derived (the investigator milestone's fourth build
step, ruling 5): a statement is a *target* of a scenario under a condition when the
oracle's answer there changes with the statement removed from the world, on every carrier
that states it. The answer is the oracle's own, the removal the oracle's own
(``answer_without``), and the comparison is over everything a report is graded on: the
impacts, the constraints, every organization member's verdict and reasons, each outcome,
the conflicts, the unknowns.

The unit is the statement and not the carrier. Two comments can show one skill; a run that
read either read the statement, and removing one comment alone moves nothing while the
other stands. The carriers are kept as the alternatives a read can return.

Candidates are every statement of the world, not only the ones the scenario's own
construction planted. A skill another scenario plants for a colleague is in the systems
when this one runs and changes that colleague's verdict here. Such a target moves rows no
report is required to state, a candidate outside the probe set, so each moved key says
whether the oracle requires it, and a table can count the targets that move a required
row apart from the rest without deriving anything again.

*What a target moves* is the set of claim keys whose expectation differs between the two
answers: a key the answer holds and the reduced one does not, the reverse, or one whose
payload differs. It is what lets a missed or a wrong row be traced to a statement the run
did or did not retrieve. A key only the reduced answer holds is what a run that missed the
statement would be led to report; the oracle does not require it, and it is recorded as
not required.

Targets are a property of the sealed world, the scenario and the condition, never of a
run, and are never read off the sealed role tags: those were derived for model-written
text only and under the dated view, and a class-written requirement clause carries none.
Under a condition with no answer there are no targets to speak of, which is a different
statement from an empty set, so the function takes an answer. A statement carried only
where the condition cannot read is no target there: removing what could not be read moves
nothing.

A removal the rules cannot read is a defect of the sealed world against today's rules and
is refused whole, with no sealed content in the refusal.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.claims import (
    AssessmentKey,
    ClaimType,
    ConflictKey,
    GradingKey,
    UnknownKey,
)
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.refs import SOURCE_BY_TARGET_KIND, EntityRef
from leaveimpact.evaluator.matching import required_unknowns
from leaveimpact.evaluator.oracle import Answerable, answer_without
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.world_index import Statement

_Stated = dict[tuple[ClaimType, GradingKey], tuple[object, bool]]
"""An answer as a report is graded on it: each claim key with its payload and whether the
oracle requires a report to hold it."""


class TargetsNotDerivable(Exception):
    """The rules could not read the world with a statement removed: a defect of the sealed
    world against today's rules, never of a run.

    The message names the scenario and a count. ``detail`` holds the rules' own reasons,
    which name what the sealed files hold: for a privileged reader to ask for, never
    printed with the exception, which is raised with no cause and no context.
    """

    def __init__(self, scenario_id: ScenarioId, removals: int, *, detail: str) -> None:
        super().__init__(
            f"{scenario_id}: the rules could not read the world with a statement removed, "
            f"for {removals} statement(s); no retrieval target is derived for a world the "
            "rules refuse"
        )
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Carrier:
    """Where a statement is written: the comment or the section, and the ticket or the document
    a read returns it inside. ``record`` is the carrier itself when a record carries it."""

    part: EntityRef
    record: EntityRef

    @property
    def source(self) -> Source:
        """The one source that holds the carrier."""
        return SOURCE_BY_TARGET_KIND[self.part.kind]


@dataclass(frozen=True, slots=True)
class MovedKey:
    """One claim key whose expectation a statement's removal changes, and whether the oracle
    requires a report to hold it."""

    claim_type: ClaimType
    key: GradingKey
    required: bool


@dataclass(frozen=True, slots=True)
class RetrievalTarget:
    """A statement the answer depends on: where it is written and what it moves.

    ``carriers`` are alternatives in reference order, any one of them stating it. ``moves``
    is never empty: it is what makes the statement a target.
    """

    statement: Statement
    carriers: tuple[Carrier, ...]
    moves: tuple[MovedKey, ...]

    @property
    def moves_a_required_key(self) -> bool:
        """Whether a row every report must hold depends on this statement."""
        return any(moved.required for moved in self.moves)


def retrieval_targets(world: SealedWorld, answer: Answerable) -> tuple[RetrievalTarget, ...]:
    """The statements ``answer`` depends on, in the world index's order.

    ``answer`` is the oracle's for its scenario and condition. Raises
    ``TargetsNotDerivable`` when a removal cannot be read by the rules.
    """
    stated = _stated(answer)
    targets: list[RetrievalTarget] = []
    refused: list[str] = []
    for statement, carriers in world.index.statements.items():
        try:
            reduced = answer_without(world, answer.scenario, answer.condition, statement)
        except ValueError as problem:
            refused.append(str(problem))
            continue
        if not isinstance(reduced, Answerable):
            # Prose holds neither the leave nor a source's reachability; an answer cannot
            # stop existing by its removal.
            refused.append("the reduced world has no answer")
            continue
        moves = _moved(stated, _stated(reduced))
        if moves:
            targets.append(
                RetrievalTarget(
                    statement,
                    tuple(
                        Carrier(
                            part, held.parent if (held := world.index.parts.get(part)) else part
                        )
                        for part in carriers
                    ),
                    moves,
                )
            )
    if refused:
        # Raised here, after every handler has ended: the rules' reasons name sealed ids and
        # a traceback prints a whole chain.
        raise TargetsNotDerivable(answer.scenario.spec.id, len(refused), detail="; ".join(refused))
    return tuple(targets)


def _stated(answer: Answerable) -> _Stated:
    """``answer`` as claim keys, each with its payload and whether a report must hold it: the
    expectations the matching grades a report against, and the optional ones beside them."""
    stated: _Stated = {}
    for truth in answer.impacts:
        stated[(ClaimType.IMPACT, truth.key)] = (None, True)
        stated[(ClaimType.COVERAGE_ACTION, truth.key)] = (truth.outcome, True)
        for assessment in truth.assessments:
            key = AssessmentKey(truth.key, assessment.employee_id)
            stated[(ClaimType.CANDIDATE_ASSESSMENT, key)] = (
                (assessment.verdict, assessment.reasons),
                assessment.employee_id in truth.probe,
            )
    for constraint in answer.constraints:
        stated[(ClaimType.CONSTRAINT, constraint)] = (None, True)
    for conflict in answer.conflicts:
        key = ConflictKey(conflict.entity, conflict.predicate)
        stated[(ClaimType.SOURCE_CONFLICT, key)] = (
            (conflict.resolved_value, conflict.authority_rule),
            True,
        )
    required = required_unknowns(answer)
    for unknown in answer.unknowns:
        key = UnknownKey(unknown.subject, unknown.required_fact)
        stated[(ClaimType.UNKNOWN, key)] = (unknown.reason, key in required)
    return stated


def _moved(stated: _Stated, reduced: _Stated) -> tuple[MovedKey, ...]:
    """The keys whose expectation differs between the answer and the reduced one, the answer's
    first and in its order. Whether a key is required is the answer's to say."""
    moved: list[MovedKey] = []
    for (claim_type, key), (payload, required) in stated.items():
        other = reduced.get((claim_type, key))
        if other is None or other[0] != payload:
            moved.append(MovedKey(claim_type, key, required))
    moved.extend(
        MovedKey(claim_type, key, False)
        for claim_type, key in reduced
        if (claim_type, key) not in stated
    )
    return tuple(moved)


__all__ = [
    "Carrier",
    "MovedKey",
    "RetrievalTarget",
    "TargetsNotDerivable",
    "retrieval_targets",
]
