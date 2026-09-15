"""Briefs: a pending target completed by the framework — register from the target, namespace
from the facts with the parent's title and the author's name added, roles as derived — and the
pre-compose contract: one carrier per prose-authored fact, a brief's required facts exactly the
authored facts naming its target, a pending target absent from the records under a parent the
scenario owns at a position the order can hold, an allowed fact a fact of the world."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core import (
    Comment,
    Document,
    DocumentKind,
    DocumentSection,
    EvidenceRef,
    Fact,
    FactBase,
    PredicateName,
    Requirement,
    SkillCriterion,
    Source,
    WorkItem,
    WorkItemStatus,
    clause_ref,
    comment_ref,
    component_ref,
    employee_ref,
    work_item_ref,
)
from leaveimpact.core.ids import clause_id, comment_id, document_id, skill_id, work_item_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Brief,
    CommentTarget,
    FactRole,
    PendingProse,
    ProseContractError,
    Register,
    SectionTarget,
    brief_for,
    check_allowed,
    check_pending,
    generate_org,
    lexicon_of,
    target_ref,
)
from leaveimpact.world.prose import SKILL_KIND

ORG = generate_org(7, DEFAULT_PARAMS)
DAY = date(2026, 3, 1)
KAFKA = skill_id("kafka")
AUTHOR = ORG.employees[0]
CANDIDATE = ORG.employees[1]
TICKET = WorkItem(
    work_item_id(1),
    "Payments API: rotate the signing keys",
    AUTHOR.id,
    WorkItemStatus.IN_PROGRESS,
    ORG.components[0].id,
    DAY,
    None,
    None,
    (),
)
RUNBOOK = Document(document_id(1), "Payments on-call runbook", DocumentKind.RUNBOOK, DAY, ())
COMMENT = CommentTarget(comment_id(1), TICKET.id, 0, DAY, AUTHOR.id)
SECTION = SectionTarget(clause_id(1), RUNBOOK.id, 0)
LEXICON = lexicon_of(ORG, [TICKET], [RUNBOOK])


def carried_by(target: CommentTarget | SectionTarget, skill: str = KAFKA) -> Fact:
    """A fact a text on ``target`` carries: a skill in a comment, an ownership in a section —
    the registry's evidence domains decide which source may evidence which."""
    if isinstance(target, CommentTarget):
        return Fact(
            employee_ref(CANDIDATE.id),
            PredicateName.HAS_SKILL,
            skill,
            EvidenceRef(Source.JIRA, target_ref(target)),
            DAY,
        )
    return Fact(
        work_item_ref(TICKET.id),
        PredicateName.OWNS_WORK_ITEM,
        employee_ref(CANDIDATE.id),
        EvidenceRef(Source.CORPUS, target_ref(target)),
        DAY,
    )


# --- Targets and pending prose ----------------------------------------------------------


def test_a_target_names_its_evidence_reference_and_refuses_a_negative_position() -> None:
    assert target_ref(COMMENT) == comment_ref(comment_id(1))
    assert target_ref(SECTION) == clause_ref(clause_id(1))
    with pytest.raises(ValueError, match="a position is non-negative"):
        CommentTarget(comment_id(2), TICKET.id, -1, DAY, AUTHOR.id)


def test_a_required_fact_names_its_target_as_evidence_and_uses_a_prose_capable_predicate() -> None:
    with pytest.raises(ProseContractError, match="names its target as evidence"):
        PendingProse(COMMENT, (carried_by(SECTION),))
    requires = Fact(
        clause_ref(clause_id(1)),
        PredicateName.REQUIRES,
        Requirement(1, (SkillCriterion(KAFKA),)),
        EvidenceRef(Source.CORPUS, clause_ref(clause_id(1))),
        DAY,
    )
    assert PendingProse(SECTION, (requires,)).required == (requires,)
    due = Fact(
        clause_ref(clause_id(1)),
        PredicateName.REQUIRES,
        Requirement(1, ()),
        EvidenceRef(Source.CORPUS, clause_ref(clause_id(1))),
        DAY,
    )
    assert PendingProse(SECTION, (due,)).required == (due,)


def test_an_allowed_fact_never_restates_a_required_one() -> None:
    fact = carried_by(COMMENT)
    in_another_comment = replace(
        fact, evidence=EvidenceRef(Source.JIRA, comment_ref(comment_id(2)))
    )
    with pytest.raises(ProseContractError, match="never restates a required one"):
        PendingProse(COMMENT, (fact,), (in_another_comment,))


def test_an_allowed_fact_shares_the_targets_source() -> None:
    """A fact of another source restated as context would survive that source's outage in
    the text alone, an evidence path the base does not model; it is required or absent."""
    on_the_profile = Fact(
        employee_ref(CANDIDATE.id),
        PredicateName.HAS_SKILL,
        "go",
        EvidenceRef(Source.FRAPPE, employee_ref(CANDIDATE.id), "skills"),
        DAY,
    )
    with pytest.raises(ProseContractError, match="shares the target's source jira"):
        PendingProse(COMMENT, (carried_by(COMMENT),), (on_the_profile,))
    with pytest.raises(ProseContractError, match="shares the target's source corpus"):
        PendingProse(SECTION, (carried_by(SECTION),), (on_the_profile,))


def test_an_allowed_fact_is_never_evidenced_by_the_briefs_own_target() -> None:
    """A fact this text evidences is one it must carry: required, never context."""
    with pytest.raises(ProseContractError, match="a fact this target evidences is required"):
        PendingProse(COMMENT, (carried_by(COMMENT),), (carried_by(COMMENT, "go"),))


# --- The framework's completion -----------------------------------------------------------


