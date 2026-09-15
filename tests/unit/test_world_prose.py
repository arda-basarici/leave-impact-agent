"""The prose vocabulary: a proposition validated against the registry like a fact; a namespace
derived from facts through the closed vocabulary, with the dates and numbers they carry; the
lexical anchors a fact's text cannot avoid, refused for a predicate prose cannot carry; and the
materialization record's own invariants — one refusal per failed attempt before the accepted
one, attempts under the cap, digests of SHA-256 shape, each target and setting once, prompt
digests in name order."""

from datetime import date

import pytest

from leaveimpact.core import (
    EmploymentType,
    EmploymentTypeCriterion,
    EvidenceRef,
    Fact,
    PredicateName,
    Requirement,
    SkillCriterion,
    Source,
    clause_ref,
    comment_ref,
    component_ref,
    employee_ref,
    work_item_ref,
)
from leaveimpact.core.ids import (
    clause_id,
    comment_id,
    component_id,
    employee_id,
    skill_id,
    work_item_id,
)
from leaveimpact.world import (
    PROSE_CAPABLE,
    AssertionMode,
    GuardName,
    Lexicon,
    MaterializationMetrics,
    MaterializationRecord,
    ModelConfiguration,
    Namespace,
    Polarity,
    Proposition,
    Refusal,
    RefusalReason,
    Setting,
    SurfaceForm,
    TargetRecord,
    derive_namespace,
    lexical_anchors,
    statement_of,
)
from leaveimpact.world.prose import SKILL_KIND

DENIZ = employee_ref(employee_id(23))
COMMENT = comment_ref(comment_id(5))
CLAUSE = clause_ref(clause_id(11))
PAYMENTS = component_ref(component_id(1))
TICKET = work_item_ref(work_item_id(42))
DAY = date(2026, 3, 1)
KAFKA = skill_id("kafka")

LEXICON = Lexicon(
    [
        SurfaceForm("employee", "emp_023", "Deniz Kaya"),
        SurfaceForm(SKILL_KIND, "kafka", "Kafka"),
        SurfaceForm("component", "comp_001", "Payments API"),
        SurfaceForm("work_item", "ticket_042", "Payments API: rotate the signing keys"),
    ]
)

KAFKA_IN_COMMENT = Fact(
    DENIZ, PredicateName.HAS_SKILL, KAFKA, EvidenceRef(Source.JIRA, COMMENT), DAY
)
TWO_KAFKA_EMPLOYEES = Fact(
    CLAUSE,
    PredicateName.REQUIRES,
    Requirement(2, (SkillCriterion(KAFKA), EmploymentTypeCriterion(EmploymentType.EMPLOYEE))),
    EvidenceRef(Source.CORPUS, CLAUSE),
    DAY,
)
SHA = "a" * 64


# --- Propositions -----------------------------------------------------------------------


def test_a_proposition_is_validated_against_the_registry_like_a_fact() -> None:
    with pytest.raises(ValueError, match="a skill id is a lower-case vocabulary key"):
        Proposition(
            DENIZ, PredicateName.HAS_SKILL, "Kafka", Polarity.AFFIRMED, AssertionMode.ASSERTED
        )
    with pytest.raises(
        ValueError, match="has_skill is a fact about employee, got a proposition about work_item"
    ):
        Proposition(
            TICKET, PredicateName.HAS_SKILL, KAFKA, Polarity.AFFIRMED, AssertionMode.ASSERTED
        )


def test_a_statement_drops_polarity_mode_evidence_and_date_and_an_unknown_subject_has_none() -> (
    None
):
    read = Proposition(
        DENIZ, PredicateName.HAS_SKILL, KAFKA, Polarity.NEGATED, AssertionMode.HEDGED
    )
    assert read.statement == statement_of(KAFKA_IN_COMMENT)
    unknown = Proposition(
        None, PredicateName.HAS_SKILL, KAFKA, Polarity.AFFIRMED, AssertionMode.ASSERTED
    )
    assert unknown.statement is None


# --- Namespace and lexicon --------------------------------------------------------------


