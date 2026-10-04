"""The parser of a model's fact entries: what reads, and which reason each unreadable entry
is kept under, the raw input whole beside it."""

import json

import pytest

from leaveimpact.agent.fact_entries import ENTRY_SCHEMA, parse_entry, parse_payload, refused_by
from leaveimpact.core import EmploymentType, PredicateName, clause_ref, comment_ref, employee_ref
from leaveimpact.core.ids import clause_id, comment_id, employee_id, skill_id
from leaveimpact.core.stated import STATED_PREDICATES, FactRefusal, RefusedInput, StatedFact
from leaveimpact.core.values import EmploymentTypeCriterion, Requirement, SkillCriterion

SKILL: dict[str, object] = {
    "carrier": "comment_005",
    "predicate": "has_skill",
    "subject": "emp_023",
    "value": "kafka",
    "quote": "I ran the Kafka migration",
}
QUOTE = (
    "The Billing: rotate the signing keys release needs two engineers with TypeScript "
    "experience, each an employee of the company."
)
REQUIRES: dict[str, object] = {
    "carrier": "clause_001",
    "predicate": "requires",
    "subject": "clause_001",
    "value": "",
    "count": 2,
    "skills": ["typescript"],
    "employment_type": "employee",
    "quote": QUOTE,
    "target_span": "Billing: rotate the signing keys",
}


def refusal(entry: object) -> FactRefusal:
    parsed = parse_entry(entry)
    assert isinstance(parsed, RefusedInput), parsed
    # The raw input is kept whole, as JSON that reads back to the entry.
    assert json.loads(parsed.raw) == entry
    return parsed.reason


def test_a_skill_entry_reads_as_the_stated_fact() -> None:
    assert parse_entry(SKILL) == StatedFact(
        PredicateName.HAS_SKILL,
        employee_ref(employee_id(23)),
        skill_id("kafka"),
        comment_ref(comment_id(5)),
        "I ran the Kafka migration",
    )


def test_a_requirement_entry_as_the_span_probes_model_wrote_it() -> None:
    clause = clause_ref(clause_id(1))
    assert parse_entry(REQUIRES) == StatedFact(
        PredicateName.REQUIRES,
        clause,
        Requirement(
            2,
            (
                SkillCriterion(skill_id("typescript")),
                EmploymentTypeCriterion(EmploymentType.EMPLOYEE),
            ),
        ),
        clause,
        QUOTE,
        "Billing: rotate the signing keys",
    )
    # No skill and no employment type is a requirement about number alone.
    bare = {k: v for k, v in REQUIRES.items() if k not in ("skills", "employment_type")}
    parsed = parse_entry(bare)
    assert isinstance(parsed, StatedFact) and parsed.value == Requirement(2, ())


@pytest.mark.parametrize(
    "entry",
    [
        "Deniz knows Kafka",
        ["has_skill", "emp_023", "kafka"],
        {k: v for k, v in SKILL.items() if k != "quote"},
        {**SKILL, "quote": 7},
        {**SKILL, "predicate": "knows"},
        {**SKILL, "predicate": "on_leave"},
        {**SKILL, "subject": "ticket_042"},
        {**SKILL, "subject": "Deniz Kaya"},
        {**SKILL, "value": "Kafka"},
        {**SKILL, "quote": ""},
        {**SKILL, "predicate": "member_of_component", "value": "Payments"},
        # A section cannot carry component membership: outside the evidence domain.
        {**SKILL, "predicate": "member_of_component", "value": "comp_001", "carrier": "clause_001"},
        {**REQUIRES, "count": 0},
        {**REQUIRES, "count": True},
        {**REQUIRES, "count": "two"},
        {k: v for k, v in REQUIRES.items() if k != "count"},
        {**REQUIRES, "skills": "typescript"},
        {**REQUIRES, "skills": [3]},
        {**REQUIRES, "skills": ["typescript", "typescript"]},
        {**REQUIRES, "employment_type": "intern"},
        {**REQUIRES, "target_span": 4},
        {**REQUIRES, "subject": "clause_002"},
    ],
)
def test_an_entry_with_no_reading_is_undecodable(entry: object) -> None:
    assert refusal(entry) is FactRefusal.UNDECODABLE