def test_a_comment_brief_reads_as_a_ticket_comment_and_admits_its_parent_and_author() -> None:
    fact = carried_by(COMMENT)
    brief = brief_for(
        PendingProse(COMMENT, (fact,)),
        [TICKET],
        [RUNBOOK],
        LEXICON,
        {fact: FactRole.ANSWER_CHANGING},
    )
    assert brief.register is Register.TICKET_COMMENT
    assert brief.required_facts == (fact,)
    assert brief.required[0].role is FactRole.ANSWER_CHANGING
    assert brief.namespace.form_of("employee", CANDIDATE.id) == CANDIDATE.name
    assert brief.namespace.form_of("employee", AUTHOR.id) == AUTHOR.name
    assert brief.namespace.form_of("work_item", TICKET.id) == TICKET.title
    assert brief.namespace.form_of(SKILL_KIND, KAFKA) == "Kafka"


def test_a_section_brief_reads_as_its_document_kind() -> None:
    fact = carried_by(SECTION)
    brief = brief_for(
        PendingProse(SECTION, (fact,)), [TICKET], [RUNBOOK], LEXICON, {fact: FactRole.CONTEXT}
    )
    assert brief.register is Register.RUNBOOK
    assert brief.namespace.form_of("document", RUNBOOK.id) == RUNBOOK.title


def test_a_brief_needs_a_role_for_every_required_fact_and_a_parent_the_scenario_owns() -> None:
    fact = carried_by(COMMENT)
    with pytest.raises(ProseContractError, match="no role derived for"):
        brief_for(PendingProse(COMMENT, (fact,)), [TICKET], [RUNBOOK], LEXICON, {})
    with pytest.raises(
        ProseContractError, match="its work item ticket_001 is not one the scenario owns"
    ):
        brief_for(PendingProse(COMMENT, (fact,)), [], [RUNBOOK], LEXICON, {fact: FactRole.CONTEXT})


# --- The pre-compose contract -------------------------------------------------------------


def briefed(target: CommentTarget | SectionTarget, *facts: Fact) -> Brief:
    roles = {fact: FactRole.CONTEXT for fact in facts}
    return brief_for(PendingProse(target, facts), [TICKET], [RUNBOOK], LEXICON, roles)


def test_a_fact_carried_by_a_template_written_part_needs_no_brief() -> None:
    written = Document(
        RUNBOOK.id,
        RUNBOOK.title,
        RUNBOOK.kind,
        DAY,
        (DocumentSection(clause_id(1), "Deniz owns Kafka."),),
    )
    check_pending([TICKET], [written], [], [carried_by(SECTION)])


def test_a_fact_carried_by_nothing_is_refused_by_name() -> None:
    with pytest.raises(
        ProseContractError, match="neither a part the scenario planted nor a brief's target"
    ):
        check_pending([TICKET], [RUNBOOK], [], [carried_by(SECTION)])


def test_a_brief_requires_exactly_the_authored_facts_naming_its_target() -> None:
    kafka, python = carried_by(COMMENT), carried_by(COMMENT, skill_id("python"))
    check_pending([TICKET], [RUNBOOK], [briefed(COMMENT, kafka, python)], [kafka, python])
    with pytest.raises(
        ProseContractError, match="the brief requires .* and the authored facts naming it are"
    ):
        check_pending([TICKET], [RUNBOOK], [briefed(COMMENT, kafka)], [kafka, python])


def test_a_pending_target_is_absent_from_the_records_and_briefed_once() -> None:
    fact = carried_by(COMMENT)
    written = Comment(
        comment_id(1), DAY, AUTHOR.id, f"[comment_001, 2026-03-01, {AUTHOR.id} — x] hi"
    )
    present = WorkItem(
        TICKET.id,
        TICKET.title,
        TICKET.owner_id,
        TICKET.status,
        TICKET.component_id,
        DAY,
        None,
        None,
        (written,),
    )
    with pytest.raises(ProseContractError, match="pending under a brief and already present"):
        check_pending([present], [RUNBOOK], [briefed(COMMENT, fact)], [fact])
    with pytest.raises(ProseContractError, match="a target has one brief"):
        check_pending([TICKET], [RUNBOOK], [briefed(COMMENT, fact), briefed(COMMENT, fact)], [fact])


def test_pending_positions_fit_the_parents_final_order() -> None:
    fact = carried_by(COMMENT)
    beyond = CommentTarget(comment_id(1), TICKET.id, 1, DAY, AUTHOR.id)
    fact_beyond = carried_by(beyond)
    with pytest.raises(
        ProseContractError, match=r"pending positions \[1\] do not fit an order of 1 parts"
    ):
        check_pending([TICKET], [RUNBOOK], [briefed(beyond, fact_beyond)], [fact_beyond])
    check_pending([TICKET], [RUNBOOK], [briefed(COMMENT, fact)], [fact])


def test_an_allowed_fact_is_a_fact_of_the_world() -> None:
    fact = carried_by(COMMENT)
    context = Fact(
        work_item_ref(TICKET.id),
        PredicateName.IN_COMPONENT,
        component_ref(TICKET.component_id),
        EvidenceRef(Source.JIRA, work_item_ref(TICKET.id), "component_id"),
        DAY,
    )
    brief = brief_for(
        PendingProse(COMMENT, (fact,), (context,)),
        [TICKET],
        [RUNBOOK],
        LEXICON,
        {fact: FactRole.CONTEXT},
    )
    check_allowed([brief], FactBase((context,)))
    with pytest.raises(ProseContractError, match="an allowed fact is a fact of the world"):
        check_allowed([brief], FactBase(()))
