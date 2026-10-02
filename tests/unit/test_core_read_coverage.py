"""Coverage from reads follows the read ports' shapes: a record is observed when a completed
read returned it, answered that it does not exist, or enumerated its kind; a kind by its
enumeration, and never where the tools have none; a window by the union of the completed
windows. A failed read covers nothing, what was read stays read whatever came after, and a
record returned two ways is withdrawn with everything it could have hidden.

The second half holds the rules to it through real operations: what an unread record
permits (the fourth build step's ruling 2), case by case."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, timedelta

from leaveimpact.core import (
    METHOD_TABLE,
    AbsentOutcome,
    Closure,
    Consulted,
    DateSpan,
    DefectOutcome,
    Document,
    DocumentKind,
    DocumentSection,
    Entity,
    EntityKind,
    EntityRef,
    Fact,
    FactBase,
    FactView,
    Gap,
    InstantSpan,
    KindSlice,
    KnownFalse,
    KnownTrue,
    Observed,
    Operation,
    OperationId,
    Outcome,
    PredicateName,
    PrefetchOrigin,
    RecordOutcome,
    RecordSlice,
    RecordsOutcome,
    RefusedCallOutcome,
    RunCondition,
    SliceStatus,
    Source,
    UnknownReason,
    UnreachableOutcome,
    Unresolved,
    WindowSlice,
    clause_ref,
    comment_ref,
    component_ref,
    coverage_from_reads,
    derive,
    document_ref,
    employee_ref,
    establish,
    establish_any,
    event_ref,
    leave_ref,
    specification_named,
    work_item_ref,
)
from leaveimpact.core.ids import document_id, employee_id, team_id
from leaveimpact.core.refs import team_ref
from leaveimpact.core.timeshape import encode_date_span, encode_instant
from tests.unit import test_core_derivation as records
from tests.unit import world_fixture as w


def as_returned[T: Entity](record: Observed[T]) -> Observed[Entity]:
    """``record`` typed as an operation's outcome holds it: any entity, from its source."""
    return Observed[Entity](record.value, record.source)


# The fixture's records as the systems would hold them, defined beside the derivation tests
# that hold their facts equal to the hand-written base.
ALICE_RECORD = as_returned(records.PEOPLE[0])
BOB_RECORD = as_returned(records.PEOPLE[1])
DENIZ_RECORD = as_returned(records.PEOPLE[2])
CAN_RECORD = as_returned(records.PEOPLE[3])
PAYMENTS = as_returned(records.PAYMENTS)
TICKET = as_returned(records.TICKET)
RELEASE = as_returned(records.RELEASE)
ALICE_LEAVE = as_returned(records.ALICE_LEAVE)

ALICE, BOB, CAN = employee_ref(w.ALICE), employee_ref(w.BOB), employee_ref(w.CAN)
DENIZ = employee_ref(w.DENIZ)
TICKET_REF = work_item_ref(w.TICKET)
RUNBOOK: Observed[Entity] = Observed(
    Document(
        document_id(7),
        "Runbook: Kafka upgrade",
        DocumentKind.RUNBOOK,
        date(2026, 2, 1),
        (DocumentSection(w.STALE_CLAUSE, "Bob owns the Kafka upgrade."),),
    ),
    Source.CORPUS,
)

COVERED, UNREAD = SliceStatus.COVERED, SliceStatus.UNREAD
FAILED, UNCLOSABLE = SliceStatus.FAILED, SliceStatus.UNCLOSABLE
EVERY_TICKET = KindSlice(EntityKind.WORK_ITEM)
EVERY_DOCUMENT = KindSlice(EntityKind.DOCUMENT)
SKILL, OWNS = PredicateName.HAS_SKILL, PredicateName.OWNS_WORK_ITEM
INSUFFICIENT, INACCESSIBLE = UnknownReason.INSUFFICIENT, UnknownReason.INACCESSIBLE

Call = tuple[str, Mapping[str, object], Outcome]


def by_id(tool: str, id: str, record: Observed[Entity] | None) -> Call:
    return (tool, {"id": id}, AbsentOutcome() if record is None else RecordOutcome(record))


def listing(tool: str, *records: Observed[Entity]) -> Call:
    return (tool, {}, RecordsOutcome(records))


def leaves_within(span: DateSpan, *records: Observed[Entity]) -> Call:
    return ("leaves_within", {"span": encode_date_span(span)}, RecordsOutcome(records))


