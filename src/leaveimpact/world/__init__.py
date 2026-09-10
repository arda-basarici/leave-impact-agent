"""The benchmark, pure: everything that exists only because the world is constructed.

The world specification (people, teams, skills, managers, tickets, meetings, leaves),
the scenario definitions (a fourteen-day slice, the leave inside it, ``now`` and the
stable-now interval, class and modifiers), the truth fact base with dated provenance,
the per-scenario keys (planted impacts, named distractors with their reason, the
``must_assess`` set, required sources, the completeness condition), the prose briefs and
templates, and the semantic generator that derives all of it from a seed, parameters and
a generator version. The construction invariants live here as well — the authored
``must_assess`` verdict must equal the rule's verdict over the fact base, and a scenario's
intended class must emerge from static org facts by selection — so a construction bug
fails generation instead of grading an agent wrong.

Boundary: imports ``core`` and nothing above it; performs no I/O, so semantic generation
can never quietly call a vendor or a model; is never imported by the investigator, which
is what keeps the answer key unreachable at source level and not only by credential.
Prose is not written here: this package emits briefs, the generator materializes them.
"""

from leaveimpact.world import org, scenario, slices, version, vocabulary
from leaveimpact.world.org import DEFAULT_PARAMS, OrgParams, OrgSpec, generate_org
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    DistractorReason,
    ExpectedImpact,
    ModifierEffect,
    ModifierName,
    NamedDistractor,
    OwnedEntities,
    Planted,
    Scenario,
    ScenarioClassName,
    ScenarioKey,
    ScenarioSpec,
    Tier,
    VerdictOverride,
)
from leaveimpact.world.slices import (
    allocate_slices,
    place_leave,
    place_now,
    stable_interval,
)
from leaveimpact.world.version import GENERATOR_VERSION, GeneratorVersion
from leaveimpact.world.vocabulary import (
    CITIES,
    COMPONENT_NAMES,
    FAMILY_NAMES,
    GIVEN_NAMES,
    SKILLS,
    TEAM_NAMES,
    City,
    Skill,
    vocabulary_digest,
)

__all__ = [
    "org",
    "scenario",
    "slices",
    "version",
    "vocabulary",
    "CITIES",
    "COMPONENT_NAMES",
    "DEFAULT_PARAMS",
    "FAMILY_NAMES",
    "GENERATOR_VERSION",
    "GIVEN_NAMES",
    "SKILLS",
    "TEAM_NAMES",
    "AuthoredVerdict",
    "City",
    "DistractorReason",
    "ExpectedImpact",
    "GeneratorVersion",
    "ModifierEffect",
    "ModifierName",
    "NamedDistractor",
    "OrgParams",
    "OrgSpec",
    "OwnedEntities",
    "Planted",
    "Scenario",
    "ScenarioClassName",
    "ScenarioKey",
    "ScenarioSpec",
    "Skill",
    "Tier",
    "VerdictOverride",
    "allocate_slices",
    "generate_org",
    "place_leave",
    "place_now",
    "stable_interval",
    "vocabulary_digest",
]
