"""Prompt policy: the assets load with the digests the version module pins; the writer's message
lays out the brief — register, author and ticket for a comment, the facts as plain phrases, the
names, dates and numbers, the length — and the checker's message carries the entity list and the
value forms and never the brief's facts; the tool schema enumerates the registry; the parse of a
filled tool yields propositions, an unlisted subject reads as unknown, and a malformed entry is
the checker's protocol failure."""

import pytest

from leaveimpact.core import EntityRef, PredicateName, Requirement, clause_ref
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.predicates import ROWS
from leaveimpact.generator.prose import (
    TOOL_NAME,
    ExtractionMalformed,
    checker_request,
    load_prompt_assets,
    parse_extraction,
    tool_schema,
    writer_request,
)
from leaveimpact.world import Brief, CommentTarget, Register, SectionTarget, lexicon_of
from leaveimpact.world.briefs import target_ref
from leaveimpact.world.prose import AssertionMode, Polarity, statement_of
from leaveimpact.world.version import PROMPT_DIGESTS
from tests.unit.prose_fixture import KAFKA, ORG, ContactInNote, SkillInComment, pending_scenario

ASSETS = load_prompt_assets()


@pytest.fixture(scope="module")
def brief() -> Brief:
    [brief] = pending_scenario(SkillInComment(context=True)).briefs
    return brief


def test_the_assets_load_and_match_the_pinned_digests() -> None:
    assert ASSETS.digests() == tuple(sorted(PROMPT_DIGESTS.items())), (
        "a prompt asset changed: re-pin PROMPT_DIGESTS in world/version.py deliberately, since "
        "the prompt is identity-bearing provenance of every world written under it"
    )
    for register in Register:
        assert ASSETS.register(register).strip()
    with pytest.raises(ValueError, match="no prompt asset named 'nope'"):
        ASSETS.text("nope")


def test_the_writer_is_told_the_brief_and_nothing_the_guards_will_not_enforce(brief: Brief) -> None:
    assert isinstance(brief.target, CommentTarget)
    lexicon = lexicon_of(ORG)
    request = writer_request(brief, lexicon, ASSETS)
    author = brief.namespace.form_of("employee", brief.target.author_id)
    assert request.system == ASSETS.text("writer_system")
    assert f"You are {author}, commenting on the ticket" in request.message
    assert f"{author} has experience with Kafka" in request.message
    assert f"{author} has experience with Python" in request.message
    assert "Event Ingestion: migrate the retry queue (work item)" in request.message
    assert f"- {author.split()[0]} (given name)" in request.message
    assert "Dates you may write (as YYYY-MM-DD): none" in request.message
    assert "Numbers you may write: none" in request.message
    assert "Length: one to three sentences." in request.message
    assert "ticket in the issue tracker" in request.message  # the register fragment
    assert request.inference.temperature > 0


def test_the_checker_sees_the_entity_list_and_value_forms_and_never_the_facts(brief: Brief) -> None:
    request = checker_request("Some text.", brief, ASSETS)
    assert request.system == ASSETS.text("checker_system")
    assert "- kafka: Kafka (skill)" in request.message
    assert "- unknown: any person or thing the text names that is not listed" in request.message
    assert (
        "- has_skill: about employee; value is the skill's id from the entity list"
        in request.message
    )
    assert "has experience with" not in request.message  # no fact phrase reaches the checker
    assert request.message.endswith("The text:\nSome text.")
    assert isinstance(brief.target, CommentTarget)
    author = brief.namespace.form_of("employee", brief.target.author_id)
    assert request.message.startswith(
        f"The text is a comment written by {author} ({brief.target.author_id}) on the ticket"
    )
    assert f"a first-person statement in it is about {author}." in request.message
    [section_brief] = pending_scenario(ContactInNote()).briefs
    sectioned = checker_request("Some text.", section_brief, ASSETS)
    assert sectioned.message.startswith(
        'The text is a section of the document "Acme account notes".'
    )
    assert request.tool.name == TOOL_NAME
    assert request.inference.temperature == 0


def test_the_tool_schema_enumerates_every_registered_predicate() -> None:
    schema = tool_schema()
    items = schema["properties"]["propositions"]["items"]  # type: ignore[index]
    assert items["properties"]["predicate"]["enum"] == [row.name.value for row in ROWS]  # type: ignore[index]
    assert schema["required"] == ["propositions", "other_claims"]


