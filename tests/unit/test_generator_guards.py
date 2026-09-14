"""The three guards over the fixture brief — a comment whose author must state their own Kafka
experience. The namespace scanner admits allowed names in any case, refuses another world name in
exact spelling, refuses an unlisted ISO date, any other date spelling and an unlisted number, and
keeps a digit inside an allowed title; the required-fact check refuses a text that dropped an
anchor; the containment check refuses an unknown subject, a negation, a hedge, an unsupported
statement, a required statement not read as asserted, and any other claim."""

import pytest

from leaveimpact.core import PredicateName, employee_ref
from leaveimpact.generator.guards import (
    containment_findings,
    namespace_findings,
    required_fact_findings,
)
from leaveimpact.generator.prose import Extraction
from leaveimpact.world import Brief, CommentTarget, lexicon_of
from leaveimpact.world.prose import AssertionMode, Lexicon, Polarity, Proposition, SurfaceForm
from tests.unit.prose_fixture import KAFKA, ORG, SkillInComment, pending_scenario


@pytest.fixture(scope="module")
def brief() -> Brief:
    [brief] = pending_scenario(SkillInComment()).briefs
    return brief


@pytest.fixture(scope="module")
def lexicon() -> Lexicon:
    scenario = pending_scenario(SkillInComment())
    return lexicon_of(ORG, [p.entity for p in scenario.owned.work_items])


@pytest.fixture(scope="module")
def world_forms(lexicon: Lexicon) -> tuple[SurfaceForm, ...]:
    return lexicon.forms()


def author_of(brief: Brief) -> str:
    assert isinstance(brief.target, CommentTarget)
    return brief.namespace.form_of("employee", brief.target.author_id)


def stranger(brief: Brief) -> str:
    """The display name of an employee the brief does not admit."""
    allowed = {form.id for form in brief.namespace.forms if form.kind == "employee"}
    return next(e.name for e in ORG.employees if e.id not in allowed)


# --- The namespace scanner ----------------------------------------------------------------


def test_allowed_names_pass_in_any_case_and_a_digit_inside_an_allowed_title_passes(
    brief: Brief, world_forms: tuple[SurfaceForm, ...]
) -> None:
    text = f"I ({author_of(brief).upper()}) took the kafka part of the retry queue work."
    assert namespace_findings(text, brief, world_forms) == ()
    titled = 'On "Event Ingestion: migrate the retry queue" I handled the Kafka side.'
    assert namespace_findings(titled, brief, world_forms) == ()


def test_another_world_name_is_refused_in_any_case_by_full_or_given_name(
    brief: Brief, world_forms: tuple[SurfaceForm, ...]
) -> None:
    other = stranger(brief)
    refused = namespace_findings(f"{other} and I ran the Kafka side.", brief, world_forms)
    assert len(refused) == 1 and "names employee" in refused[0]
    lowered_text = f"thanks {other.lower()}. I ran the Kafka side."
    [lowered] = namespace_findings(lowered_text, brief, world_forms)
    assert "names employee" in lowered
    [given] = namespace_findings(f"thanks {other.split()[0]}, Kafka is done.", brief, world_forms)
    assert "names given_name" in given
    mine = author_of(brief).split()[0]
    assert namespace_findings(f"{mine} here, Kafka is done.", brief, world_forms) == ()


def test_an_allowed_short_form_cannot_erase_a_longer_foreign_form_it_sits_inside(
    brief: Brief, world_forms: tuple[SurfaceForm, ...]
) -> None:
    given = author_of(brief).split()[0]
    foreign = SurfaceForm("employee", "emp_999", f"{given} Kowalski")
    text = f"thanks {given} Kowalski, Kafka is in."
    [refused] = namespace_findings(text, brief, (*world_forms, foreign))
    assert "names employee emp_999" in refused
    assert namespace_findings(f"thanks {given}, Kafka is in.", brief, (*world_forms, foreign)) == ()


def test_a_short_world_form_matches_only_in_exact_spelling(
    brief: Brief, world_forms: tuple[SurfaceForm, ...]
) -> None:
    assert any(form.form == "Go" for form in world_forms)  # the skill, not in this brief
    assert namespace_findings("We go live with Kafka tomorrow.", brief, world_forms) == ()
    [refused] = namespace_findings("Kafka and Go are both mine.", brief, world_forms)
    assert "names skill go" in refused


