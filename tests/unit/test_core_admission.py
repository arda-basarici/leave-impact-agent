"""The five gates of admission, each on a statement only it refuses, in the order they are
asked, over reads a run made."""

from leaveimpact.core import PredicateName, component_ref, employee_ref
from leaveimpact.core.admission import admit, carriers_read, run_lexicon
from leaveimpact.core.anchors import SKILL_KIND
from leaveimpact.core.ids import SkillId, component_id, employee_id, skill_id
from leaveimpact.core.skills import SKILLS
from leaveimpact.core.stated import Admitted, FactRefusal, Refused, StatedFact
from leaveimpact.core.values import Requirement, SkillCriterion
from tests.unit import stated_fixture as f

KAFKA = skill_id("kafka")
DENIZ_KNOWS_KAFKA = StatedFact(
    PredicateName.HAS_SKILL, f.DENIZ_REF, KAFKA, f.COMMENT_REF, "I ran the Kafka migration"
)
NEEDS_TWO = StatedFact(
    PredicateName.REQUIRES,
    f.CLAUSE_REF,
    Requirement(2, (SkillCriterion(KAFKA),)),
    f.CLAUSE_REF,
    f"The {f.TITLE} release needs two people with Kafka experience.",
    f.TITLE,
)


def decided(stated: StatedFact, **reads: object) -> Admitted | Refused:
    projection = f.reads_of(**reads)  # type: ignore[arg-type]
    return admit(stated, projection, run_lexicon(projection))


def refusal(stated: StatedFact, **reads: object) -> FactRefusal:
    result = decided(stated, **reads)
    assert isinstance(result, Refused), result
    assert result.fact == stated
    return result.reason


def test_a_first_person_quote_from_its_authors_comment_is_admitted() -> None:
    assert decided(DENIZ_KNOWS_KAFKA) == Admitted(DENIZ_KNOWS_KAFKA)


def test_a_carrier_no_read_returned_refuses_the_statement() -> None:
    assert refusal(NEEDS_TWO, documents=()) is FactRefusal.CARRIER_NOT_READ


def test_a_quote_that_is_not_in_the_carrier_as_read() -> None:
    reworded = StatedFact(
        PredicateName.HAS_SKILL, f.DENIZ_REF, KAFKA, f.COMMENT_REF, "I ran the kafka migration"
    )
    # Exact, with no normalization: one letter's case is another text.
    assert refusal(reworded) is FactRefusal.QUOTE_NOT_IN_CARRIER


def test_a_subject_the_run_never_read() -> None:
    stranger = StatedFact(
        PredicateName.HAS_SKILL,
        employee_ref(employee_id(99)),
        KAFKA,
        f.COMMENT_REF,
        "I ran the Kafka migration",
    )
    assert refusal(stranger) is FactRefusal.SUBJECT_NOT_READ


def test_a_value_the_run_has_no_form_for() -> None:
    unknown_skill = StatedFact(
        PredicateName.HAS_SKILL,
        f.DENIZ_REF,
        SkillId("cobol"),
        f.COMMENT_REF,
        "I ran the Kafka migration",
    )
    unread_component = StatedFact(
        PredicateName.MEMBER_OF_COMPONENT,
        f.DENIZ_REF,
        component_ref(component_id(9)),
        f.COMMENT_REF,
        "I ran the Kafka migration",
    )
    asks_for_cobol = StatedFact(
        PredicateName.REQUIRES,
        f.CLAUSE_REF,
        Requirement(2, (SkillCriterion(SkillId("cobol")),)),
        f.CLAUSE_REF,
        NEEDS_TWO.quote,
        f.TITLE,
    )
    for stated in (unknown_skill, unread_component, asks_for_cobol):
        assert refusal(stated) is FactRefusal.VALUE_NOT_READ


def test_a_quote_that_does_not_name_who_the_fact_is_about() -> None:
    # Deniz's words, read as a fact about Alice: the first person anchors the author only.
    about_alice = StatedFact(
        PredicateName.HAS_SKILL, f.ALICE_REF, KAFKA, f.COMMENT_REF, "I ran the Kafka migration"
    )
    result = decided(about_alice)
    assert isinstance(result, Refused)
    assert result.reason is FactRefusal.MISSING_ANCHOR
    assert "Alice Demir" in result.detail
    # And one that names the person and not the skill.
    no_skill = StatedFact(
        PredicateName.HAS_SKILL, f.DENIZ_REF, KAFKA, f.COMMENT_REF, "can take this one"
    )
    assert refusal(no_skill) is FactRefusal.MISSING_ANCHOR