def test_a_filled_tool_parses_into_propositions_with_unlisted_subjects_unknown(
    brief: Brief,
) -> None:
    assert isinstance(brief.target, CommentTarget)
    who = brief.target.author_id
    filled: JsonObject = {
        "propositions": [
            {
                "subject": who,
                "predicate": "has_skill",
                "value": KAFKA,
                "polarity": "affirmed",
                "mode": "asserted",
            },
            {
                "subject": "emp_999",
                "predicate": "has_skill",
                "value": "go",
                "polarity": "affirmed",
                "mode": "hedged",
            },
            {
                "subject": "unknown",
                "predicate": "has_skill",
                "value": "go",
                "polarity": "negated",
                "mode": "asserted",
            },
        ],
        "other_claims": ["the release needs sign-off from legal"],
    }
    extraction = parse_extraction(filled, brief.namespace, target_ref(brief.target))
    first, second, third = extraction.propositions
    assert first.subject is not None and first.subject.id == who
    assert first.statement is not None and first.predicate is PredicateName.HAS_SKILL
    assert second.subject is None and second.assertion_mode is AssertionMode.HEDGED
    assert third.subject is None and third.polarity is Polarity.NEGATED
    assert extraction.unknown_subjects == 2
    assert extraction.other_claims == ("the release needs sign-off from legal",)


def test_a_requirement_value_parses_through_the_same_spec_a_fact_uses(brief: Brief) -> None:
    filled: JsonObject = {
        "propositions": [
            {
                "subject": "unknown",
                "predicate": "requires",
                "value": {"count": 2, "skills": [KAFKA], "employment_type": "employee"},
                "polarity": "affirmed",
                "mode": "asserted",
            }
        ],
        "other_claims": [],
    }
    [read] = parse_extraction(filled, brief.namespace, target_ref(brief.target)).propositions
    assert read.predicate is PredicateName.REQUIRES
    assert isinstance(read.value, Requirement) and read.value.count == 2


def test_a_malformed_entry_is_the_checkers_protocol_failure(brief: Brief) -> None:
    good: JsonObject = {
        "subject": "unknown",
        "predicate": "has_skill",
        "value": KAFKA,
        "polarity": "affirmed",
        "mode": "asserted",
    }
    cases: list[tuple[JsonObject, str]] = [
        ({"propositions": "not a list", "other_claims": []}, "the tool input"),
        ({"propositions": [{**good, "predicate": "knows"}], "other_claims": []}, "a proposition"),
        (
            {"propositions": [{k: v for k, v in good.items() if k != "mode"}], "other_claims": []},
            "mode is missing",
        ),
        (
            {"propositions": [{**good, "value": "Kafka"}], "other_claims": []},
            "has_skill: a skill id is a lower-case vocabulary key",
        ),
        (
            {"propositions": [{**good, "value": 3}], "other_claims": []},
            "has_skill: expected a string",
        ),
        ({"propositions": [], "other_claims": [3]}, "an item of other_claims is a string"),
    ]
    for broken, reason in cases:
        with pytest.raises(ExtractionMalformed, match=reason):
            parse_extraction(broken, brief.namespace, target_ref(brief.target))


def test_a_carrier_subject_proposition_is_bound_to_the_target_by_construction() -> None:
    """The section names the leaver: the model cannot name the section it is reading, so the
    parser binds the subject to the target; read from a comment, the kinds disagree and the
    subject stays unknown."""
    [section_brief] = pending_scenario(ContactInNote()).briefs
    assert isinstance(section_brief.target, SectionTarget)
    leaver = section_brief.required[0].fact.value
    assert isinstance(leaver, EntityRef)
    filled: JsonObject = {
        "propositions": [
            {
                "subject": "unknown",
                "predicate": "names_responsible",
                "value": leaver.id,
                "polarity": "affirmed",
                "mode": "asserted",
            }
        ],
        "other_claims": [],
    }
    section = target_ref(section_brief.target)
    [read] = parse_extraction(filled, section_brief.namespace, section).propositions
    assert read.subject == clause_ref(section_brief.target.id)
    assert read.statement in {statement_of(f) for f in section_brief.required_facts}
    [comment_brief] = pending_scenario(SkillInComment()).briefs
    comment = target_ref(comment_brief.target)
    [misread] = parse_extraction(filled, comment_brief.namespace, comment).propositions
    assert misread.subject is None
