"""The composer: from a run's reads and the facts a model stated to the claims the rules write.

Every system whose claims the rules write shares this one path (the contract step's
rulings, and the composer group's eight points). A model states facts with the words it
read them from; no model writes a verdict. The baseline is the same path with no statement.

What composing does, in order:

1. *The join.* The admitted statements enter the structured projection of the reads
   (``core.stated_view``), which leaves out the readings that cannot stand together.
2. *The binding and the scope rules.* Each requirement still standing has its span bound
   once, over everything the run read, and the placements are scoped (``core.scoping``):
   one constraint per clause whose spans placed on one artifact, none for a clause read
   with two scopes or bound to a document without exactly one section. Those requirements
   are withheld, and the view is the join without them.
3. *The rules.* The impacts the view grounds for the leaver over the leave's span, and
   ``core``'s composing pass over them with every composed constraint, as an oracle is
   given every sealed one; the rules select by the need.
4. *The report.* The reporting policy's claims, a constraint stated only where its target
   lies in a reported impact's scope (``report``).
5. *The composition.* Who composed and under which policy, every placement, every
   exclusion: what an export records and a review shows beside the claims.

Admission is not here. A statement was admitted or refused when the answer that carried it
was recorded, over the reads logged before it (``core.admission``); composing takes the
admitted ones as given, in emission order. Nor are the run's preconditions: whether the
attempt failed by defect or abstains is decided before anything is composed.

*The composing policy* names what decides a composed report: a version kept by hand and
raised whenever the same reads and statements would compose a different report, the
reporting policy's three declared values, the predicates a model may state, the anchor
table's digest, the binding rule, the exclusion reasons, the scope rules and the rule for
which constraints are stated. Its digest is of that specification in canonical JSON. One
policy for every rules-composed system, the baseline included; the preregistration binds
it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from leaveimpact.agent.report import REPORTING_POLICY, compose_report
from leaveimpact.core.anchors import anchor_table_digest
from leaveimpact.core.claims import Claim
from leaveimpact.core.entities import Leave
from leaveimpact.core.facts import FactView
from leaveimpact.core.grounding import derive_impacts
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.read_projection import StructuredReads
from leaveimpact.core.readings import conclude_impacts
from leaveimpact.core.run_ending import ClaimAuthor, ComposingPolicy, Composition
from leaveimpact.core.scoping import scope_requirements
from leaveimpact.core.stated import STATED_PREDICATES, StatedFact
from leaveimpact.core.stated_view import Exclusion, view_with_stated
from leaveimpact.core.worldtime import RunContext

COMPOSER = "rules-composer"
"""The composing policy's identifier."""

COMPOSER_VERSION = 1
"""Kept by hand: raised whenever the same reads and statements would compose another report."""


def composing_specification() -> JsonObject:
    """The composing policy as data: everything that decides a composed report, by value or
    by name."""
    return {
        "identifier": COMPOSER,
        "version": COMPOSER_VERSION,
        "reporting": {
            "identifier": REPORTING_POLICY.identifier,
            "version": REPORTING_POLICY.version,
            "tie_break": REPORTING_POLICY.tie_break,
        },
        "stated_predicates": [name.value for name in STATED_PREDICATES],
        "anchor_table": anchor_table_digest(),
        "binding": "exact_title_equality_with_longer_title_guard",
        "exclusions": [reason.value for reason in Exclusion],
        "scope": ["one_target_per_clause", "a_document_means_its_one_section"],
        "stated_constraints": "target_in_the_scope_of_a_reported_impact",
    }


def composing_policy() -> ComposingPolicy:
    """The policy every rules-composed claim set records: the identifier and the digest of
    the specification.

    >>> composing_policy().identifier
    'rules-composer'
    """
    digest = hashlib.sha256(canonical_bytes(composing_specification())).hexdigest()
    return ComposingPolicy(COMPOSER, digest)


def rules_only_composition() -> Composition:
    """How a run with no stated fact was composed, as its export states it: by the rules,
    under the composing policy, with nothing placed and nothing left out. The baseline's
    composition, and that of any run that failed or abstained before composing."""
    return Composition(ClaimAuthor.RULES, composing_policy(), (), ())


@dataclass(frozen=True, slots=True)
class Composed:
    """What composing gave: the claims, how they were composed, and the view the rules were
    asked over."""

    claims: tuple[Claim, ...]
    composition: Composition
    view: FactView


def compose(
    reads: StructuredReads,
    admitted: Sequence[StatedFact],
    context: RunContext,
    leave: Leave,
    universe: Sequence[EmployeeId],
) -> Composed:
    """The claims of a run that read ``reads`` and admitted ``admitted``, for ``leave`` over
    the candidates ``universe``.

    ``admitted`` are the statements the gates let in, in emission order. Raises nothing
    for what a model stated; ``ValueError`` for a report the policy cannot state, a defect
    of the harness.
    """
    joined = view_with_stated(reads, admitted)
    scoped = scope_requirements(
        reads, (s for s in joined.included if s.predicate is PredicateName.REQUIRES)
    )
    if scoped.withheld:
        joined = view_with_stated(
            reads, admitted, {excluded.fact: excluded.reason for excluded in scoped.withheld}
        )
    view = joined.view
    grounded = derive_impacts(
        view, context.leave_id, leave.employee_id, leave.span, context.reference_timezone
    ).grounded
    conclusions = conclude_impacts(
        view,
        grounded,
        scoped.constraints,
        leave.employee_id,
        leave.span,
        context.reference_timezone,
        universe,
    )
    claims = compose_report(conclusions, view, scoped.constraints)
    composition = Composition(
        ClaimAuthor.RULES, composing_policy(), scoped.placements, joined.excluded
    )
    return Composed(claims, composition, view)


__all__ = [
    "COMPOSER",
    "COMPOSER_VERSION",
    "Composed",
    "compose",
    "composing_policy",
    "composing_specification",
    "rules_only_composition",
]