def events_within(span: InstantSpan, *records: Observed[Entity]) -> Call:
    encoded = {"start": encode_instant(span.start), "end": encode_instant(span.end)}
    return ("events_within", {"span": encoded}, RecordsOutcome(records))


def down(tool: str, arguments: Mapping[str, object] | None = None) -> Call:
    source = _source_of(tool)
    return (tool, arguments or {}, UnreachableOutcome(source, "no answer after the retries"))


def _source_of(tool: str) -> Source:
    specification = specification_named(tool)
    assert specification is not None
    return METHOD_TABLE[specification.method].source


def reads(*calls: Call) -> tuple[Operation, ...]:
    """Prefetch operations in the order given, each on the source its tool reads."""
    return tuple(
        Operation(
            OperationId(f"op-{number}"),
            PrefetchOrigin(),
            tool,
            _source_of(tool),
            arguments,
            outcome,
        )
        for number, (tool, arguments, outcome) in enumerate(calls, start=1)
    )


def view_of(operations: tuple[Operation, ...], *planted: Fact) -> FactView:
    """What the rules see of a run: the facts every returned record derives, dated to the
    fixture's day, with the coverage its reads gave. ``planted`` are the prose facts a test
    admits by hand, standing in for the evaluator's gate on the carrier's content."""
    derived: dict[Fact | Gap, None] = {}
    unreachable: set[Source] = set()
    for operation in operations:
        outcome = operation.outcome
        if isinstance(outcome, UnreachableOutcome):
            unreachable.add(outcome.source)
        records = (
            (outcome.record,)
            if isinstance(outcome, RecordOutcome)
            else outcome.records
            if isinstance(outcome, RecordsOutcome)
            else ()
        )
        for record in records:
            derived.update(dict.fromkeys(derive(record, w.NOW)))
    facts = tuple(item for item in derived if isinstance(item, Fact))
    gaps = tuple(item for item in derived if isinstance(item, Gap))
    condition = RunCondition.all_reachable().without(*unreachable)
    return FactBase((*facts, *planted), gaps).observed(
        w.NOW, condition, coverage_from_reads(operations)
    )


# --- What covers a slice --------------------------------------------------------------------


def test_an_empty_trace_observed_nothing_and_some_slices_no_read_could_have() -> None:
    nothing = coverage_from_reads(())
    for where in (
        RecordSlice(CAN),
        KindSlice(EntityKind.EMPLOYEE),
        EVERY_TICKET,
        KindSlice(EntityKind.COMPONENT),
        WindowSlice(EntityKind.LEAVE, w.LEAVE_SPAN),
        WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN),
    ):
        assert nothing.status(where) is UNREAD
    # The corpus has a search and no enumeration; leaves, events and teams are found by
    # id or by window only.
    for kind in (EntityKind.DOCUMENT, EntityKind.LEAVE, EntityKind.EVENT, EntityKind.TEAM):
        assert nothing.status(KindSlice(kind)) is UNCLOSABLE


def test_a_record_is_observed_however_a_completed_read_returned_it() -> None:
    by_its_id = coverage_from_reads(reads(by_id("employee", w.CAN, CAN_RECORD)))
    assert by_its_id.status(RecordSlice(CAN)) is COVERED
    assert by_its_id.status(RecordSlice(BOB)) is UNREAD
    assert by_its_id.status(KindSlice(EntityKind.EMPLOYEE)) is UNREAD
    in_a_window = coverage_from_reads(reads(leaves_within(w.LEAVE_SPAN, ALICE_LEAVE)))
    assert in_a_window.status(RecordSlice(leave_ref(w.LEAVE))) is COVERED


def test_an_answer_of_no_such_record_is_an_observation_of_that_record() -> None:
    nobody = coverage_from_reads(reads(by_id("employee", "emp_099", None)))
    assert nobody.status(RecordSlice(employee_ref(employee_id(99)))) is COVERED
    assert nobody.status(RecordSlice(CAN)) is UNREAD


