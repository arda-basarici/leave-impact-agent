"""Impact grounding over the four-person world: each subtype grounds on exactly the facts the
classes plant, a dated ticket is a deadline or nothing, a stale document never grounds an
obligation the tracker contradicts, an outage leaves the grounding open rather than false,
and the enumerator is the same predicate applied to every candidate."""

from dataclasses import replace
from datetime import date

from leaveimpact.core import (
    DerivedImpacts,
    Fact,
    FactBase,
    FactView,
    Grounded,
    Grounding,
    ImpactKey,
    ImpactSubtype,
    PredicateName,
    RunCondition,
    Source,
    Ungrounded,
    UnknownReason,
    Unresolved,
    WorkItemStatus,
    clause_ref,
    derive_impacts,
    employee_ref,
    event_ref,
    ground_impact,
    work_item_ref,
)
from leaveimpact.core.ids import clause_id
from leaveimpact.core.refs import EvidenceRef
from tests.unit import world_fixture as w

NORMAL = RunCondition.all_reachable()
VIEW = w.WORLD.at(w.NOW, NORMAL)
TICKET = work_item_ref(w.TICKET)
STATUS = w.ticket(PredicateName.WORK_ITEM_STATUS, WorkItemStatus.IN_PROGRESS, "status")
DUE = w.ticket(PredicateName.DUE_ON, date(2026, 9, 17), "due_on")
CONTACT_CLAUSE = clause_id(14)
CONTACT = ImpactKey(w.LEAVE, ImpactSubtype.RESPONSIBILITY, clause_ref(CONTACT_CLAUSE))
TICKET_DUTY = ImpactKey(w.LEAVE, ImpactSubtype.RESPONSIBILITY, TICKET)


def names(who: w.EmployeeId) -> Fact:
    return Fact(
        clause_ref(CONTACT_CLAUSE),
        PredicateName.NAMES_RESPONSIBLE,
        employee_ref(who),
        EvidenceRef(Source.CORPUS, clause_ref(CONTACT_CLAUSE)),
        w.WORLD_START,
    )


def world_with(*added: Fact, without: tuple[Fact, ...] = ()) -> FactBase:
    kept = tuple(fact for fact in w.FACTS if fact not in without)
    return FactBase((*kept, *added), w.WORLD.gaps)


def ground(key: ImpactKey, leaver: w.EmployeeId = w.ALICE, view: FactView = VIEW) -> Grounding:
    return ground_impact(view, key, leaver, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)


def test_a_deadline_grounds_on_ownership_status_and_a_due_date_inside_the_leave() -> None:
    assert ground(w.DEADLINE) == Grounded((w.LIVE_OWNER, STATUS, DUE))


def test_a_meeting_grounds_on_attendance_and_a_schedule_on_a_leave_day() -> None:
    assert ground(w.MEETING) == Grounded(
        (w.attends(w.RELEASE, w.ALICE), w.scheduled(w.RELEASE, w.RELEASE_SPAN))
    )
    # The other meeting is on a leave day too, but Alice does not attend it.
    other = ImpactKey(w.LEAVE, ImpactSubtype.MEETING, event_ref(w.OTHER_MEETING))
    assert ground(other) == Ungrounded()


def test_a_dated_ticket_is_a_deadline_or_nothing() -> None:
    # Due the day after the leave: the wrong-window distractor grounds neither subtype.
    after = world_with(replace(DUE, value=date(2026, 9, 20)), without=(DUE,))
    view = after.at(w.NOW, NORMAL)
    assert ground(w.DEADLINE, view=view) == Ungrounded()
    assert ground(TICKET_DUTY, view=view) == Ungrounded()
    # No due date at all: an open obligation, the work-item responsibility shape.
    undated = world_with(without=(DUE,)).at(w.NOW, NORMAL)
    assert ground(w.DEADLINE, view=undated) == Ungrounded()
    assert ground(TICKET_DUTY, view=undated) == Grounded((w.LIVE_OWNER, STATUS))


def test_a_done_ticket_grounds_nothing() -> None:
    done = world_with(replace(STATUS, value=WorkItemStatus.DONE), without=(STATUS, DUE))
    view = done.at(w.NOW, NORMAL)
    assert ground(w.DEADLINE, view=view) == Ungrounded()
    assert ground(TICKET_DUTY, view=view) == Ungrounded()


def test_a_stale_document_never_grounds_an_obligation_the_tracker_contradicts() -> None:
    # The runbook names Bob; the tracker names Alice; Bob holds no deadline on the ticket.
    assert ground(w.DEADLINE, leaver=w.BOB) == Ungrounded()


def test_an_unreachable_source_leaves_the_grounding_open_with_the_question() -> None:
    no_tracker = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    assert ground(w.DEADLINE, view=no_tracker) == Unresolved(
        TICKET, PredicateName.OWNS_WORK_ITEM, UnknownReason.INACCESSIBLE
    )
    no_calendar = w.WORLD.at(w.NOW, NORMAL.without(Source.CALENDAR))
    assert ground(w.MEETING, view=no_calendar) == Unresolved(
        event_ref(w.RELEASE), PredicateName.ATTENDS_EVENT, UnknownReason.INACCESSIBLE
    )


def test_a_documented_responsibility_grounds_on_the_section_naming_the_leaver() -> None:
    view = world_with(names(w.ALICE)).at(w.NOW, NORMAL)
    assert ground(CONTACT, view=view) == Grounded((names(w.ALICE),))
    # The corpus answered and names nobody else: known false, so ungrounded for Bob.
    assert ground(CONTACT, leaver=w.BOB, view=view) == Ungrounded()
    no_corpus = world_with(names(w.ALICE)).at(w.NOW, NORMAL.without(Source.CORPUS))
    assert ground(CONTACT, view=no_corpus) == Unresolved(
        clause_ref(CONTACT_CLAUSE), PredicateName.NAMES_RESPONSIBLE, UnknownReason.INACCESSIBLE
    )


def test_the_enumerator_applies_the_same_predicate_to_every_candidate() -> None:
    view = world_with(names(w.ALICE)).at(w.NOW, NORMAL)
    derived = derive_impacts(view, w.LEAVE, w.ALICE, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert derived == DerivedImpacts((w.DEADLINE, w.MEETING, CONTACT), ())
    # Bob's only connection to the ticket is the stale runbook: proposed, then refused.
    bob = derive_impacts(view, w.LEAVE, w.BOB, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert bob == DerivedImpacts(
        (ImpactKey(w.LEAVE, ImpactSubtype.MEETING, event_ref(w.OTHER_MEETING)),), ()
    )


def test_the_enumerator_reports_what_an_outage_leaves_open() -> None:
    no_tracker = w.WORLD.at(w.NOW, NORMAL.without(Source.JIRA))
    # Alice's ownership lives in the tracker: no candidate at all without it, only the meeting.
    alice = derive_impacts(no_tracker, w.LEAVE, w.ALICE, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    assert alice == DerivedImpacts((w.MEETING,), ())
    # The runbook still proposes the ticket for Bob, and the record cannot answer.
    bob = derive_impacts(no_tracker, w.LEAVE, w.BOB, w.LEAVE_SPAN, w.REFERENCE_TIMEZONE)
    open_question = Unresolved(TICKET, PredicateName.OWNS_WORK_ITEM, UnknownReason.INACCESSIBLE)
    assert bob.unresolved == (
        (ImpactKey(w.LEAVE, ImpactSubtype.DEADLINE, TICKET), open_question),
        (TICKET_DUTY, open_question),
    )
