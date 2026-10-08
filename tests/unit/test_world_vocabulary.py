"""The vocabulary: closed, collision-free, every zone real, and fingerprinted against its version.

The digest test is the one with teeth. Editing a table changes what a seed produces, so
the edit must travel with a generator-version bump; the recorded digest makes the suite
fail until ``world.version`` is touched, and the diff then shows whether the version moved.
"""

import sys
from zoneinfo import ZoneInfo

from leaveimpact.core.ids import SKILL_ID
from leaveimpact.world import (
    CITIES,
    COMPONENT_NAMES,
    FAMILY_NAMES,
    GIVEN_NAMES,
    SKILLS,
    TEAM_NAMES,
    vocabulary_digest,
)
from leaveimpact.world.adversarial import RUNBOOK_TITLE
from leaveimpact.world.fragmented import (
    NOTE_TITLE,
    POLICY_TITLE,
    PROCEDURE_TITLE,
    RELEASE_POLICY_TITLE,
)
from leaveimpact.world.modifiers import BOUNDARY_EVENT_TITLE
from leaveimpact.world.version import GENERATOR_PYTHON, GENERATOR_VERSION, VOCABULARY_DIGEST
from leaveimpact.world.vocabulary import (
    CLIENT_NAMES,
    FICTIONAL_CLIENTS,
    FICTIONAL_RELEASES,
    LOOK_ALIKE_MEETING_PHRASES,
    LOOK_ALIKE_TICKET_PHRASES,
    MEETING_PHRASES,
    MEETING_QUALIFIERS,
    TICKET_PHRASES,
    TICKET_QUALIFIERS,
    filler_titles,
    titles,
)


def test_every_table_is_collision_free() -> None:
    for table in (
        GIVEN_NAMES,
        FAMILY_NAMES,
        TEAM_NAMES,
        COMPONENT_NAMES,
        tuple(city.name for city in CITIES),
        tuple(skill.id for skill in SKILLS),
        tuple(skill.name for skill in SKILLS),
    ):
        assert len(set(table)) == len(table), table


def test_every_city_zone_loads() -> None:
    for city in CITIES:
        assert ZoneInfo(city.timezone).key == city.timezone
        assert len(city.country) == 2 and city.country.isupper()


def test_skill_ids_have_the_domain_shape() -> None:
    for skill in SKILLS:
        assert SKILL_ID.match(skill.id), skill.id


def test_names_can_fill_an_organization_far_larger_than_the_vision_asks() -> None:
    assert len(GIVEN_NAMES) * len(FAMILY_NAMES) >= 200


def test_component_names_are_not_team_names() -> None:
    assert not set(COMPONENT_NAMES) & set(TEAM_NAMES)


def planted_titles() -> set[str]:
    """Every title a planted ticket, meeting, event or document can carry, over every context
    the organization tables afford and every class template."""
    tickets = {
        title
        for component in COMPONENT_NAMES
        for phrases in (TICKET_PHRASES, LOOK_ALIKE_TICKET_PHRASES)
        for title in titles(component, phrases, TICKET_QUALIFIERS)
    }
    meetings = {
        title
        for team in TEAM_NAMES
        for phrases in (MEETING_PHRASES, LOOK_ALIKE_MEETING_PHRASES)
        for title in titles(team, phrases, MEETING_QUALIFIERS)
    }
    documents = (
        {RUNBOOK_TITLE.format(release=t) for t in tickets}
        | {RELEASE_POLICY_TITLE.format(release=t) for t in tickets}
        | {POLICY_TITLE.format(meeting=m) for m in meetings}
        | {NOTE_TITLE.format(client=c) for c in CLIENT_NAMES}
        | {PROCEDURE_TITLE.format(client=c) for c in CLIENT_NAMES}
    )
    return tickets | meetings | documents | {BOUNDARY_EVENT_TITLE}


def test_the_filler_name_book_names_nothing_the_planted_tables_name() -> None:
    # The scanner admits a fictional form by spelling, so an equal spelling anywhere in the
    # planted tables would admit the real thing; casefolded, since the scanner is.
    tables: tuple[tuple[str, ...], ...] = (
        GIVEN_NAMES,
        FAMILY_NAMES,
        TEAM_NAMES,
        COMPONENT_NAMES,
        CLIENT_NAMES,
        tuple(city.name for city in CITIES),
        tuple(skill.name for skill in SKILLS),
    )
    planted_forms = {form.casefold() for table in tables for form in table}
    book = FICTIONAL_RELEASES + FICTIONAL_CLIENTS
    fictional = {name.casefold() for name in book}
    assert not fictional & planted_forms
    assert len(fictional) == len(book)


def test_no_filler_title_contains_or_sits_inside_a_planted_title() -> None:
    # The scope matcher resolves by substring, so a filler title around or inside a planted
    # one would steal that clause's resolution; the check is the matcher's own relation.
    planted = {title.casefold() for title in planted_titles()}
    minted = [title.casefold() for _, title in filler_titles()]
    assert len(set(minted)) == len(minted)
    crossing = [
        (filler, title)
        for filler in minted
        for title in planted
        if filler == title or filler in title or title in filler
    ]
    assert crossing == []


def test_the_vocabulary_matches_the_digest_recorded_for_this_generator_version() -> None:
    assert vocabulary_digest() == VOCABULARY_DIGEST, (
        f"the vocabulary changed under generator version {GENERATOR_VERSION}: bump "
        "GENERATOR_VERSION and re-record VOCABULARY_DIGEST in world/version.py"
    )


def test_the_interpreter_is_the_one_this_generator_version_was_recorded_under() -> None:
    assert sys.version_info[:2] == GENERATOR_PYTHON, (
        f"Python {sys.version_info[0]}.{sys.version_info[1]} is not the interpreter generator "
        f"version {GENERATOR_VERSION} was recorded under; random's higher-level draws may "
        "differ: inspect what the generator now produces, bump GENERATOR_VERSION, update "
        "GENERATOR_PYTHON, re-cut the frozen worlds"
    )