def test_a_read_by_id_answered_with_another_record_observed_only_what_it_returned() -> None:
    # Asked for Can, answered with Bob: Bob's record was returned, Can's was neither
    # returned nor found missing, and the mismatch is kept for whoever reports it.
    seen = coverage_from_reads(reads(by_id("employee", w.CAN, BOB_RECORD)))
    assert seen.status(RecordSlice(BOB)) is COVERED
    assert seen.status(RecordSlice(CAN)) is UNREAD
    assert seen.misanswered == {CAN}
    honest = coverage_from_reads(reads(by_id("employee", w.CAN, CAN_RECORD)))
    assert honest.misanswered == frozenset()


def test_an_enumeration_observes_its_kind_and_every_record_of_it_present_or_not() -> None:
    everyone = coverage_from_reads(reads(listing("employees", ALICE_RECORD, BOB_RECORD)))
    assert everyone.status(KindSlice(EntityKind.EMPLOYEE)) is COVERED
    assert everyone.status(RecordSlice(BOB)) is COVERED
    # Not in the enumeration: observed, as absent.
    assert everyone.status(RecordSlice(CAN)) is COVERED
    # An enumeration that returned nothing is still one.
    assert coverage_from_reads(reads(listing("work_items"))).status(EVERY_TICKET) is COVERED


def test_a_section_is_observed_inside_a_returned_document_and_a_comment_inside_a_ticket() -> None:
    search: Call = ("search", {"query": "kafka owner", "limit": 5}, RecordsOutcome((RUNBOOK,)))
    for call in (by_id("document", "doc_007", RUNBOOK), search):
        seen = coverage_from_reads(reads(call))
        assert seen.status(RecordSlice(clause_ref(w.STALE_CLAUSE))) is COVERED
        assert seen.status(RecordSlice(clause_ref(w.KAFKA_CLAUSE))) is UNREAD
        # A search returns what matched and a read by id one document: neither is the corpus.
        assert seen.status(EVERY_DOCUMENT) is UNCLOSABLE
    one_ticket = coverage_from_reads(reads(by_id("work_item", w.TICKET, TICKET)))
    assert one_ticket.status(RecordSlice(comment_ref(w.DENIZ_COMMENT))) is COVERED
    assert one_ticket.status(EVERY_TICKET) is UNREAD


def test_windows_cover_a_question_when_their_union_contains_it() -> None:
    week = WindowSlice(EntityKind.LEAVE, w.LEAVE_SPAN)  # 15 to 19 September
    first = DateSpan(date(2026, 9, 14), date(2026, 9, 16))
    assert coverage_from_reads(reads(leaves_within(first))).status(week) is UNREAD
    # Days are inclusive: 14-16 and 17-20 leave no day between them.
    from_the_17th = DateSpan(date(2026, 9, 17), date(2026, 9, 20))
    adjacent = reads(leaves_within(from_the_17th), leaves_within(first))
    assert coverage_from_reads(adjacent).status(week) is COVERED
    from_the_18th = DateSpan(date(2026, 9, 18), date(2026, 9, 20))
    gapped = reads(leaves_within(first), leaves_within(from_the_18th))
    assert coverage_from_reads(gapped).status(week) is UNREAD

    hour = WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN)  # 10:00 to 11:00
    start, end = w.RELEASE_SPAN.start, w.RELEASE_SPAN.end
    half = timedelta(minutes=30)
    # Half-open spans: one ending at 10:30 and one starting there leave no instant between.
    touching = reads(
        events_within(InstantSpan(start, start + half)),
        events_within(InstantSpan(start + half, end)),
    )
    assert coverage_from_reads(touching).status(hour) is COVERED
    short = reads(events_within(InstantSpan(start, end - timedelta(minutes=1))))
    assert coverage_from_reads(short).status(hour) is UNREAD
    # The same instants written in another zone are the same window.
    in_utc = InstantSpan(start.astimezone(UTC), end.astimezone(UTC))
    assert coverage_from_reads(reads(events_within(in_utc))).status(hour) is COVERED


def test_a_failed_read_covers_nothing_and_marks_what_its_source_left_unobserved() -> None:
    tracker_down = coverage_from_reads(reads(down("work_items")))
    assert tracker_down.status(EVERY_TICKET) is FAILED
    assert tracker_down.status(RecordSlice(component_ref(w.PAYMENTS))) is FAILED
    assert tracker_down.status(RecordSlice(CAN)) is UNREAD
    # A corpus that could not be read is an outage, not a limit of the tool surface.
    corpus_down = coverage_from_reads(reads(down("search", {"query": "kafka", "limit": 5})))
    assert corpus_down.status(EVERY_DOCUMENT) is FAILED


