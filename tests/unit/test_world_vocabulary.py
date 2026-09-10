"""The vocabulary: closed, collision-free, every zone real, and fingerprinted against its version.

The digest test is the one with teeth. Editing a table changes what a seed produces, so
the edit must travel with a generator-version bump; the recorded digest makes the suite
fail until ``world.version`` is touched, and the diff then shows whether the version moved.
"""

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
from leaveimpact.world.version import GENERATOR_VERSION, VOCABULARY_DIGEST


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


def test_the_vocabulary_matches_the_digest_recorded_for_this_generator_version() -> None:
    assert vocabulary_digest() == VOCABULARY_DIGEST, (
        f"the vocabulary changed under generator version {GENERATOR_VERSION}: bump "
        "GENERATOR_VERSION and re-record VOCABULARY_DIGEST in world/version.py"
    )
