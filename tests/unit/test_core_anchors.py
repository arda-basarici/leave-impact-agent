"""The anchor table read two ways: the generator's check of a drafted text drops the author's
own group, a harness's check of a model's quote keeps every group and lets the author say
"I"; both look a spelling up as a whole word, and the table's digest moves with the table."""

from datetime import date

import pytest

from leaveimpact.core import (
    EvidenceRef,
    Fact,
    PredicateName,
    Source,
    clause_ref,
    comment_ref,
    employee_ref,
    work_item_ref,
)
from leaveimpact.core import anchors as core_anchors
from leaveimpact.core.anchors import (
    ANCHOR_ROWS,
    SKILL_KIND,
    Lexicon,
    SurfaceForm,
    anchor_table_digest,
    lexical_anchors,
    missing_anchors,
    quote_anchors,
    record_forms,
)
from leaveimpact.core.entities import CalendarEvent, Leave, Team
from leaveimpact.core.enums import LeaveKind, LeaveStatus
from leaveimpact.world import prose as world_prose
from tests.unit import world_fixture as w

ALICE = employee_ref(w.ALICE)
DENIZ = employee_ref(w.DENIZ)
TICKET = work_item_ref(w.TICKET)
CLAUSE = clause_ref(w.KAFKA_CLAUSE)
LEXICON = Lexicon(
    [
        SurfaceForm("employee", w.ALICE, "Alice Demir"),
        SurfaceForm("employee", w.DENIZ, "Deniz Kaya"),
        SurfaceForm("work_item", w.TICKET, "Payments: rotate the keys"),
        SurfaceForm(SKILL_KIND, "kafka", "Kafka"),
        SurfaceForm(SKILL_KIND, "go", "Go"),
    ]
)
SKILL = (DENIZ, PredicateName.HAS_SKILL, "kafka")
OWNER = (TICKET, PredicateName.OWNS_WORK_ITEM, DENIZ)
RESPONSIBLE = (CLAUSE, PredicateName.NAMES_RESPONSIBLE, DENIZ)
REQUIRED = (CLAUSE, PredicateName.REQUIRES, w.TWO_KAFKA_EMPLOYEES)


def test_a_quote_keeps_every_group_when_its_carrier_has_no_author() -> None:
    assert quote_anchors(SKILL, LEXICON) == (("Deniz Kaya",), ("Kafka",))
    assert quote_anchors(OWNER, LEXICON) == (("Payments: rotate the keys",), ("Deniz Kaya",))
    assert quote_anchors(RESPONSIBLE, LEXICON) == (("Deniz Kaya",),)
    assert quote_anchors(REQUIRED, LEXICON) == (
        ("2", "two"),
        ("employee", "employees"),
        ("Kafka",),
    )


def test_the_author_may_say_i_wherever_the_statement_names_them() -> None:
    assert quote_anchors(SKILL, LEXICON, author=DENIZ)[0] == ("Deniz Kaya", "I", "my", "me")
    assert quote_anchors(OWNER, LEXICON, author=DENIZ) == (
        ("Payments: rotate the keys",),
        ("Deniz Kaya", "I", "my", "me"),
    )
    assert quote_anchors(RESPONSIBLE, LEXICON, author=DENIZ) == (("Deniz Kaya", "I", "my", "me"),)


def test_another_persons_first_person_anchors_nobody() -> None:
    groups = quote_anchors(SKILL, LEXICON, author=ALICE)
    assert groups == (("Deniz Kaya",), ("Kafka",))
    assert missing_anchors("I have run Kafka in production for years.", groups) == (
        ("Deniz Kaya",),
    )


def test_a_requirement_has_no_first_person() -> None:
    assert quote_anchors(REQUIRED, LEXICON, author=DENIZ) == quote_anchors(REQUIRED, LEXICON)


def test_the_generators_reading_drops_the_authors_group_and_the_quotes_does_not() -> None:
    fact = Fact(
        DENIZ,
        PredicateName.HAS_SKILL,
        "kafka",
        EvidenceRef(Source.JIRA, comment_ref(w.DENIZ_COMMENT)),
        date(2026, 3, 1),
    )
    assert lexical_anchors(fact, LEXICON, first_person=DENIZ) == (("Kafka",),)
    assert len(quote_anchors(SKILL, LEXICON, author=DENIZ)) == 2


def test_presence_is_a_whole_word_whatever_its_case() -> None:
    assert missing_anchors("we moved to KAFKA last year", (("Kafka",),)) == ()
    assert missing_anchors("the Kafkaesque migration", (("Kafka",),)) == (("Kafka",),)
    assert missing_anchors("Gopher tooling, mostly", (("Go",),)) == (("Go",),)
    # One spelling of a group is enough; a group with none is returned whole.
    assert missing_anchors("two engineers", (("2", "two"), ("contractor", "contractors"))) == (
        ("contractor", "contractors"),
    )
    assert missing_anchors("I've done this before", (("Deniz Kaya", "I", "my", "me"),)) == ()
    assert missing_anchors("It is done", (("Deniz Kaya", "I", "my", "me"),)) != ()


def test_a_statement_about_a_thing_the_lexicon_never_held_is_refused() -> None:
    stranger = employee_ref(w.CAN)
    with pytest.raises(ValueError, match="employee emp_031 has no display form"):
        quote_anchors((stranger, PredicateName.HAS_SKILL, "kafka"), LEXICON)
    with pytest.raises(ValueError, match="skill postgres has no display form"):
        quote_anchors((DENIZ, PredicateName.HAS_SKILL, "postgres"), LEXICON)


def test_a_predicate_with_no_row_has_no_quote_anchors() -> None:
    with pytest.raises(ValueError, match="due_on cannot be carried by prose"):
        quote_anchors((TICKET, PredicateName.DUE_ON, date(2026, 3, 1)), LEXICON)


def test_a_returned_record_affords_its_name_or_its_title_and_a_leave_nothing() -> None:
    leave = Leave(
        w.LEAVE,
        w.ALICE,
        date(2026, 9, 15),
        date(2026, 9, 19),
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    )
    assert record_forms(leave) == ()
    assert record_forms(Team(w.TEAM, "Payments")) == (SurfaceForm("team", w.TEAM, "Payments"),)
    event = CalendarEvent(w.RELEASE, "Release review", w.RELEASE_SPAN.start, w.RELEASE_SPAN.end, ())
    assert record_forms(event) == (SurfaceForm("event", w.RELEASE, "Release review"),)


def test_the_worlds_names_are_the_moved_objects() -> None:
    for name in ("Lexicon", "SurfaceForm", "Anchor", "lexical_anchors", "NUMBER_WORDS"):
        assert getattr(world_prose, name) is getattr(core_anchors, name)
    assert frozenset(ANCHOR_ROWS) == world_prose.PROSE_CAPABLE


def test_the_tables_digest_is_pinned() -> None:
    # A changed row, spelling, first-person word or presence rule is a changed registration:
    # this value moves only with a deliberate change to the guard.
    assert anchor_table_digest() == (
        "108ae9635f548534d78624b6c241ce194b2d07609fabecfdbd2ef4b07cc76350"
    )