def test_a_malformed_record_and_a_refused_call_cover_nothing_and_fail_nothing() -> None:
    defect: Call = ("work_items", {}, DefectOutcome(Source.JIRA, "issue 10012", "no owner field"))
    refused: Call = ("employee", {"id": "LIA-42"}, RefusedCallOutcome("not an employee id"))
    seen = coverage_from_reads(reads(defect, refused))
    assert seen.status(EVERY_TICKET) is UNREAD
    assert seen.status(RecordSlice(CAN)) is UNREAD
    assert seen.failed == frozenset()


def test_what_a_run_read_stays_read_whatever_came_after() -> None:
    then_failed = reads(by_id("component", w.PAYMENTS, PAYMENTS), down("work_items"))
    payments = RecordSlice(component_ref(w.PAYMENTS))
    for operations in (then_failed, tuple(reversed(then_failed))):
        seen = coverage_from_reads(operations)
        assert seen.status(payments) is COVERED
        assert seen.status(EVERY_TICKET) is FAILED


def test_a_record_returned_two_ways_is_withdrawn_with_what_it_could_have_hidden() -> None:
    reassigned = as_returned(
        Observed(replace(records.TICKET.value, owner_id=w.BOB), Source.JIRA)
    )
    twice = coverage_from_reads(
        reads(listing("work_items", TICKET), by_id("work_item", w.TICKET, reassigned))
    )
    assert twice.unobserved == {TICKET_REF, comment_ref(w.DENIZ_COMMENT)}
    assert twice.status(RecordSlice(TICKET_REF)) is UNREAD
    # The ticket in doubt is where a comment showing a skill could be.
    assert twice.status(EVERY_TICKET) is UNREAD
    # Returned twice alike is returned.
    alike = coverage_from_reads(
        reads(listing("work_items", TICKET), by_id("work_item", w.TICKET, TICKET))
    )
    assert alike.unobserved == frozenset()
    assert alike.status(EVERY_TICKET) is COVERED
    # Found by one read and found missing by another.
    both = coverage_from_reads(
        reads(by_id("employee", w.CAN, CAN_RECORD), by_id("employee", w.CAN, None))
    )
    assert both.status(RecordSlice(CAN)) is UNREAD


def test_a_caller_can_withdraw_a_record_it_has_its_own_reason_to_doubt() -> None:
    everything = coverage_from_reads(reads(listing("work_items", TICKET)))
    doubted = everything.excluding([comment_ref(w.DENIZ_COMMENT)])
    assert doubted.status(RecordSlice(comment_ref(w.DENIZ_COMMENT))) is UNREAD
    assert doubted.status(EVERY_TICKET) is UNREAD
    # The ticket's own fields were not doubted.
    assert doubted.status(RecordSlice(TICKET_REF)) is COVERED


def _recorded(
    tool: str, source: Source, arguments: Mapping[str, object], outcome: Outcome
) -> tuple[Operation, ...]:
    """One operation exactly as given, whatever its tool declares."""
    return (Operation(OperationId("op-1"), PrefetchOrigin(), tool, source, arguments, outcome),)


def test_an_operation_is_credited_only_when_it_is_what_its_tool_declares() -> None:
    # The operation type holds no agreement between a tool and what was recorded for it, so
    # that a broken export can be decoded and reported. None of these observed what the
    # tool's name suggests (the batch review of group A).
    week = {"span": encode_date_span(w.LEAVE_SPAN)}
    can = {"id": w.CAN}
    not_credited = (
        # A read of the HR system recorded against the tracker says nothing about HR.
        (_recorded("employee", Source.JIRA, can, AbsentOutcome()), RecordSlice(CAN)),
        (_recorded("work_items", Source.FRAPPE, {}, RecordsOutcome(())), EVERY_TICKET),
        # Records of another kind: the employees were not listed, the leaves not searched.
        (
            _recorded("employees", Source.FRAPPE, {}, RecordsOutcome((ALICE_LEAVE,))),
            KindSlice(EntityKind.EMPLOYEE),
        ),
        (
            _recorded("leaves_within", Source.FRAPPE, week, RecordsOutcome((CAN_RECORD,))),
            WindowSlice(EntityKind.LEAVE, w.LEAVE_SPAN),
        ),
        # The other cardinality: an enumeration answers a sequence, a read by id one or none.
        (
            _recorded("employees", Source.FRAPPE, {}, RecordOutcome(CAN_RECORD)),
            KindSlice(EntityKind.EMPLOYEE),
        ),
        (
            _recorded("employees", Source.FRAPPE, {}, AbsentOutcome()),
            KindSlice(EntityKind.EMPLOYEE),
        ),
        (_recorded("employee", Source.FRAPPE, can, RecordsOutcome(())), RecordSlice(CAN)),
    )
    for operations, where in not_credited:
        assert coverage_from_reads(operations).status(where) is UNREAD, operations[0].tool