def test_a_requirement_needs_its_count_and_its_skill_in_the_quote() -> None:
    assert decided(NEEDS_TWO) == Admitted(NEEDS_TWO)
    three = StatedFact(
        PredicateName.REQUIRES,
        f.CLAUSE_REF,
        Requirement(3, (SkillCriterion(KAFKA),)),
        f.CLAUSE_REF,
        NEEDS_TWO.quote,
        f.TITLE,
    )
    assert refusal(three) is FactRefusal.MISSING_ANCHOR


def test_the_gates_are_asked_in_order_and_one_reason_is_given() -> None:
    # Wrong on every count that needs a read: the carrier is the reason.
    everything = StatedFact(
        PredicateName.HAS_SKILL,
        employee_ref(employee_id(99)),
        SkillId("cobol"),
        f.COMMENT_REF,
        "words the comment does not hold",
    )
    assert refusal(everything, work_items=()) is FactRefusal.CARRIER_NOT_READ
    assert refusal(everything) is FactRefusal.QUOTE_NOT_IN_CARRIER


def test_a_requirement_is_admitted_before_its_target_is_read() -> None:
    # The ticket the clause names was never read. That is the binding's business at
    # composition, and no gate's: the requirement enters on its own carrier and quote.
    assert decided(NEEDS_TWO, work_items=()) == Admitted(NEEDS_TWO)


def test_a_later_read_does_not_rescue_a_refusal_and_a_restatement_is_admitted() -> None:
    before, after = f.reads_of(documents=()), f.reads_of()
    first = admit(NEEDS_TWO, before, run_lexicon(before))
    assert isinstance(first, Refused)
    # The refusal stands as decided; the same statement made after the read is admitted.
    assert admit(NEEDS_TWO, after, run_lexicon(after)) == Admitted(NEEDS_TWO)


def test_the_lexicon_holds_the_public_skills_and_what_the_run_read_and_nothing_else() -> None:
    reads = f.reads_of()
    forms = {(form.kind, form.id): form.form for form in run_lexicon(reads).forms()}
    skills = {(SKILL_KIND, skill.id): skill.name for skill in SKILLS}
    read = {
        ("employee", f.ALICE.id): f.ALICE.name,
        ("employee", f.DENIZ.id): f.DENIZ.name,
        ("component", f.PAYMENTS.id): f.PAYMENTS.name,
        ("work_item", f.TICKET.id): f.TITLE,
        ("document", f.RUNBOOK.id): f.RUNBOOK.title,
    }
    assert forms == skills | read


def test_the_carriers_are_the_comments_and_sections_of_what_was_returned() -> None:
    carriers = carriers_read(f.reads_of())
    assert set(carriers) == {f.COMMENT_REF, f.CLAUSE_REF}
    assert carriers[f.COMMENT_REF].author == f.DENIZ_REF
    assert carriers[f.COMMENT_REF].text == f.COMMENT.text
    assert carriers[f.CLAUSE_REF].author is None


def test_a_returned_record_with_a_blank_title_has_no_form_and_stops_nothing() -> None:
    from dataclasses import replace

    from leaveimpact.core.refs import work_item_ref

    blank = replace(f.TICKET, title="  ")
    reads = f.reads_of(work_items=(blank,))
    lexicon = run_lexicon(reads)
    assert lexicon.alias("work_item", blank.id) is None
    # A statement about the ticket is refused for the anchor nothing could meet.
    owner = StatedFact(
        PredicateName.OWNS_WORK_ITEM,
        work_item_ref(blank.id),
        f.DENIZ_REF,
        f.CLAUSE_REF,
        f"Deniz Kaya owns {f.TITLE}.",
    )
    result = admit(owner, reads, lexicon)
    assert isinstance(result, Refused) and result.reason is FactRefusal.MISSING_ANCHOR
    # And a statement that never names the ticket is admitted as before.
    assert admit(DENIZ_KNOWS_KAFKA, reads, lexicon) == Admitted(DENIZ_KNOWS_KAFKA)
