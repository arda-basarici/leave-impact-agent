"""The fragmented tier's scenario classes: at least one answer-changing fact needs synthesis
beyond structured fields.

Tier 2 tests whether an investigator reads what the structured fields do not say (DESIGN,
"The first golden set"; the class shapes under the step 15 rulings). ``free_text_qualification``
is the first: a release meeting the leaver attends falls inside the leave under a
scenario-owned policy clause that requires a skill, and the one person authored viable
holds that skill nowhere on the HR record — it is evidenced solely in a comment they wrote
on their own ticket, a part a model writes under a brief. A second candidate whose record
lacks the skill and who wrote no such comment is authored non-viable for the skill
criterion, so the assessment rows carry the contrast and not only the discovery. The
policy stays template-written and names the meeting it applies to, so the constraint's
target and the text's scope agree by construction and no other scenario's artifact falls
inside it (constraint-bearing documents are scenario-owned in M1).

The shape is symmetric with the responsibility class to come: there the obligation is in
prose and the qualifications structured, here the impact is structured and the
qualification in prose, so a score gap between the two localizes to which fact a model
wrote. The roles are a query over the static organization in canonical order: a skill some
record holds, a cover whose record lacks it and who belongs to a component (their ticket
lives there), the first other record-holder lacking it, and the first leaver outside the
skill's holders and the two candidates, so a concurrent leave on the cover still leaves
the outcome assign. Titles and the clause are templates over the vocabulary's forms, which
the scanner knows; only the comment is paid for.
"""

from __future__ import annotations

from collections.abc import Mapping
from random import Random
from types import MappingProxyType

from leaveimpact.core.claims import (
    AssessmentReason,
    ConstraintKey,
    CoverageActionKind,
    ImpactKey,
    ImpactSubtype,
    Verdict,
)
from leaveimpact.core.entities import Component, Document, DocumentSection, Employee, Team
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import SkillId
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import (
    EvidenceRef,
    clause_ref,
    comment_ref,
    component_ref,
    employee_ref,
    event_ref,
    work_item_ref,
)
from leaveimpact.core.values import Requirement, SkillCriterion
from leaveimpact.world.briefs import CommentTarget, PendingProse
from leaveimpact.world.construction import Construction, Draft, Frame, ScenarioClass
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    ExpectedImpact,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    Tier,
)
from leaveimpact.world.structured import plant_leave, plant_meeting, plant_ticket
from leaveimpact.world.vocabulary import SKILLS

POLICY_TITLE = "Release policy: {meeting}"
POLICY_CLAUSE = "The {meeting} needs an engineer with {skill} experience."
"""The scenario-owned clause, template-written: it names the meeting it applies to."""

SKILL_NAMES: Mapping[SkillId, str] = MappingProxyType({skill.id: skill.name for skill in SKILLS})


class FreeTextQualification:
    """A meeting under a skill clause; the viable cover's skill lives only in a ticket comment."""

    name = ScenarioClassName.FREE_TEXT_QUALIFICATION
    tier = Tier.FRAGMENTED
    affordance = (
        "a skill some record holds, a cover in a component whose record lacks it, another "
        "record-holder lacking it, and a leaver outside the skill's holders"
    )

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        return tuple(
            _qualification_construction(org, *roles) for roles in _qualification_roles(org)
        )


FRAGMENTED_CLASSES: Mapping[ScenarioClassName, ScenarioClass] = MappingProxyType(
    {ScenarioClassName.FREE_TEXT_QUALIFICATION: FreeTextQualification()}
)
"""The fragmented classes built so far, by name."""


# --- Role selection ---------------------------------------------------------------------