def test_a_malformed_operation_still_contributes_the_records_it_returned() -> None:
    listed = _recorded("employees", Source.FRAPPE, {}, RecordsOutcome((ALICE_LEAVE, CAN_RECORD)))
    seen = coverage_from_reads(listed)
    assert seen.status(RecordSlice(leave_ref(w.LEAVE))) is COVERED
    assert seen.status(RecordSlice(CAN)) is COVERED
    assert seen.status(KindSlice(EntityKind.EMPLOYEE)) is UNREAD
    assert seen.status(RecordSlice(BOB)) is UNREAD


def test_a_negative_about_hr_is_not_grounded_by_a_read_recorded_against_the_tracker() -> None:
    view = view_of(_recorded("employee", Source.JIRA, {"id": w.CAN}, AbsentOutcome()))
    employed = PredicateName.EMPLOYED_AS
    assert establish(view, CAN, employed) == Unresolved(CAN, employed, INSUFFICIENT)
    # The same call on the source its tool reads is an observation of that record's absence.
    honest = view_of(reads(by_id("employee", w.CAN, None)))
    assert establish(honest, CAN, employed) == KnownFalse()


def test_a_call_that_is_not_a_declared_tools_contributes_its_records_only() -> None:
    unknown = Operation(
        OperationId("op-1"),
        PrefetchOrigin(),
        "everyone",
        Source.FRAPPE,
        {},
        RecordsOutcome((CAN_RECORD,)),
    )
    undeclared = Operation(
        OperationId("op-2"),
        PrefetchOrigin(),
        "employees",
        Source.FRAPPE,
        {"team": "team_001"},
        RecordsOutcome((BOB_RECORD,)),
    )
    seen = coverage_from_reads((unknown, undeclared))
    assert seen.status(RecordSlice(CAN)) is COVERED
    assert seen.status(RecordSlice(BOB)) is COVERED
    assert seen.status(KindSlice(EntityKind.EMPLOYEE)) is UNREAD
    assert seen.status(RecordSlice(team_ref(team_id(1)))) is UNREAD
    assert seen.status(RecordSlice(document_ref(document_id(7)))) is UNREAD


# --- What an unread record permits, through real operations -----------------------------------


def test_on_an_empty_trace_nothing_is_known_true_or_known_false() -> None:
    view = view_of(())
    assert establish(view, CAN, SKILL, w.KAFKA) == Unresolved(CAN, SKILL, INSUFFICIENT)
    assert establish(view, TICKET_REF, OWNS, ALICE) == Unresolved(TICKET_REF, OWNS, INSUFFICIENT)
    membership = PredicateName.MEMBER_OF_COMPONENT
    assert establish(view, BOB, membership, component_ref(w.PAYMENTS)) == Unresolved(
        BOB, membership, INSUFFICIENT
    )


def test_an_employee_record_alone_does_not_ground_a_skill_not_held() -> None:
    view = view_of(reads(by_id("employee", w.CAN, CAN_RECORD)))
    assert establish(view, CAN, SKILL, w.KAFKA) == Unresolved(CAN, SKILL, INSUFFICIENT)
    # What the record does say is known.
    assert isinstance(establish(view, CAN, SKILL, w.POSTGRES), KnownTrue)


def test_the_record_and_every_ticket_ground_it_with_the_corpus_left_unclosed() -> None:
    view = view_of(reads(by_id("employee", w.CAN, CAN_RECORD), listing("work_items", TICKET)))
    lacks_kafka = establish(view, CAN, SKILL, w.KAFKA)
    assert lacks_kafka == KnownFalse()
    assert lacks_kafka.proof == (
        Consulted(RecordSlice(CAN), COVERED),
        Consulted(EVERY_DOCUMENT, UNCLOSABLE),
        Consulted(EVERY_TICKET, COVERED),
    )