@pytest.mark.parametrize(
    "carrier",
    ["doc_003", "ticket_042", "emp_023", "the runbook", "", "comment", "clause-1", "comment_5"],
)
def test_a_carrier_that_is_no_comment_or_section_id_is_its_own_reason(carrier: str) -> None:
    assert refusal({**SKILL, "carrier": carrier}) is FactRefusal.MALFORMED_CARRIER
    # The probe's commonest unreadable entry: a requirement carried by its document's id.
    assert (
        refusal({**REQUIRES, "carrier": "doc_003", "subject": "doc_003"})
        is FactRefusal.MALFORMED_CARRIER
    )


@pytest.mark.parametrize("span", [None, "", "Billing: rotate the keys", "billing: rotate"])
def test_a_requirement_without_a_span_inside_its_quote(span: str | None) -> None:
    entry = {k: v for k, v in REQUIRES.items() if k != "target_span"}
    if span is not None:
        entry["target_span"] = span
    assert refusal(entry) is FactRefusal.SPAN_NOT_IN_QUOTE


def test_fields_a_predicate_does_not_use_are_not_read() -> None:
    noise: dict[str, object] = {"count": 1, "skills": [], "target_span": "", "employment_type": "x"}
    noisy = {**SKILL, **noise}
    assert parse_entry(noisy) == parse_entry(SKILL)
    # A requirement's ``value`` is left empty by the model and is not read either.
    assert parse_entry({**REQUIRES, "value": "two engineers"}) == parse_entry(REQUIRES)


def test_a_payload_is_read_entry_by_entry_in_the_order_stated() -> None:
    parsed = parse_payload({"facts": [SKILL, "noise", REQUIRES]})
    assert parsed is not None
    assert [type(entry).__name__ for entry in parsed] == [
        "StatedFact",
        "RefusedInput",
        "StatedFact",
    ]
    # A later valid entry for a statement refused before it is read like any other.
    again = parse_payload({"facts": [{**SKILL, "value": "Kafka"}, SKILL]})
    assert again is not None and isinstance(again[1], StatedFact)


@pytest.mark.parametrize("payload", [None, [], "facts", {"fact": []}, {"facts": {"0": SKILL}}])
def test_a_payload_that_is_no_batch_is_left_to_the_caller(payload: object) -> None:
    assert parse_payload(payload) is None


def test_the_schema_names_the_stated_predicates_and_the_refusal_names_the_parser() -> None:
    items = ENTRY_SCHEMA["properties"]["facts"]["items"]  # type: ignore[index]
    assert items["properties"]["predicate"]["enum"] == [p.value for p in STATED_PREDICATES]
    assert refused_by().parser == "fact-entries-1"
    assert len(refused_by().schema_digest) == 64


def test_an_entry_holding_a_lone_surrogate_is_refused_with_a_raw_text_that_can_be_written() -> None:
    # What ``json.loads`` makes of a model's unpaired escape. A stated fact built from it
    # could not be encoded into an export, so no fact is built, whatever else it says.
    entry = json.loads(
        '{"carrier":"comment_005","predicate":"has_skill","subject":"emp_023",'
        '"value":"kafka","quote":"I ran \\ud83d the Kafka migration"}'
    )
    parsed = parse_entry(entry)
    assert isinstance(parsed, RefusedInput) and parsed.reason is FactRefusal.UNDECODABLE
    assert parsed.raw.encode("utf-8") and json.loads(parsed.raw) == entry
    refused_anyway = parse_entry({**entry, "predicate": "knows"})
    assert isinstance(refused_anyway, RefusedInput)
    assert refused_anyway.raw.encode("utf-8")


def test_an_optional_field_left_null_or_empty_is_absent() -> None:
    bare = {k: v for k, v in REQUIRES.items() if k not in ("skills", "employment_type")}
    number_alone = parse_entry(bare)
    assert parse_entry({**bare, "skills": None}) == number_alone
    assert parse_entry({**bare, "employment_type": None}) == number_alone
    assert parse_entry({**bare, "employment_type": ""}) == number_alone
