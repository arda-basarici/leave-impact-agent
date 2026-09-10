"""The structured tier's scenario classes: every answer-relevant fact sits in a structured field.

Tier 1 tests tool use, temporal filtering, joins across systems and the deterministic
candidate check, with no prose to read (DESIGN, "The first golden set"). This module
holds the first class, ``structured_deadline``, pulled forward from the Tier 1 step as
the acceptance proof of the construction framework; the meeting and mixed classes join
it at that step.

A class here is deliberately the smallest real thing: no policy clause, no prose, no
conflict, no planted unknown. Its near-misses are structural. A fellow member of the
ticket's component is the obvious cover and is authored viable; a teammate of the leaver
who is not in that component is authored non-viable for the component criterion — the
"same team against relevant component" trap the world's shape section names, gradable
because the key says why the teammate fails. Anything that makes the cover harder (a
concurrent leave, a resolved look-alike ticket) is a modifier's business, so the class
stays orthogonal to them.

Ticket titles are templates, not vocabulary: structured-shaped text the generator writes
from a fixed phrase and the component's name, exactly as DESIGN says nothing is learned
from paying a model for "Release planning — Payments API".
"""

from __future__ import annotations

from datetime import timedelta
from random import Random

from leaveimpact.core.claims import (
    AssessmentReason,
    CoverageActionKind,
    ImpactKey,
    ImpactSubtype,
    Verdict,
)
from leaveimpact.core.entities import Component, Employee, Leave, WorkItem
from leaveimpact.core.enums import LeaveKind, LeaveStatus, WorkItemStatus
from leaveimpact.core.refs import work_item_ref
from leaveimpact.world.construction import Construction, Draft, Frame
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    ExpectedImpact,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    Tier,
)

TICKET_TITLES: tuple[str, ...] = (
    "{component}: upgrade the client library",
    "{component}: rotate the signing keys",
    "{component}: migrate the retry queue",
    "{component}: close the audit findings",
    "{component}: cut over to the new gateway",
)


class StructuredDeadline:
    """A ticket the leaver owns falls due during the leave; who in its component can take it over?

    Admissible constructions, in canonical order: for each component (org order), for
    each member as leaver (id order), for each other member as the viable cover (id
    order), with the first teammate of the leaver outside the component as the
    structural near-miss. The organization affords the class whenever some component
    holds two people one of whom has a teammate outside it — an org without that shape
    fails by name.
    """

    name = ScenarioClassName.STRUCTURED_DEADLINE
    tier = Tier.STRUCTURED
    affordance = "a component with two members, one of whom has a teammate outside the component"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        by_id = {employee.id: employee for employee in org.employees}
        constructions: list[Construction] = []
        for component in org.components:
            members = set(component.member_ids)
            for leaver_id in component.member_ids:
                leaver = by_id[leaver_id]
                outsiders = [
                    teammate
                    for teammate in org.members_of(leaver.team_id)
                    if teammate.id not in members
                ]
                if not outsiders:
                    continue
                for cover_id in component.member_ids:
                    if cover_id != leaver_id:
                        constructions.append(
                            _construction(component, leaver, by_id[cover_id], outsiders[0])
                        )
        return tuple(constructions)


def _construction(
    component: Component, leaver: Employee, cover: Employee, outsider: Employee
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        visible = frame.window.start
        leave = Leave(
            frame.ids.leave(),
            leaver.id,
            frame.leave.start,
            frame.leave.end,
            LeaveKind.ANNUAL,
            LeaveStatus.APPROVED,
        )
        due = frame.leave.start + timedelta(days=rng.randrange(frame.leave.days))
        ticket = WorkItem(
            id=frame.ids.work_item(),
            title=rng.choice(TICKET_TITLES).format(component=component.name),
            owner_id=leaver.id,
            status=WorkItemStatus.IN_PROGRESS,
            component_id=component.id,
            opened_on=visible,
            resolved_on=None,
            due_on=due,
            comments=(),
        )
        impact = ImpactKey(leave.id, ImpactSubtype.DEADLINE, work_item_ref(ticket.id))
        must_assess = (
            AuthoredVerdict(cover.id, Verdict.VIABLE),
            AuthoredVerdict(outsider.id, Verdict.NON_VIABLE, (AssessmentReason.COMPONENT,)),
        )
        owned = OwnedEntities(
            leaves=(Planted(leave, visible),),
            work_items=(Planted(ticket, visible),),
        )
        expected = ExpectedImpact(impact, CoverageActionKind.ASSIGN, must_assess)
        return Draft(owned, leave.id, (expected,))

    return plant
