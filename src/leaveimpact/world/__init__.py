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

from leaveimpact.world import (
    assembly,
    construction,
    modifiers,
    org,
    plan,
    scenario,
    slices,
    structured,
    truth_facts,
    version,
    vocabulary,
    zones,
)
from leaveimpact.world.assembly import (
    Contamination,
    ForeignRecord,
    WorldContamination,
    WorldSpec,
    assemble_world,
    verify_world,
    world_fact_base,
)
from leaveimpact.world.construction import (
    Amendment,
    ConflictingEffects,
    Construction,
    ConstructionError,
    Draft,
    Frame,
    Minting,
    MissingAffordance,
    Modifier,
    ScenarioClass,
    ScenarioInvariantFailed,
    construct,
)
from leaveimpact.world.modifiers import (
    COMPATIBLE_MODIFIERS,
    MODIFIERS,
    AlreadyResolved,
    ConcurrentLeave,
    OutsideWindow,
    TimezoneBoundary,
    WrongTeam,
)
from leaveimpact.world.org import DEFAULT_PARAMS, OrgParams, OrgSpec, generate_org
from leaveimpact.world.plan import (
    TIER_ONE_RULES,
    PlanInfeasible,
    PlanRow,
    PlanRules,
    check_plan,
    plan_world,
)
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
from leaveimpact.world.structured import (
    SCENARIO_CLASSES,
    StructuredDeadline,
    StructuredMeeting,
    StructuredMixed,
)
from leaveimpact.world.truth_facts import (
    SYSTEM_OF,
    derive_org,
    derive_owned,
    observed,
    truth_fact_base,
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
from leaveimpact.world.zones import gap_at, gap_holds_all_year, offset_of

__all__ = [
    "assembly",
    "construction",
    "modifiers",
    "org",
    "plan",
    "scenario",
    "slices",
    "structured",
    "truth_facts",
    "version",
    "vocabulary",
    "zones",
    "CITIES",
    "COMPATIBLE_MODIFIERS",
    "COMPONENT_NAMES",
    "DEFAULT_PARAMS",
    "FAMILY_NAMES",
    "GENERATOR_VERSION",
    "GIVEN_NAMES",
    "MODIFIERS",
    "SCENARIO_CLASSES",
    "SKILLS",
    "SYSTEM_OF",
    "TEAM_NAMES",
    "TIER_ONE_RULES",
    "AlreadyResolved",
    "Amendment",
    "AuthoredVerdict",
    "City",
    "ConcurrentLeave",
    "ConflictingEffects",
    "Construction",
    "ConstructionError",
    "Contamination",
    "DistractorReason",
    "Draft",
    "ExpectedImpact",
    "ForeignRecord",
    "Frame",
    "GeneratorVersion",
    "Minting",
    "MissingAffordance",
    "Modifier",
    "ModifierEffect",
    "ModifierName",
    "NamedDistractor",
    "OrgParams",
    "OrgSpec",
    "OutsideWindow",
    "OwnedEntities",
    "PlanInfeasible",
    "PlanRow",
    "PlanRules",
    "Planted",
    "Scenario",
    "ScenarioClass",
    "ScenarioClassName",
    "ScenarioInvariantFailed",
    "ScenarioKey",
    "ScenarioSpec",
    "Skill",
    "StructuredDeadline",
    "StructuredMeeting",
    "StructuredMixed",
    "Tier",
    "TimezoneBoundary",
    "VerdictOverride",
    "WorldContamination",
    "WorldSpec",
    "WrongTeam",
    "allocate_slices",
    "assemble_world",
    "check_plan",
    "construct",
    "derive_org",
    "derive_owned",
    "gap_at",
    "gap_holds_all_year",
    "generate_org",
    "observed",
    "offset_of",
    "place_leave",
    "place_now",
    "plan_world",
    "stable_interval",
    "truth_fact_base",
    "verify_world",
    "vocabulary_digest",
    "world_fact_base",
]
