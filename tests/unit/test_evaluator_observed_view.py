"""The observed-run view holds what a run's reads support and nothing else: structured facts as
returned and dated to the run's day, a prose fact only when its comment or section came back
with the sealed text, and nothing from a record the run was shown two ways. Every difference
between what was read and the sealed world is a finding of kinds and ids; a part the
evaluator cannot vouch for is withdrawn from coverage, so a negative it could hide is not
grounded. The systems here hold the sealed world unless a test makes them drift."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    Comment,
    DocumentSection,
    EntityKind,
    EntityRef,
    Fact,
    KindSlice,
    KnownFalse,
    KnownTrue,
    PredicateName,
    RecordSlice,
    SliceStatus,
    Source,
    UnknownReason,
    Unresolved,
    WorkItem,
    derive,
    document_ref,
    employee_ref,
    establish,
    leave_ref,
    work_item_ref,
)
from leaveimpact.core.ids import DocumentId, EmployeeId, WorkItemId, comment_id, work_item_id
from leaveimpact.core.timeshape import encode_date_span
from leaveimpact.evaluator.observed_view import (
    IntegrityFinding,
    IntegrityKind,
    ObservedRun,
    observe,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import run_export
from tests.unit.reads_fixture import Recorder, Systems, systems_holding
from tests.unit.throwaway_world import loaded_world

SKILL, OWNS = PredicateName.HAS_SKILL, PredicateName.OWNS_WORK_ITEM
EVERY_TICKET = KindSlice(EntityKind.WORK_ITEM)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def systems(world: SealedWorld) -> Systems:
    """Fresh systems holding the sealed world: a test may make them drift."""
    return systems_holding(world)


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


def observed(world: SealedWorld, scenario: Scenario, reads: Recorder) -> ObservedRun:
    return observe(world.index, run_export(world, scenario, operations=reads.operations))


def kinds(run: ObservedRun) -> list[IntegrityKind]:
    return [finding.kind for finding in run.findings]


class Subject:
    """A sealed skill evidenced only by a ticket comment: the comment, its ticket, the fact."""

    def __init__(self, world: SealedWorld) -> None:
        self.comment = next(
            ref for ref in world.index.carried if ref.kind is EntityKind.COMMENT
        )
        self.ticket = world.index.parts[self.comment].parent
        (self.fact,) = world.index.carried[self.comment]
        self.who = self.fact.subject
        self.ticket_id = WorkItemId(self.ticket.id)
        self.employee_id = EmployeeId(self.who.id)


@pytest.fixture(scope="module")
def skill(world: SealedWorld) -> Subject:
    return Subject(world)


def rewritten(item: WorkItem, comment: EntityRef, text: str) -> WorkItem:
    return replace(
        item,
        comments=tuple(
            replace(each, text=text) if each.id == comment.id else each for each in item.comments
        ),
    )


# --- What the view holds ----------------------------------------------------------------------


def test_structured_facts_are_the_returned_records_own_dated_to_the_runs_day(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    reads = Recorder(systems)
    reads.read("employees")
    run = observed(world, scenario, reads)
    today = scenario.spec.today
    expected = {
        item
        for employee in systems.people.employees()
        for item in derive(employee, today)
        if isinstance(item, Fact)
    }
    assert set(run.view.facts) == expected
    assert {fact.observable_from for fact in run.view.facts} == {today}
    assert run.findings == ()
    assert run.view.coverage == run.coverage


def test_an_unread_run_observed_nothing(world: SealedWorld, scenario: Scenario) -> None:
    run = observe(world.index, run_export(world, scenario))
    assert (run.view.facts, run.view.gaps, run.findings) == ((), (), ())
    assert run.read_as_sealed == frozenset()


def test_a_prose_fact_enters_only_when_its_carrier_was_read_with_the_sealed_text(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    elsewhere = Recorder(systems)
    elsewhere.read("employee", {"id": skill.employee_id})
    elsewhere.read("components")
    unread = observed(world, scenario, elsewhere)
    assert skill.fact.value not in {
        fact.value for fact in unread.view.facts_about(skill.who, SKILL)
    }

    reads = Recorder(systems)
    reads.read("work_item", {"id": skill.ticket_id})
    read = observed(world, scenario, reads)
    assert skill.comment in read.read_as_sealed
    admitted = replace(skill.fact, observable_from=scenario.spec.today)
    assert admitted in read.view.facts
    assert establish(read.view, skill.who, SKILL, skill.fact.value) == KnownTrue((admitted,))
    assert read.findings == ()


def test_the_carrier_index_is_world_wide(world: SealedWorld, systems: Systems) -> None:
    # A run of one scenario reads a document another scenario planted: what its section
    # states is true whoever planted it, and whether it matters is the answer grading's.
    carrier, facts = next(
        (ref, facts)
        for ref, facts in world.index.carried.items()
        if ref.kind is EntityKind.CLAUSE and facts[0].predicate is PredicateName.REQUIRES
    )
    document = world.index.parts[carrier].parent
    owner = next(
        each
        for each in world.scenarios
        if any(document_ref(p.entity.id) == document for p in each.owned.documents)
    )
    another = next(each for each in world.scenarios if each is not owner)
    reads = Recorder(systems)
    reads.read("document", {"id": DocumentId(document.id)})
    run = observed(world, another, reads)
    assert replace(facts[0], observable_from=another.spec.today) in run.view.facts


# --- When the systems no longer hold the sealed world ---------------------------------------------


def test_a_comment_whose_text_is_not_the_sealed_one_admits_nothing_and_closes_nothing(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    def everything_about_the_skill() -> ObservedRun:
        reads = Recorder(systems)
        reads.read("employee", {"id": skill.employee_id})
        reads.read("work_items")
        return observed(world, scenario, reads)

    sealed = everything_about_the_skill()
    assert isinstance(establish(sealed.view, skill.who, SKILL, skill.fact.value), KnownTrue)

    tickets = systems.work.tickets
    tickets[skill.ticket_id] = rewritten(tickets[skill.ticket_id], skill.comment, "Edited since.")
    drifted = everything_about_the_skill()
    assert drifted.findings == (
        IntegrityFinding(IntegrityKind.PART_DIFFERS, skill.ticket, skill.comment),
    )
    assert skill.comment not in drifted.read_as_sealed
    # The sealed fact is not substituted, and the edited comment is not read as saying
    # nothing: every ticket was listed, and "no comment shows the skill" is still open.
    assert drifted.coverage.status(EVERY_TICKET) is SliceStatus.UNREAD
    assert establish(drifted.view, skill.who, SKILL, skill.fact.value) == Unresolved(
        skill.who, SKILL, UnknownReason.INSUFFICIENT
    )
    # The ticket's own fields were not doubted.
    assert drifted.coverage.status(RecordSlice(skill.ticket)) is SliceStatus.COVERED


def test_a_missing_and_an_unknown_part_are_each_a_finding_and_each_withdrawn(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    tickets = systems.work.tickets
    sealed_item = tickets[skill.ticket_id]
    stranger = Comment(comment_id(999), scenario.spec.today, skill.employee_id, "A new remark.")
    kept = tuple(each for each in sealed_item.comments if each.id != skill.comment.id)
    tickets[skill.ticket_id] = replace(sealed_item, comments=(*kept, stranger))
    reads = Recorder(systems)
    reads.read("work_items")
    run = observed(world, scenario, reads)
    unknown = EntityRef(EntityKind.COMMENT, stranger.id)
    assert set(run.findings) == {
        IntegrityFinding(IntegrityKind.PART_MISSING, skill.ticket, skill.comment),
        IntegrityFinding(IntegrityKind.PART_UNKNOWN, skill.ticket, unknown),
    }
    assert run.coverage.status(EVERY_TICKET) is SliceStatus.UNREAD
    assert replace(skill.fact, observable_from=scenario.spec.today) not in run.view.facts


def test_a_drifted_structured_record_derives_its_facts_as_returned_with_a_finding(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    tickets = systems.work.tickets
    sealed_item = tickets[skill.ticket_id]
    new_owner = next(e.id for e in world.org.employees if e.id != sealed_item.owner_id)
    tickets[skill.ticket_id] = replace(sealed_item, owner_id=new_owner)
    reads = Recorder(systems)
    reads.read("work_item", {"id": skill.ticket_id})
    run = observed(world, scenario, reads)
    assert run.findings == (IntegrityFinding(IntegrityKind.RECORD_DIFFERS, skill.ticket),)
    # Grounding asks what the run's reads support, and it read this owner.
    assert isinstance(
        establish(run.view, skill.ticket, OWNS, employee_ref(new_owner)), KnownTrue
    )
    # Its comments are compared one by one: the sealed one still carries its fact.
    assert skill.comment in run.read_as_sealed


def test_a_record_the_sealed_world_does_not_hold_is_a_finding_and_still_read(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    foreign = replace(systems.work.tickets[skill.ticket_id], id=work_item_id(999), comments=())
    systems.work.add_work_item(foreign)
    reads = Recorder(systems)
    reads.read("work_item", {"id": foreign.id})
    run = observed(world, scenario, reads)
    stranger = work_item_ref(foreign.id)
    assert run.findings == (IntegrityFinding(IntegrityKind.UNKNOWN_RECORD, stranger),)
    assert isinstance(establish(run.view, stranger, OWNS), KnownTrue)


def test_a_record_the_run_was_shown_two_ways_derives_nothing(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    reads = Recorder(systems)
    reads.read("work_item", {"id": skill.ticket_id})
    tickets = systems.work.tickets
    sealed_item = tickets[skill.ticket_id]
    new_owner = next(e.id for e in world.org.employees if e.id != sealed_item.owner_id)
    tickets[skill.ticket_id] = replace(sealed_item, owner_id=new_owner)
    reads.read("work_item", {"id": skill.ticket_id})
    run = observed(world, scenario, reads)
    assert run.findings == (IntegrityFinding(IntegrityKind.RETURNS_DIFFER, skill.ticket),)
    assert run.view.facts_about(skill.ticket, OWNS) == ()
    assert skill.comment not in run.read_as_sealed
    assert establish(run.view, skill.ticket, OWNS) == Unresolved(
        skill.ticket, OWNS, UnknownReason.INSUFFICIENT
    )


def test_a_record_no_fact_can_be_made_from_is_a_finding_and_never_an_exception(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    people = systems.people.people
    blank = replace(world.org.employees[0], location="  ")
    people[blank.id] = blank
    reads = Recorder(systems)
    reads.read("employees")
    run = observed(world, scenario, reads)
    who = employee_ref(blank.id)
    assert set(run.findings) == {
        IntegrityFinding(IntegrityKind.RECORD_DIFFERS, who),
        IntegrityFinding(IntegrityKind.RECORD_NOT_DERIVABLE, who),
    }
    assert not [fact for fact in run.view.facts if fact.subject == who]
    assert run.coverage.status(RecordSlice(who)) is SliceStatus.UNREAD
    # Everyone else's record was read as it is.
    other = employee_ref(world.org.employees[1].id)
    assert run.view.facts_about(other, PredicateName.EMPLOYED_AS)


def test_a_sealed_record_a_completed_read_should_have_returned_is_a_finding(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    leave = scenario.investigated_leave
    gone = world.org.employees[2]
    del systems.work.tickets[skill.ticket_id]
    del systems.people.leaves[leave.id]
    del systems.people.people[gone.id]
    reads = Recorder(systems)
    reads.read("work_items")
    reads.read("leaves_within", {"span": encode_date_span(scenario.spec.window)})
    reads.read("employee", {"id": gone.id})
    run = observed(world, scenario, reads)
    assert set(run.findings) == {
        IntegrityFinding(IntegrityKind.SEALED_RECORD_NOT_RETURNED, skill.ticket),
        IntegrityFinding(IntegrityKind.SEALED_RECORD_NOT_RETURNED, leave_ref(leave.id)),
        IntegrityFinding(IntegrityKind.SEALED_RECORD_NOT_RETURNED, employee_ref(gone.id)),
    }
    # The run observed what it observed: its coverage stands, and the finding says the
    # systems no longer held the sealed world.
    assert run.coverage.status(EVERY_TICKET) is SliceStatus.COVERED
    assert establish(run.view, employee_ref(gone.id), PredicateName.EMPLOYED_AS) == KnownFalse()


def test_a_read_by_id_answered_with_another_record_is_a_finding_about_the_record_asked_for(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    # The batch review of group B: the source answers a read of one employee with
    # another's record. Nothing was learned about the one asked for, and that is said.
    asked, other = world.org.employees[0], world.org.employees[1]
    systems.people.people[asked.id] = other
    reads = Recorder(systems)
    reads.read("employee", {"id": asked.id})
    run = observed(world, scenario, reads)
    assert run.findings == (
        IntegrityFinding(IntegrityKind.ANOTHER_RECORD_RETURNED, employee_ref(asked.id)),
    )
    assert run.coverage.status(RecordSlice(employee_ref(asked.id))) is SliceStatus.UNREAD
    employed = PredicateName.EMPLOYED_AS
    assert establish(run.view, employee_ref(asked.id), employed) == Unresolved(
        employee_ref(asked.id), employed, UnknownReason.INSUFFICIENT
    )
    # The record that did come back is the sealed one of its own id, and was read.
    assert run.view.facts_about(employee_ref(other.id), employed)

    # Reported whatever else returned the record asked for, and for an id nothing holds.
    reads.read("employees")
    reads.read("employee", {"id": EmployeeId("emp_999")})
    systems.people.people[EmployeeId("emp_999")] = other
    reads.read("employee", {"id": EmployeeId("emp_999")})
    again = observed(world, scenario, reads)
    assert [finding for finding in again.findings if finding.record.id == "emp_999"] == [
        IntegrityFinding(IntegrityKind.ANOTHER_RECORD_RETURNED, employee_ref(EmployeeId("emp_999")))
    ]
    assert IntegrityFinding(
        IntegrityKind.ANOTHER_RECORD_RETURNED, employee_ref(asked.id)
    ) in again.findings


def test_a_section_whose_text_is_not_the_sealed_one_states_no_requirement(
    world: SealedWorld, systems: Systems, scenario: Scenario
) -> None:
    carrier = next(
        ref
        for ref, facts in world.index.carried.items()
        if facts[0].predicate is PredicateName.REQUIRES
    )
    parent = world.index.parts[carrier].parent
    documents = systems.documents.documents
    sealed_document = documents[DocumentId(parent.id)]
    documents[sealed_document.id] = replace(
        sealed_document,
        sections=tuple(
            DocumentSection(section.id, "Rewritten.") for section in sealed_document.sections
        ),
    )
    reads = Recorder(systems)
    reads.read("document", {"id": sealed_document.id})
    run = observed(world, scenario, reads)
    assert IntegrityFinding(IntegrityKind.PART_DIFFERS, parent, carrier) in run.findings
    requires = PredicateName.REQUIRES
    assert establish(run.view, carrier, requires) == Unresolved(
        carrier, requires, UnknownReason.INSUFFICIENT
    )


# --- The run's own condition ----------------------------------------------------------------------


def test_what_was_read_before_a_source_failed_stays_in_the_view(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    reads = Recorder(systems)
    reads.read("work_item", {"id": skill.ticket_id})
    systems.work.reachable = False
    reads.read("work_items")
    run = observed(world, scenario, reads)
    assert Source.JIRA not in run.view.condition.reachable
    assert run.view.facts_about(skill.ticket, OWNS)
    assert skill.comment in run.read_as_sealed
    assert run.coverage.status(EVERY_TICKET) is SliceStatus.FAILED
    assert run.findings == ()


def test_findings_come_in_one_order_whatever_order_the_reads_came_in(
    world: SealedWorld, systems: Systems, scenario: Scenario, skill: Subject
) -> None:
    tickets = systems.work.tickets
    tickets[skill.ticket_id] = rewritten(tickets[skill.ticket_id], skill.comment, "Edited.")
    people = systems.people.people
    first = world.org.employees[0]
    people[first.id] = replace(first, location="Elsewhere")
    one_way = Recorder(systems)
    one_way.read("work_items")
    one_way.read("employees")
    other_way = Recorder(systems)
    other_way.read("employees")
    other_way.read("work_items")
    findings = observed(world, scenario, one_way).findings
    assert findings == observed(world, scenario, other_way).findings
    assert kinds(observed(world, scenario, one_way)) == [
        IntegrityKind.PART_DIFFERS,
        IntegrityKind.RECORD_DIFFERS,
    ]
