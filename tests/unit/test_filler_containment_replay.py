"""The group 0 containment probe replayed through the built gate: fourteen texts and the checker's
saved readings of them, run through the live scanner and the decoy rule with no model call.

The fixture (``tests/fixtures/filler_containment.json``) is the probe's record of 2026-10-08:
nine hand-written texts and five the live writer wrote, each with the scanner's findings, the
typed propositions, the untyped predicates and the other claims Nova Pro returned, and the
probe's own two-clause verdict. That verdict column is kept as the probe wrote it and is not
what this test asserts: the ``expected`` column is, under the amended rule, so the two texts
the two-clause rule passed and the untyped clause refuses (M2, M3) are the amendment's test.
The probe built its brief by hand with ids numbered 901 and a fictional person; the brief
here is the built constructor's over the same forms with the ids moved into the fictional
range, and the saved ids are moved with them, so the texts and the readings are the probe's
bytes and only the numbering is the built world's. The probe's fictional release wore a
client's name, "Northwind", and passed the scanner only because the longer admitted form is
matched first; the replay keeps that name so the record reproduces, and the vocabulary's own
test is what rules the name out of the generator's book.

Five rows of the third probe round join the fourteen: four contextual references to a
planted person that carry no name ("the employee taking leave is responsible", "their
manager signs off", "the owner of the release approves", "the leaver is not responsible")
and one harmless requirement text, each written against the generator's own first
requirement brief of seed 7's golden world with a six-document pool, so the brief is
rebuilt by minting and not by hand. Their readings carry the checker's unresolved values
apart from the untyped, as the parse does since the external read of 2026-10-08; every
negative must refuse on that reading, which is the deciding evidence the read asked for.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.core import (
    Document,
    DocumentKind,
    EmploymentType,
    EmploymentTypeCriterion,
    EntityKind,
    EntityRef,
    PredicateName,
    Requirement,
    SkillCriterion,
)
from leaveimpact.core.anchors import GIVEN_NAME_KIND, SKILL_KIND, SurfaceForm
from leaveimpact.core.ids import (
    ClauseId,
    DocumentId,
    clause_id,
    document_id,
    employee_id,
    skill_id,
    work_item_id,
)
from leaveimpact.core.jsonshape import (
    array_field,
    as_object,
    field_of,
    integer_field,
    object_field,
    string_field,
    string_item,
)
from leaveimpact.core.predicates import predicate as predicate_row
from leaveimpact.core.values import ValueKind
from leaveimpact.generator.guards import containment_findings, namespace_findings
from leaveimpact.generator.prose import Extraction
from leaveimpact.generator.prose.schema import Unresolved
from leaveimpact.world import (
    DEFAULT_PARAMS,
    FICTIONAL_ID_BASE,
    FillerBrief,
    Register,
    assemble_semantic_world,
    filler_brief_for,
    lexicon_of,
)
from leaveimpact.world.prose import AssertionMode, Polarity, Proposition, RefusalReason
from leaveimpact.world.vocabulary import SKILLS

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "filler_containment.json"
PERSON = employee_id(FICTIONAL_ID_BASE)
RELEASE = work_item_id(FICTIONAL_ID_BASE)
CLAUSE = clause_id(FICTIONAL_ID_BASE)
NOTE = document_id(FICTIONAL_ID_BASE)
RENUMBERED: Mapping[str, str] = {
    "emp_901": PERSON,
    "ticket_901": RELEASE,
    "clause_901": CLAUSE,
    "doc_901": NOTE,
}
Record = Mapping[str, object]


@pytest.fixture(scope="module")
def records() -> dict[str, Record]:
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    labelled = [as_object(row, "a row") for row in rows]  # type: ignore[arg-type]
    return {string_field(row, "label").split()[0]: row for row in labelled}


@pytest.fixture(scope="module")
def world_forms() -> tuple[SurfaceForm, ...]:
    world = assemble_semantic_world(7, DEFAULT_PARAMS, date(2026, 1, 1), "golden")
    return lexicon_of(
        world.org,
        [p.entity for s in world.scenarios for p in s.owned.work_items],
        [p.entity for s in world.scenarios for p in s.owned.documents],
        [p.entity for s in world.scenarios for p in s.owned.events],
    ).forms()


@pytest.fixture(scope="module")
def brief() -> FillerBrief:
    world = assemble_semantic_world(7, DEFAULT_PARAMS, date(2026, 1, 1), "golden")
    document = Document(
        NOTE, "Halcyon account notes", DocumentKind.CLIENT_NOTE, date(2026, 1, 1), ()
    )
    fictional = (
        SurfaceForm(EntityKind.WORK_ITEM.value, RELEASE, "Northwind release"),
        SurfaceForm(EntityKind.EMPLOYEE.value, PERSON, "Mara Quill"),
        SurfaceForm(GIVEN_NAME_KIND, PERSON, "Mara"),
    )
    skills = tuple(
        SurfaceForm(SKILL_KIND, s.id, s.name) for s in SKILLS if s.id in world.org.skills
    )
    return filler_brief_for(document, CLAUSE, 0, Register.FILLER_REQUIREMENT, fictional, skills)


def _ref(data: Record) -> EntityRef:
    id = string_field(data, "id")
    return EntityRef(EntityKind(string_field(data, "kind")), RENUMBERED.get(id, id))


def _value(predicate: PredicateName, raw: object) -> object:
    if predicate is PredicateName.REQUIRES:
        requirement = as_object(raw, "a requirement")
        criteria: list[SkillCriterion | EmploymentTypeCriterion] = []
        for item in array_field(requirement, "criteria"):
            criterion = as_object(item, "a criterion")
            if "skill" in criterion:
                criteria.append(SkillCriterion(skill_id(string_field(criterion, "skill"))))
            else:
                criteria.append(
                    EmploymentTypeCriterion(
                        EmploymentType(string_field(criterion, "employment_type"))
                    )
                )
        return Requirement(integer_field(requirement, "count"), tuple(criteria))
    if predicate_row(predicate).value_spec.kind is ValueKind.ENTITY_REF:
        return _ref(as_object(raw, "an entity value"))
    return raw


def extraction_of(record: Record) -> Extraction:
    """The checker's saved reading rebuilt as the gate reads it, the ids renumbered."""
    propositions: list[Proposition] = []
    for item in array_field(record, "propositions"):
        read = as_object(item, "a proposition")
        predicate = PredicateName(string_field(read, "predicate"))
        raw_subject = field_of(read, "subject")
        subject = None if raw_subject is None else _ref(as_object(raw_subject, "a subject"))
        propositions.append(
            Proposition(
                subject,
                predicate,
                _value(predicate, field_of(read, "value")),  # type: ignore[arg-type]
                Polarity(string_field(read, "polarity")),
                AssertionMode(string_field(read, "assertion_mode")),
            )
        )
    unresolved: list[Unresolved] = []
    for item in array_field(record, "unresolved") if "unresolved" in record else ():
        read = as_object(item, "an unresolved proposition")
        raw_subject = field_of(read, "subject")
        unresolved.append(
            Unresolved(
                None if raw_subject is None else _ref(as_object(raw_subject, "a subject")),
                PredicateName(string_field(read, "predicate")),
                Polarity(string_field(read, "polarity")),
                AssertionMode(string_field(read, "assertion_mode")),
            )
        )
    return Extraction(
        tuple(propositions),
        tuple(string_item(claim, "other_claims") for claim in array_field(record, "other_claims")),
        tuple(
            PredicateName(string_item(name, "untyped")) for name in array_field(record, "untyped")
        ),
        0,
        tuple(unresolved),
    )