def test_dates_and_numbers_outside_the_brief_are_refused(
    brief: Brief, world_forms: tuple[SurfaceForm, ...]
) -> None:
    assert brief.namespace.dates == () and brief.namespace.numbers == ()
    for text, finding in (
        ("Kafka went live on 2026-03-01.", "date 2026-03-01 not listed"),
        ("Kafka went live on March 1st.", "date spelled other than YYYY-MM-DD"),
        ("Kafka went live on 1/3/2026.", "date spelled other than YYYY-MM-DD"),
        ("Kafka needs 3 people.", "number 3 not listed"),
    ):
        findings = namespace_findings(text, brief, world_forms)
        assert len(findings) == 1 and finding in findings[0], text
    assert (
        namespace_findings("Kafka needs three people.", brief, world_forms) == ()
    )  # the extractor's


# --- The required-fact check ---------------------------------------------------------------


def test_a_text_that_dropped_an_anchor_is_refused_before_the_checker_is_paid(
    brief: Brief, lexicon: Lexicon
) -> None:
    author = author_of(brief)
    assert (
        required_fact_findings(f"{author} here: I have run KAFKA in production.", brief, lexicon)
        == ()
    )
    [finding] = required_fact_findings(
        f"{author} here: I have run the streaming stack.", brief, lexicon
    )
    assert "has_skill" in finding and "Kafka" in finding


def test_a_comments_author_is_its_first_person_and_never_an_anchor(
    brief: Brief, lexicon: Lexicon
) -> None:
    """The first measurement world refused every attempt for the author's missing name: a
    fact about the author is anchored on its value alone."""
    spoken = "I've run Kafka in production for two years."
    assert required_fact_findings(spoken, brief, lexicon) == ()
    [finding] = required_fact_findings("I've run the streaming stack.", brief, lexicon)
    assert "Kafka" in finding


# --- The containment check ------------------------------------------------------------------


def read(subject: str | None, value: str, polarity: Polarity, mode: AssertionMode) -> Proposition:
    ref = None if subject is None else employee_ref(subject)  # type: ignore[arg-type]
    return Proposition(ref, PredicateName.HAS_SKILL, value, polarity, mode)


def test_containment_accepts_exactly_the_required_read_as_affirmed_and_asserted(
    brief: Brief,
) -> None:
    who = brief.required_facts[0].subject.id
    clean = Extraction((read(who, KAFKA, Polarity.AFFIRMED, AssertionMode.ASSERTED),), ())
    assert containment_findings(brief, clean) == ()
    for extraction, finding in (
        (Extraction((), ()), "required and not read as asserted"),
        (Extraction((read(who, KAFKA, Polarity.NEGATED, AssertionMode.ASSERTED),), ()), "negated"),
        (Extraction((read(who, KAFKA, Polarity.AFFIRMED, AssertionMode.HEDGED),), ()), "hedged"),
        (
            Extraction((read(None, KAFKA, Polarity.AFFIRMED, AssertionMode.ASSERTED),), ()),
            "subject not in the entity list",
        ),
        (
            Extraction(
                (
                    read(who, KAFKA, Polarity.AFFIRMED, AssertionMode.ASSERTED),
                    read(who, "go", Polarity.AFFIRMED, AssertionMode.ASSERTED),
                ),
                (),
            ),
            "not a required or allowed fact",
        ),
        (
            Extraction(
                (read(who, KAFKA, Polarity.AFFIRMED, AssertionMode.ASSERTED),),
                ("needs legal sign-off",),
            ),
            "other claim",
        ),
    ):
        findings = containment_findings(brief, extraction)
        assert any(finding in f for f in findings), (finding, findings)


def test_an_untyped_proposition_refuses_the_attempt(brief: Brief) -> None:
    extraction = Extraction((), (), (PredicateName.OWNS_WORK_ITEM,))
    findings = containment_findings(brief, extraction)
    assert "owns_work_item: a proposition the checker could not type" in findings
