"""The adversarial tier's scenario classes: the correct output depends on reasoning about the
evidence itself.

Tier 3 tests whether an investigator resolves what the sources say against each other, and
concludes a limit where the world holds one (DESIGN, "The first golden set"; the class shapes
under the step 15 rulings, the 15.5 interview). ``stale_source_conflict`` is the first: the
tracker gives the leaver a release ticket due inside the leave, and a runbook section a model
writes names the leaver's teammate outside the component as the ticket's owner. The cast is
the structured deadline class's, unchanged: the same viable cover inside the component, the
same outsider authored non-viable by component. What the section adds is one fact of the
corpus contradicting the tracker on a single-valued predicate, so the rules derive a conflict
resolved to the system of record, the impact stays grounded on the tracker's owner, and the
key seals the conflict as expected (``ScenarioKey.expected_conflicts``). The failure the class
catches is an investigator who believes the document: one that drops the impact, or hands
cover to the named owner, whose component verdict the key already grades, without assessing
them. The outsider is the stale owner and not a component member on purpose, since a viable
stale owner would let a believing agent produce a correct-looking plan and leave the
conflict claim as the only separation.

The section carries the one required fact and nothing else the benchmark could read: the
contract already refuses a cross-source fact as context, and this class allows none, so the
section narrates the on-call routine and asserts one proposition. The required fact is
answer-changing through the conflict alone (the fact moves no verdict and no outcome), which
is what the key's expected conflicts made derivable; without them the ablation would have
called the section context, a construction error for a prose class. Required sources are the
record for the leave, the tracker for the impact and the corpus for the conflict, since the
conflict vanishes under a corpus outage and a tracker outage leaves ownership unknown with the
document not promoted (the authority ruling).

The runbook is titled by the release ticket it is about, a title the world's book mints once
per component, so two conflict rows in one component never share a runbook title and the
checker's entity list holds one document per name. No reservation-book rule is added for the
stale owner: the ticket is due inside this slice, its resolved owner is the leaver, and the
evidence scope of expected conflicts keeps the standing runbook off other rows' keys; the
two-hundred-seed sweep is the oracle for any interaction the book does not know (the 15.4
ruling's own sentence).
"""

from __future__ import annotations

from collections.abc import Mapping
from random import Random
from types import MappingProxyType

from leaveimpact.core.claims import AuthorityRule
from leaveimpact.core.entities import Component, Document, Employee
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.facts import Fact
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EvidenceRef, clause_ref, employee_ref, work_item_ref
from leaveimpact.world.briefs import PendingProse, SectionTarget
from leaveimpact.world.construction import Construction, Draft, Frame, ScenarioClass
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    ExpectedConflict,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    Tier,
)
from leaveimpact.world.structured import (
    StructuredDeadline,
    deadline_impact,
    deadline_roles,
    plant_leave,
    plant_ticket,
)

RUNBOOK_TITLE = "Release runbook: {release}"
"""The stale runbook's title, scoped to the release ticket it names an owner for."""


class StaleSourceConflict:
    """A runbook names a stale owner for the leaver's release ticket; the tracker is the record.

    The deadline cast (a component, its leaver, a viable cover inside it, a teammate outside
    it) plus one runbook section a model writes, stating that the outsider owns the ticket.
    Authored: the cover viable, the outsider non-viable by component, the outcome assign; the
    class asserts the one conflict its section plants, resolved to the leaver under the
    system-of-record rule, and construction refuses the scenario if the rules derive
    anything else. Admissible wherever the deadline class is, in the same canonical order.
    """

    name = ScenarioClassName.STALE_SOURCE_CONFLICT
    tier = Tier.ADVERSARIAL
    affordance = StructuredDeadline.affordance

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        return tuple(_conflict_construction(*roles) for roles in deadline_roles(org))


ADVERSARIAL_CLASSES: Mapping[ScenarioClassName, ScenarioClass] = MappingProxyType(
    {ScenarioClassName.STALE_SOURCE_CONFLICT: StaleSourceConflict()}
)
"""The adversarial classes built so far, by name; ``classes.SCENARIO_CLASSES`` joins every tier."""


def _conflict_construction(
    component: Component, leaver: Employee, cover: Employee, outsider: Employee
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        visible = frame.window.start
        leave = plant_leave(frame, leaver)
        ticket = plant_ticket(frame, rng, component, leaver)
        section = frame.ids.clause()
        # The runbook's sections are empty here: the section is the model's, filled in at
        # materialization at the pending target's position (as the account note's is).
        runbook = Document(
            frame.ids.document(),
            RUNBOOK_TITLE.format(release=ticket.entity.title),
            DocumentKind.RUNBOOK,
            visible,
            (),
        )
        stale = Fact(
            work_item_ref(ticket.entity.id),
            PredicateName.OWNS_WORK_ITEM,
            employee_ref(outsider.id),
            EvidenceRef(Source.CORPUS, clause_ref(section)),
            visible,
        )
        owned = OwnedEntities(
            leaves=(leave,), work_items=(ticket,), documents=(Planted(runbook, visible),)
        )
        return Draft(
            owned,
            leave.entity.id,
            (deadline_impact(leave, ticket, cover, outsider),),
            authored_facts=(stale,),
            pending=(PendingProse(SectionTarget(section, runbook.id, 0), (stale,)),),
            required_conflicts=(
                ExpectedConflict(
                    work_item_ref(ticket.entity.id),
                    PredicateName.OWNS_WORK_ITEM,
                    employee_ref(leaver.id),
                    AuthorityRule.SYSTEM_OF_RECORD_WINS,
                ),
            ),
        )

    return plant


__all__ = ["ADVERSARIAL_CLASSES", "RUNBOOK_TITLE", "StaleSourceConflict"]