def _qualification_roles(
    org: OrgSpec,
) -> list[tuple[SkillId, Employee, Component, Employee, Employee, Team]]:
    """(skill, cover, the cover's component, other candidate, leaver, the leaver's team), in
    canonical order."""
    roles: list[tuple[SkillId, Employee, Component, Employee, Employee, Team]] = []
    teams = {team.id: team for team in org.teams}
    for skill in org.skills:
        holders = {employee.id for employee in org.holders_of(skill)}
        if not holders:
            continue
        lacking = [e for e in org.employees if e.skills is not None and e.id not in holders]
        for cover in lacking:
            component = next((c for c in org.components if cover.id in c.member_ids), None)
            if component is None:
                continue
            other = next((e for e in lacking if e.id != cover.id), None)
            leaver = next(
                (
                    e
                    for e in org.employees
                    if e.id not in holders and e.id not in (cover.id, other and other.id)
                ),
                None,
            )
            if other is None or leaver is None:
                continue
            roles.append((skill, cover, component, other, leaver, teams[leaver.team_id]))
    return roles


# --- The construction --------------------------------------------------------------------


def _qualification_construction(
    org: OrgSpec,
    skill: SkillId,
    cover: Employee,
    component: Component,
    other: Employee,
    leaver: Employee,
    team: Team,
) -> Construction:
    outside = tuple(employee for employee in org.employees if employee.team_id != team.id)

    def plant(frame: Frame, rng: Random) -> Draft:
        visible = frame.window.start
        leave = plant_leave(frame, leaver)
        meeting = plant_meeting(frame, rng, team, leaver, outside)
        clause = frame.ids.clause()
        policy = Document(
            frame.ids.document(),
            POLICY_TITLE.format(meeting=meeting.entity.title),
            DocumentKind.POLICY,
            visible,
            (
                DocumentSection(
                    clause,
                    POLICY_CLAUSE.format(meeting=meeting.entity.title, skill=SKILL_NAMES[skill]),
                ),
            ),
        )
        requires = Fact(
            clause_ref(clause),
            PredicateName.REQUIRES,
            Requirement(1, (SkillCriterion(skill),)),
            EvidenceRef(Source.CORPUS, clause_ref(clause)),
            visible,
        )
        ticket = plant_ticket(frame, rng, component, cover)
        comment = frame.ids.comment()
        evidenced = Fact(
            employee_ref(cover.id),
            PredicateName.HAS_SKILL,
            skill,
            EvidenceRef(Source.JIRA, comment_ref(comment)),
            visible,
        )
        # The ticket is the author's own, and a comment on one's own ticket says so: allowed,
        # so the checker's reading of "my ticket" matches a fact of the world (the third
        # measurement world refused every attempt on exactly that reading, 2026-09-14).
        owns = Fact(
            work_item_ref(ticket.entity.id),
            PredicateName.OWNS_WORK_ITEM,
            employee_ref(cover.id),
            EvidenceRef(Source.JIRA, work_item_ref(ticket.entity.id), "owner_id"),
            visible,
        )
        # The ticket's component, so the remark has something true to be about besides the
        # required skill (the fourth measurement world padded with offers, 2026-09-14).
        in_component = Fact(
            work_item_ref(ticket.entity.id),
            PredicateName.IN_COMPONENT,
            component_ref(component.id),
            EvidenceRef(Source.JIRA, work_item_ref(ticket.entity.id), "component_id"),
            visible,
        )
        impact = ImpactKey(leave.entity.id, ImpactSubtype.MEETING, event_ref(meeting.entity.id))
        expected = ExpectedImpact(
            impact,
            CoverageActionKind.ASSIGN,
            (
                AuthoredVerdict(cover.id, Verdict.VIABLE),
                AuthoredVerdict(other.id, Verdict.NON_VIABLE, (AssessmentReason.SKILL,)),
            ),
        )
        owned = OwnedEntities(
            leaves=(leave,),
            work_items=(ticket,),
            events=(meeting,),
            documents=(Planted(policy, visible),),
        )
        return Draft(
            owned,
            leave.entity.id,
            (expected,),
            constraints=(ConstraintKey(clause, event_ref(meeting.entity.id)),),
            authored_facts=(requires, evidenced),
            pending=(
                PendingProse(
                    CommentTarget(comment, ticket.entity.id, 0, visible, cover.id),
                    (evidenced,),
                    allowed=(owns, in_component),
                ),
            ),
        )

    return plant


__all__ = [
    "FRAGMENTED_CLASSES",
    "POLICY_CLAUSE",
    "POLICY_TITLE",
    "FreeTextQualification",
]