def test_the_namespace_is_derived_from_the_facts_with_their_dates_and_numbers() -> None:
    due = Fact(
        TICKET,
        PredicateName.DUE_ON,
        date(2026, 3, 9),
        EvidenceRef(Source.JIRA, TICKET, "due_on"),
        DAY,
    )
    extra = [SurfaceForm("work_item", "ticket_042", "Payments API: rotate the signing keys")]
    namespace = derive_namespace([KAFKA_IN_COMMENT, TWO_KAFKA_EMPLOYEES, due], LEXICON, extra)
    assert namespace.form_of("employee", "emp_023") == "Deniz Kaya"
    assert namespace.form_of(SKILL_KIND, "kafka") == "Kafka"
    assert namespace.form_of("work_item", "ticket_042").startswith("Payments API")
    assert namespace.dates == (date(2026, 3, 9),)
    assert namespace.numbers == (2,)
    with pytest.raises(ValueError, match="component comp_001 is outside the namespace"):
        namespace.form_of("component", "comp_001")


def test_a_namespace_names_each_thing_once_and_keeps_dates_and_numbers_sorted() -> None:
    form = SurfaceForm("employee", "emp_023", "Deniz Kaya")
    with pytest.raises(ValueError, match="names each entity once"):
        Namespace((form, form), (), ())
    with pytest.raises(ValueError, match="dates are sorted and unique"):
        Namespace((), (date(2026, 3, 2), date(2026, 3, 1)), ())
    with pytest.raises(ValueError, match="numbers are sorted and unique"):
        Namespace((), (), (2, 2))


def test_a_lexicon_refuses_two_display_forms_for_one_thing_and_names_the_unknown() -> None:
    with pytest.raises(ValueError, match="employee emp_023 has two display forms"):
        Lexicon(
            [
                SurfaceForm("employee", "emp_023", "Deniz"),
                SurfaceForm("employee", "emp_023", "Deniz K"),
            ]
        )
    with pytest.raises(ValueError, match="employee emp_999 has no display form in this world"):
        LEXICON.form_of(employee_ref(employee_id(999)))


# --- Lexical anchors ----------------------------------------------------------------------


def test_anchors_name_the_person_and_the_skill_for_a_skill_fact() -> None:
    assert lexical_anchors(KAFKA_IN_COMMENT, LEXICON) == (("Deniz Kaya",), ("Kafka",))


def test_anchors_for_a_requirement_admit_either_spelling_of_the_count() -> None:
    # Criteria sit in the requirement's canonical order: employment type before skill.
    assert lexical_anchors(TWO_KAFKA_EMPLOYEES, LEXICON) == (
        ("2", "two"),
        ("employee", "employees"),
        ("Kafka",),
    )


def test_anchors_for_an_ownership_fact_name_the_ticket_and_the_owner() -> None:
    owner = Fact(
        TICKET, PredicateName.OWNS_WORK_ITEM, DENIZ, EvidenceRef(Source.CORPUS, CLAUSE), DAY
    )
    assert lexical_anchors(owner, LEXICON) == (
        ("Payments API: rotate the signing keys",),
        ("Deniz Kaya",),
    )


def test_a_predicate_without_an_anchor_row_cannot_be_carried_by_prose() -> None:
    due = Fact(TICKET, PredicateName.DUE_ON, DAY, EvidenceRef(Source.JIRA, TICKET, "due_on"), DAY)
    assert PredicateName.DUE_ON not in PROSE_CAPABLE
    with pytest.raises(ValueError, match="due_on cannot be carried by prose"):
        lexical_anchors(due, LEXICON)


# --- The materialization record -----------------------------------------------------------


def test_a_refusal_is_numbered_from_one_and_counts_at_least_one_finding() -> None:
    with pytest.raises(ValueError, match="numbered from one"):
        Refusal(0, GuardName.NAMESPACE, 1)
    with pytest.raises(ValueError, match="at least one finding"):
        Refusal(1, GuardName.NAMESPACE, 0)