def gate(
    record: Record, brief: FillerBrief, world_forms: tuple[SurfaceForm, ...]
) -> tuple[set[RefusalReason], set[RefusalReason]]:
    """The scanner's reasons and the decoy rule's reasons for one saved text."""
    text = string_field(record, "text")
    scanner = {finding.reason for finding in namespace_findings(text, brief, world_forms)}
    decoy = {finding.reason for finding in containment_findings(brief, extraction_of(record))}
    return scanner, decoy


@pytest.mark.parametrize("label", ["N2", "N3"])
def test_the_accepted_texts_pass_the_whole_gate(
    label: str,
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    scanner, decoy = gate(records[label], brief, world_forms)
    assert (scanner, decoy) == (set(), set()), (label, scanner, decoy)
    assert string_field(records[label], "expected").startswith("pass")


@pytest.mark.parametrize("label", ["N1", "F1"])
def test_a_text_with_an_other_claim_now_refuses_on_it(
    label: str,
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # N1 was the handbook composition's shape and F1 a fictional person's review duty the
    # checker could not express; the probe's rule tolerated other claims for the handbook's
    # sake, the composition was dropped and the tolerance with it (the group 2 review), so
    # both now refuse as a planted text would, the scanner still clean.
    scanner, decoy = gate(records[label], brief, world_forms)
    assert scanner == set() and decoy == {RefusalReason.OTHER_CLAIM}, label


def test_an_undeclared_fictional_person_is_an_unknown_subject(
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # The checker also left one proposition untyped on this text; the unknown subject is the
    # clause that names the fault the text was written to show.
    scanner, decoy = gate(records["F2"], brief, world_forms)
    assert scanner == set()
    assert decoy == {RefusalReason.UNKNOWN_SUBJECT, RefusalReason.UNTYPED_PROPOSITION}


@pytest.mark.parametrize("label", ["M1", "M2", "M3", "M4"])
def test_every_must_fail_text_is_refused_and_the_scanner_catches_each_first(
    label: str,
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    scanner, _ = gate(records[label], brief, world_forms)
    assert RefusalReason.FOREIGN_NAME in scanner
    assert string_field(records[label], "expected") == "refused"


def test_the_untyped_clause_alone_refuses_what_the_two_clause_rule_passed(
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # M2 and M3 came back with no typed proposition about the world: the probe's rule passed
    # them and the amendment's clause refuses them, which is what the amendment exists for.
    # M3's one typed proposition is a status of the fictional release, a decoy, and its two
    # other claims are tolerated; the untyped ``on_leave`` is the whole refusal.
    for label, expected in (
        ("M2", {RefusalReason.UNTYPED_PROPOSITION}),
        ("M3", {RefusalReason.UNTYPED_PROPOSITION, RefusalReason.OTHER_CLAIM}),
    ):
        assert string_field(records[label], "decoy_verdict") == "pass"
        _, decoy = gate(records[label], brief, world_forms)
        assert decoy == expected, label
    # M1's real employee is outside the namespace, so the checker wrote an unknown subject,
    # and left a second proposition untyped.
    _, decoy = gate(records["M1"], brief, world_forms)
    assert decoy == {RefusalReason.UNKNOWN_SUBJECT, RefusalReason.UNTYPED_PROPOSITION}


def test_a_planted_title_inside_a_requirement_is_caught_by_the_scanner_alone(
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # Group 0's finding: the checker reads the requirement as the target's own, a decoy in
    # shape, so the deterministic scanner is the sole guard between a planted title and a
    # filler text, and the lexicon holds every planted title by construction.
    scanner, decoy = gate(records["M4"], brief, world_forms)
    assert scanner == {RefusalReason.FOREIGN_NAME} and decoy == set()


@pytest.mark.parametrize("label", ["W1", "W2", "W3", "W4"])
def test_what_the_live_writer_wrote_is_decoy_under_the_rule(
    label: str,
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # The writer given no facts and no instruction invented a person holding every listed
    # skill (W1, W2), all of it about the declared fiction, so the rule passes it: what the
    # register and the filler passage exist to steer is content, not containment.
    _, decoy = gate(records[label], brief, world_forms)
    assert decoy == set(), label


def test_one_writer_text_in_five_fails_the_built_gate_on_an_untyped_proposition(
    records: dict[str, Record],
    brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # W5 stated its requirement (a decoy) and the checker left an ``in_component`` untyped;
    # under the built gate that text is a refused attempt and would be rewritten. The rate
    # on the production rendering is the live re-probe's to measure, not this replay's.
    _, decoy = gate(records["W5"], brief, world_forms)
    assert decoy == {RefusalReason.UNTYPED_PROPOSITION}


# --- Round 3: contextual references to a planted person, and the harmless requirement ---------


@pytest.fixture(scope="module")
def production_brief(records: dict[str, Record]) -> FillerBrief:
    """The brief the round 3 texts were checked against, rebuilt from the record: the generator's
    first requirement brief under the three-book mint of that day, whose draws the two-book mint
    no longer reproduces."""
    recorded = object_field(records["R1"], "brief")
    document = object_field(recorded, "document")
    forms = {
        key: tuple(
            SurfaceForm(
                string_field(as_object(item, key), "kind"),
                string_field(as_object(item, key), "id"),
                string_field(as_object(item, key), "form"),
            )
            for item in array_field(recorded, key)
        )
        for key in ("fictional", "skills")
    }
    return filler_brief_for(
        Document(
            DocumentId(string_field(document, "id")),
            string_field(document, "title"),
            DocumentKind(string_field(document, "kind")),
            date(2026, 1, 1),
            (),
        ),
        ClauseId(string_field(recorded, "clause")),
        0,
        Register(string_field(recorded, "register")),
        forms["fictional"],
        forms["skills"],
    )


@pytest.mark.parametrize("label", ["R1", "R2", "R3", "R4"])
def test_a_contextual_reference_to_a_planted_person_refuses_on_the_unresolved_reading(
    label: str,
    records: dict[str, Record],
    production_brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # No spelling for the scanner, so the checker's unresolved value is the only reading where
    # the reference shows; the gate refuses it under the reason the untyped already carry.
    record = records[label]
    assert string_field(record, "document_id") == production_brief.target.id.replace(
        "clause", "doc"
    )
    scanner, decoy = gate(record, production_brief, world_forms)
    assert scanner == set()
    assert RefusalReason.UNTYPED_PROPOSITION in decoy
    assert array_field(record, "unresolved"), label


def test_a_requirement_text_naming_nobody_passes_every_decoy_clause(
    records: dict[str, Record],
    production_brief: FillerBrief,
    world_forms: tuple[SurfaceForm, ...],
) -> None:
    # H1 states its requirement and then a second sentence about the rollback plan, which the
    # checker filed as an other claim; the decoy clauses pass the text and the other-claim
    # clause, filler's since the group 2 review, refuses it as it would a planted text. The
    # register now asks for the requirement and nothing else, and the production acceptance
    # under that length is the fifth probe round's to measure.
    scanner, decoy = gate(records["H1"], production_brief, world_forms)
    assert scanner == set() and decoy == {RefusalReason.OTHER_CLAIM}