def test_a_retrieved_comment_showing_the_skill_contradicts_the_negative() -> None:
    operations = reads(by_id("employee", w.DENIZ, DENIZ_RECORD), listing("work_items", TICKET))
    without_the_comment = view_of(operations)
    assert establish(without_the_comment, DENIZ, SKILL, w.KAFKA) == Unresolved(
        DENIZ, SKILL, UnknownReason.ABSENT
    )
    with_it = view_of(operations, w.DENIZ_KAFKA_IN_COMMENT)
    assert establish(with_it, DENIZ, SKILL, w.KAFKA) == KnownTrue((w.DENIZ_KAFKA_IN_COMMENT,))


def test_the_components_record_grounds_non_membership_and_the_employees_cannot() -> None:
    membership, payments = PredicateName.MEMBER_OF_COMPONENT, component_ref(w.PAYMENTS)
    employee_only = view_of(reads(by_id("employee", w.BOB, BOB_RECORD)))
    assert establish(employee_only, BOB, membership, payments) == Unresolved(
        BOB, membership, INSUFFICIENT
    )
    for call in (by_id("component", w.PAYMENTS, PAYMENTS), listing("components", PAYMENTS)):
        view = view_of(reads(call))
        assert establish(view, BOB, membership, payments) == KnownFalse()
        assert isinstance(establish(view, CAN, membership, payments), KnownTrue)


def test_a_leave_read_by_its_id_grounds_no_absence_of_leave_and_a_covering_window_does() -> None:
    on_leave = PredicateName.ON_LEAVE

    def away(view: FactView, who: EntityRef) -> Closure:
        return establish_any(
            view,
            on_leave,
            lambda fact: fact.subject == who and fact.value == w.LEAVE_SPAN,
            who,
            scope=w.LEAVE_SPAN,
        )

    one_leave = view_of(reads(by_id("leave", w.LEAVE, ALICE_LEAVE)))
    assert isinstance(away(one_leave, ALICE), KnownTrue)
    assert away(one_leave, BOB) == Unresolved(BOB, on_leave, INSUFFICIENT)
    the_week = view_of(reads(leaves_within(w.LEAVE_SPAN, ALICE_LEAVE)))
    assert away(the_week, BOB) == KnownFalse()
    assert isinstance(away(the_week, ALICE), KnownTrue)


def test_an_event_read_by_its_id_leaves_its_hour_unobserved() -> None:
    one_event = coverage_from_reads(reads(by_id("event", w.RELEASE, RELEASE)))
    assert one_event.status(RecordSlice(event_ref(w.RELEASE))) is COVERED
    assert one_event.status(WindowSlice(EntityKind.EVENT, w.RELEASE_SPAN)) is UNREAD


def test_a_conclusive_read_stays_usable_after_its_source_fails() -> None:
    membership, payments = PredicateName.MEMBER_OF_COMPONENT, component_ref(w.PAYMENTS)
    view = view_of(
        reads(
            by_id("employee", w.CAN, CAN_RECORD),
            by_id("component", w.PAYMENTS, PAYMENTS),
            down("work_items"),
        )
    )
    # The tracker is unreachable in this run's condition, and what it returned first stands.
    assert Source.JIRA not in view.condition.reachable
    assert establish(view, BOB, membership, payments) == KnownFalse()
    assert isinstance(establish(view, CAN, membership, payments), KnownTrue)
    # What the failure left unobserved is inaccessible, not unread.
    assert establish(view, CAN, SKILL, w.KAFKA) == Unresolved(CAN, SKILL, INACCESSIBLE)


def test_an_unread_tracker_leaves_a_runbooks_owner_open_and_a_read_one_resolves_it() -> None:
    runbook = by_id("document", "doc_007", RUNBOOK)
    unread = view_of(reads(runbook), w.STALE_OWNER)
    for asked in (ALICE, BOB, None):
        assert establish(unread, TICKET_REF, OWNS, asked) == Unresolved(
            TICKET_REF, OWNS, INSUFFICIENT
        )
    read = view_of(reads(runbook, by_id("work_item", w.TICKET, TICKET)), w.STALE_OWNER)
    assert isinstance(establish(read, TICKET_REF, OWNS, ALICE), KnownTrue)
    assert establish(read, TICKET_REF, OWNS, BOB) == KnownFalse()