def test_a_refusals_reasons_account_for_every_finding_once_in_reason_order() -> None:
    """``None`` is a refusal sealed before reasons were recorded, distinct from any count."""
    assert Refusal(1, GuardName.EXTRACTION, 2).reasons is None
    ordered = Refusal(
        1,
        GuardName.EXTRACTION,
        3,
        ((RefusalReason.UNTYPED_PROPOSITION, 2), (RefusalReason.OTHER_CLAIM, 1)),
    )
    assert ordered.reasons == (
        (RefusalReason.OTHER_CLAIM, 1),
        (RefusalReason.UNTYPED_PROPOSITION, 2),
    )
    with pytest.raises(ValueError, match="account for every finding"):
        Refusal(1, GuardName.EXTRACTION, 3, ((RefusalReason.OTHER_CLAIM, 1),))
    with pytest.raises(ValueError, match="each reason once"):
        Refusal(
            1,
            GuardName.EXTRACTION,
            2,
            ((RefusalReason.OTHER_CLAIM, 1), (RefusalReason.OTHER_CLAIM, 1)),
        )
    with pytest.raises(ValueError, match="at least one finding"):
        Refusal(1, GuardName.EXTRACTION, 1, ((RefusalReason.OTHER_CLAIM, 0),))


def test_a_target_record_is_a_possible_history_one_refusal_per_failed_attempt() -> None:
    TargetRecord(
        "comment_005",
        3,
        (Refusal(1, GuardName.NAMESPACE, 2), Refusal(2, GuardName.EXTRACTION, 1)),
        SHA,
        SHA,
        (),
    )
    impossible = (
        (3, (Refusal(3, GuardName.NAMESPACE, 2),)),  # refused on the accepted attempt
        (4, ()),  # three silent failures
        (3, (Refusal(1, GuardName.NAMESPACE, 1), Refusal(1, GuardName.EXTRACTION, 1))),
        (4, (Refusal(2, GuardName.NAMESPACE, 1),)),  # attempt 1 unaccounted for
    )
    for attempts, refusals in impossible:
        with pytest.raises(ValueError, match="were each refused once in order"):
            TargetRecord("comment_005", attempts, refusals, SHA, SHA, ())
    with pytest.raises(ValueError, match="accepted_body_digest is a SHA-256 hex"):
        TargetRecord("comment_005", 1, (), SHA, "deadbeef", ())


def test_a_model_configuration_orders_its_settings_and_names_each_once() -> None:
    configured = ModelConfiguration(
        "eu.model", (Setting("top_p", 0.9), Setting("temperature", 0.7))
    )
    assert [setting.name for setting in configured.settings] == ["temperature", "top_p"]
    with pytest.raises(ValueError, match="a setting is given once"):
        ModelConfiguration("eu.model", (Setting("temperature", 0.7), Setting("temperature", 0)))


def test_the_record_keeps_attempts_under_the_cap_and_each_target_once() -> None:
    writer = ModelConfiguration("writer", ())
    checker = ModelConfiguration("checker", ())
    refused = tuple(Refusal(n, GuardName.EXTRACTION, 1) for n in (1, 2, 3))
    accepted = TargetRecord("comment_005", 4, refused, SHA, SHA, ())
    record = MaterializationRecord(
        writer, checker, (("writer", SHA), ("checker", SHA)), 4, (accepted,)
    )
    assert record.target_ids == {"comment_005"}
    assert [name for name, _ in record.prompt_digests] == ["checker", "writer"]  # name order
    with pytest.raises(ValueError, match="4 attempts over a cap of 3"):
        MaterializationRecord(writer, checker, (), 3, (accepted,))
    with pytest.raises(ValueError, match="a target is recorded once"):
        MaterializationRecord(writer, checker, (), 4, (accepted, accepted))
    with pytest.raises(ValueError, match="a prompt asset is digested once"):
        MaterializationRecord(writer, checker, (("a", SHA), ("a", SHA)), 4, ())


def test_the_records_counters_are_optional_and_never_negative() -> None:
    writer = ModelConfiguration("writer", ())
    checker = ModelConfiguration("checker", ())
    assert MaterializationRecord(writer, checker, (), 4, ()).metrics is None
    zeros = dict.fromkeys(MaterializationMetrics.__slots__, 0)
    counted = MaterializationMetrics(**{**zeros, "writer_input_tokens": 3209})
    assert MaterializationRecord(writer, checker, (), 4, (), counted).metrics == counted
    with pytest.raises(ValueError, match="checker_latency_ms: a counter is never negative"):
        MaterializationMetrics(**{**zeros, "checker_latency_ms": -1})
