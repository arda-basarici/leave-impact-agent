"""The report view over exports: the all-types fixture renders every claim exactly once in
the manager's order with every citation shown, named by the records the run read, the
quotations found in the text as read and every derivation resolving within the run; the
four rendering cases (an attempt that ended before any successful read, a completed run
with no claim, a citation no read returned, a claim set that is not well-formed) each
render whole; a record the run's own reads returned two ways is withdrawn with nothing
credited; the ending comes first and says what the log holds and no more; the condition
names the unreachable sources and links the unknowns recorded as caused by them."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from leaveimpact.app.public import PublicId, PublicReplay
from leaveimpact.app.report import (
    EvidenceStatus,
    ReportView,
    report_view,
    value_text,
)
from leaveimpact.core import (
    ClaimType,
    DateSpan,
    EvidenceRef,
    Requirement,
    RunCondition,
    ScenarioId,
    SkillCriterion,
    Source,
    TerminalStatus,
    Unknown,
    UnknownReason,
)
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import claim_id, skill_id
from tests.unit import format_fixtures as cases
from tests.unit import report_view_fixture as fixture
from tests.unit import stated_fixture as f

PUBLISHED = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
REPLAY = PublicReplay(
    PublicId("handover"),
    ScenarioId("scenario_003"),
    "The handover",
    PUBLISHED,
    TerminalStatus.COMPLETED,
)


def view_of(export: cases.RunExport) -> ReportView:
    return report_view(REPLAY, export, fixture.INSTANTS)


def every_evidence(view: ReportView) -> list[tuple[str, EvidenceStatus]]:
    items: list[tuple[str, EvidenceStatus]] = []
    blocks = [
        *(
            block
            for section in view.impacts
            for block in (section.impact, *section.assessments, *section.actions)
        ),
        *(section.constraint for section in view.constraints),
        *view.unknowns,
        *view.conflicts,
        *view.unlinked,
    ]
    for block in blocks:
        items.extend((item.target.id, item.status) for item in block.evidence)
    return items


def test_every_claim_appears_exactly_once_in_the_managers_order() -> None:
    view = view_of(fixture.all_types())
    ids = view.claim_ids()
    assert sorted(ids) == sorted(claim.claim_id for claim in fixture.claims())
    assert len(set(ids)) == len(ids)
    assert [section.impact.claim_id for section in view.impacts] == [
        "claim_001",
        "claim_002",
        "claim_003",
    ]
    deadline, meeting, obligation = view.impacts
    assert [b.claim_id for b in deadline.assessments] == ["claim_005"]
    assert [b.claim_id for b in deadline.actions] == ["claim_007"]
    assert [b.claim_id for b in meeting.assessments] == ["claim_006"]
    assert [b.claim_id for b in meeting.actions] == ["claim_008"]
    assert obligation.assessments == () and [b.claim_id for b in obligation.actions] == [
        "claim_011"
    ]
    assert [s.constraint.claim_id for s in view.constraints] == ["claim_004"]
    assert view.constraints[0].impact_id == "claim_001"
    assert [b.claim_id for b in view.unknowns] == ["claim_009"]
    assert [b.claim_id for b in view.conflicts] == ["claim_010"]
    assert view.unlinked == () and view.problems == ()


def test_the_sentences_are_templates_over_the_claims_fields_naming_people_by_their_records() -> (
    None
):
    view = view_of(fixture.all_types())
    deadline, meeting, obligation = view.impacts
    ticket = f"{f.TITLE} (ticket_042)"
    deniz = "Deniz Kaya (emp_023)"
    assert deadline.impact.sentence == f"A deadline the leave affects: {ticket}."
    assert meeting.impact.sentence == "A meeting the leave affects: Release review (event_007)."
    assert obligation.impact.sentence == (
        "An obligation of the leaver's the leave affects: clause_011 of Payments runbook (doc_003)."
    )
    assert view.constraints[0].constraint.sentence == (
        f"clause_011 of Payments runbook (doc_003) applies to {ticket}."
    )
    assert deadline.assessments[0].sentence == f"{deniz} can cover {ticket}."
    assert meeting.assessments[0].sentence == (
        f"{deniz} cannot cover Release review (event_007): is not available."
    )
    assert deadline.actions[0].sentence == f"Assign {deniz} to {ticket}."
    assert deadline.actions[0].rationale == fixture.RATIONALE
    assert meeting.actions[0].sentence == "Release review (event_007) is left uncovered."
    assert obligation.actions[0].sentence == (
        "Whether clause_011 of Payments runbook (doc_003) is covered is unknown."
    )
    assert view.unknowns[0].sentence == (
        f"The employed as of {deniz} could not be established: the evidence read is insufficient."
    )
    assert view.conflicts[0].sentence == (
        f"The sources disagree on the owns work item of {ticket}: corpus says {deniz}; jira says "
        "Alice Demir (emp_017). Resolved as Alice Demir (emp_017) by the rule that the system of "
        "record wins."
    )
    assert view.conflicts[0].observations == (("corpus", deniz), ("jira", "Alice Demir (emp_017)"))
    assert all(block.kind is ClaimType.COVERAGE_ACTION for block in deadline.actions)


def test_every_citation_is_shown_from_the_runs_own_reads_with_its_positions_and_instant() -> None:
    view = view_of(fixture.all_types())
    assert {kind for _, kind in every_evidence(view)} == {EvidenceStatus.SHOWN}
    cited_kinds = {
        item.target.kind
        for section in view.impacts
        for block in (section.impact, *section.assessments, *section.actions)
        for item in block.evidence
    } | {item.target.kind for block in (*view.unknowns, *view.conflicts) for item in block.evidence}
    assert cited_kinds == set(EntityKind)
    deadline = view.impacts[0]
    # A claim holds its citations in canonical order (by source), so items are found by target.
    leave, ticket = deadline.impact.evidence
    assert ticket.label == f"{f.TITLE} (ticket_042)" and ticket.field == "due_on"
    assert ("due_on", "2026-03-20") in ticket.fields and ("owner_id", "emp_017") in ticket.fields
    assert ("comments", "") not in ticket.fields and all(
        name != "comments" for name, _ in ticket.fields
    )
    assert ticket.positions == (7, 25) and ticket.recorded_at == fixture.INSTANTS[7]
    assert leave.target.kind is EntityKind.LEAVE and ("kind", "annual") in leave.fields
    skills, comment = deadline.assessments[0].evidence
    assert skills.target == f.DENIZ_REF and comment.target == f.COMMENT_REF
    assert ("skills", "none") in skills.fields and ("manager_id", "emp_017") in skills.fields
    assert comment.text == f.COMMENT.text and comment.held_by == f"{f.TITLE} (ticket_042)"
    assert [(q.text, q.found) for q in comment.quotes] == [(f.REMARK, True)]
    clause = view.constraints[0].constraint.evidence[0]
    assert clause.text == f.CLAUSE_TEXT and clause.held_by == "Payments runbook (doc_003)"
    assert [(q.predicate, q.found) for q in clause.quotes] == [
        ("requires", True),
        ("names_responsible", True),
    ]
    document = view.impacts[2].impact.evidence[1]
    assert document.label == "Payments runbook (doc_003)" and ("kind", "runbook") in document.fields
    assert all(name != "sections" for name, _ in document.fields)


def test_every_derivation_resolves_to_a_claim_on_the_page() -> None:
    view = view_of(fixture.all_types())
    links = [
        link
        for section in view.impacts
        for block in (section.impact, *section.assessments, *section.actions)
        for link in block.derived_from
    ]
    assert links and all(link.available for link in links)
    assert {link.claim_id for link in links} <= set(view.claim_ids())


def test_the_header_and_the_leave_come_from_the_context_and_the_record_read() -> None:
    view = view_of(fixture.all_types())
    header = view.header
    assert header.public_id == "handover" and header.title == "The handover"
    assert header.scenario_date == date(2026, 3, 2) and header.timezone == "Europe/Istanbul"
    assert header.system == "agent (reference)" and header.world_version == "7b806ed6"
    assert header.admitted_at == cases.ADMITTED
    leave = view.leave
    assert leave is not None
    assert leave.person == "Alice Demir (emp_017)" and leave.days == 5
    assert (leave.start, leave.end, leave.kind, leave.status) == (
        date(2026, 3, 9),
        date(2026, 3, 13),
        "annual",
        "approved",
    )
    assert leave.evidence.positions == (3,) and view.leave_id == "leave_005"


def test_a_citation_no_read_returned_renders_unavailable_with_the_page_intact() -> None:
    view = view_of(fixture.citing_an_unread_record())
    assert len(view.claim_ids()) == len(fixture.claims())
    unread = [
        item for item in view.impacts[0].impact.evidence if item.target == fixture.UNREAD_TICKET
    ]
    assert len(unread) == 1
    item = unread[0]
    assert item.status is EvidenceStatus.UNAVAILABLE
    assert item.label == "ticket_099" and item.fields == () and item.positions == ()
    assert item.recorded_at is None
    assert [kind for _, kind in every_evidence(view)].count(EvidenceStatus.UNAVAILABLE) == 1


def test_a_record_returned_two_ways_is_withdrawn_with_nothing_credited() -> None:
    view = view_of(fixture.ticket_returned_two_ways())
    statuses = dict(every_evidence(view))
    assert statuses["ticket_042"] is EvidenceStatus.WITHDRAWN
    assert statuses["comment_001"] is EvidenceStatus.WITHDRAWN
    assert {
        status for target, status in statuses.items() if target not in ("ticket_042", "comment_001")
    } == {EvidenceStatus.SHOWN}
    ticket = view.impacts[0].impact.evidence[1]
    assert ticket.target == f.TICKET_REF
    assert ticket.fields == () and ticket.text is None and ticket.positions == (7, 25)
    comment = view.impacts[0].assessments[0].evidence[1]
    assert comment.target == f.COMMENT_REF
    assert comment.text is None and comment.held_by == f"{f.TITLE} (ticket_042)"
    assert [(q.text, q.found) for q in comment.quotes] == [(f.REMARK, False)]
    # The sentences still name the ticket by its first return: the label is not evidence.
    assert (
        view.impacts[0].impact.sentence == f"A deadline the leave affects: {f.TITLE} (ticket_042)."
    )


def test_a_claim_set_that_is_not_well_formed_still_renders_every_claim_once() -> None:
    view = view_of(fixture.malformed_set())
    ids = view.claim_ids()
    assert len(ids) == 12 and len(set(ids)) == 12
    assert [b.claim_id for b in view.unlinked] == ["claim_012"]
    viable = view.impacts[0].assessments[0]
    assert [(link.claim_id, link.available) for link in viable.derived_from] == [
        ("claim_001", True),
        ("claim_099", False),
    ]
    assert any("claim_099" in line for line in view.problems)
    assert any("cycle" in line for line in view.problems)


def test_an_attempt_that_ended_before_any_read_says_nothing_ran() -> None:
    view = view_of(cases.never_claimed())
    ending = view.ending
    assert ending.status is TerminalStatus.FAILED
    assert ending.headline == "Nothing ran: no worker claimed the attempt."
    assert "Failed by infrastructure: no worker claimed the attempt" in ending.details
    assert "Abandoned by operator: cancelled" in ending.details
    assert ending.failure_anchor is None and ending.caps == ()
    assert ending.reads_summary == "0 completed reads returned 0 records from no source."
    assert view.leave is None and view.impacts == () and ending.empty


def test_a_failure_at_the_input_bound_anchors_the_counting_operation() -> None:
    view = view_of(cases.input_bound_exhausted())
    ending = view.ending
    assert ending.status is TerminalStatus.FAILED and ending.headline == "The run failed."
    anchor = ending.failure_anchor
    assert anchor is not None and anchor.startswith("count-")


def test_a_completed_run_with_no_claim_reports_no_impact_and_never_an_all_clear() -> None:
    view = view_of(cases.export((), cases.evidence(), request=11))
    ending = view.ending
    assert ending.status is TerminalStatus.COMPLETED and ending.empty
    assert ending.headline == "The run completed. It reported no impact."
    assert ending.reads_summary == "3 completed reads returned 4 records from frappe, jira."
    assert "The plan was approved automatically." in ending.details


def test_a_cap_exhausted_run_shows_the_caps_beside_its_accounted_consumption() -> None:
    export = fixture.all_types()
    capped = replace(export, record=replace(export.record, status=TerminalStatus.CAP_EXHAUSTED))
    ending = view_of(capped).ending
    assert ending.headline == "The run stopped under the registered caps and reported what it had."
    calls, tokens = ending.caps
    assert (calls.resource, calls.consumed, calls.cap, calls.at_cap) == (
        "model calls",
        "1",
        "20",
        False,
    )
    assert tokens.consumed == "at least 150" and tokens.cap == "100,000" and not tokens.at_cap
    assert "Finalization reserve: 2 calls, 5,000 tokens." in ending.details


def test_the_condition_names_the_unreachable_sources_and_links_their_unknowns() -> None:
    export = fixture.all_types()
    inaccessible = Unknown(
        claim_id=claim_id(13),
        evidence_refs=(EvidenceRef(Source.CORPUS, f.CLAUSE_REF),),
        subject=f.CLAUSE_REF,
        required_fact=cases.PredicateName.REQUIRES,
        reason=UnknownReason.INACCESSIBLE,
    )
    degraded = replace(
        export,
        record=replace(
            export.record, observed_condition=RunCondition.all_reachable().without(Source.CORPUS)
        ),
        trace=replace(export.trace, claims=(*export.trace.claims, inaccessible)),
    )
    view = view_of(degraded)
    assert view.condition.unreachable == (Source.CORPUS,)
    assert view.condition.unknown_ids == ("claim_013",)
    assert view_of(export).condition.unreachable == ()


def test_fact_values_read_as_a_sentence_says_them() -> None:
    reads = report_view(REPLAY, fixture.all_types(), fixture.INSTANTS)
    assert reads is not None
    requirement = Requirement(2, (SkillCriterion(skill_id("kafka")),))
    from leaveimpact.app.report import _Reads  # pyright: ignore[reportPrivateUsage]

    empty = _Reads(())
    assert value_text(requirement, empty) == "at least 2 people, each with the skill kafka"
    assert value_text(Requirement(1, ()), empty) == "at least 1 person"
    assert (
        value_text(DateSpan(date(2026, 3, 9), date(2026, 3, 13)), empty)
        == "2026-03-09 to 2026-03-13"
    )
    assert value_text(f.DENIZ_REF, empty) == "emp_023"
