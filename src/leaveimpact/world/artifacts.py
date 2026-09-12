"""The three sealed artifacts of a world, their canonical bytes and digests, and the world version.

Three readers, three files (the bundle ruling at step 8, the names settled at its
review, the content redrawn at the validator step). The *world spec* — the organization,
the plan, the slices, what each scenario planted with the date it became observable, each
scenario's stable interval, the provenance, and the content digests of the other two
files, so a swapped file is visible — is the planted world: benchmark-private, read by
the projectors and the validator, never by the application, since the plan alone names
which traps were planted. It is what was supposed to be projected and holds nothing
truth expects of it. The *scenario specs* hold the agent-visible rows only: what a run is
asked, legitimate inputs and no evaluator-only truth. The *truth manifest* is
evaluator-only: every key, the authored facts, and the dated world-level fact base — what
the plantings are expected to imply. One home per fact across the three: the plantings
and the stable intervals moved out of the truth manifest when the validator became the
spec's first reader from bytes, because a validator whose role reads the spec alone could
not otherwise know what was planted, and the evaluator joins the two files by scenario id.
The serialized key is therefore narrower than the in-memory construction record on
purpose. A fourth file is deliberately not here: the *world manifest* of the earlier
contract — adapter configuration, the identity map from semantic to vendor ids, org
parameters, the world version and digests — is the projection's receipt, written after
the vendors mint ids, application-readable, outside the hash, and holding no fact that
can change an answer (the test: delete it after identity resolution and lose nothing
answer-relevant). It lives in ``adapters.manifest``, the lowest package that can type the
adapter configuration it carries. Nothing here writes a byte; canonical
serialization and hashing are pure, and persistence and sealing belong to the generator
entry point.

The world version is the digest of the realized bundle — the three canonical byte
sequences hashed in a fixed order, each prefixed by its file name — never of the recipe,
because the interpreter finding at the organization step is exactly a case where the
recipe holds and the realization drifts. It is external metadata of the bundle and is
never serialized into a hashed artifact, which would define it circularly. The tests
record a reference seed's version beside the generator version as a pair: a changed
hash with an unchanged generator version fails, and re-cutting the pair is the
deliberate act that accompanies a bump.

Canonical means what every codec here means by it — the one byte rule in ``core``'s
JSON shape module, so the bytes are a property of the world and not of a serializer's
defaults. Fact values travel through the value codec,
tagged by their predicate's spec; instants carry their IANA zone beside the offset-bearing
timestamp, because the zone is provenance for how a human read the time.

The world spec is encoded from ``PlantedWorldSpec``, a value that is exactly the file's
content, projected from the assembled world by a pure function; the encoder chooses no
fields of its own. That makes the codec a round trip over one value, three separately
provable claims — the projection yields the expected value, decoding an encoding yields
the value, encoding a decoding of the sealed bytes yields the bytes — instead of a codec
over a type the file cannot rebuild. The decoders for the spec and the scenario specs
live in the sibling ``decoders`` module; the truth manifest's waits for its first
consumer, the evaluator, since a decoder the validator is forbidden to use has no place
where the validator can reach it.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from leaveimpact.core.claims import ConstraintKey, ImpactKey
from leaveimpact.core.entities import (
    CalendarEvent,
    Comment,
    Component,
    Document,
    Employee,
    Leave,
    Team,
    WorkItem,
)
from leaveimpact.core.facts import Fact, FactBase, Gap
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.predicates import predicate
from leaveimpact.core.refs import EvidenceRef
from leaveimpact.core.values_json import encode_ref, encode_value
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.world.assembly import WorldSpec
from leaveimpact.world.org import OrgSpec, encode_org_params
from leaveimpact.world.plan import PlanRow
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    ExpectedImpact,
    NamedDistractor,
    OwnedEntities,
    Planted,
    Scenario,
    ScenarioKey,
    ScenarioSpec,
)
from leaveimpact.world.version import GeneratorVersion

WORLD_SPEC = "world-spec.json"
SCENARIO_SPECS = "scenario-specs.json"
TRUTH_MANIFEST = "truth-manifest.json"


@dataclass(frozen=True, slots=True)
class Artifact:
    """One file of the bundle: its name, canonical bytes and SHA-256 digest."""

    name: str
    content: bytes
    digest: str


@dataclass(frozen=True, slots=True)
class Bundle:
    """The three artifacts and the world version that names their realization."""

    world_spec: Artifact
    scenario_specs: Artifact
    truth_manifest: Artifact
    world_version: WorldVersion

    @property
    def artifacts(self) -> tuple[Artifact, ...]:
        """The files in the order the version hashes them."""
        return (self.world_spec, self.scenario_specs, self.truth_manifest)


SHA256_HEX = re.compile(r"[0-9a-f]{64}")
"""The shape of every digest a sealed artifact cites."""


@dataclass(frozen=True, slots=True)
class ScenarioPlanting:
    """One scenario's row of the world spec: what it planted, and when its answer is stable.

    The stable interval sits here and not in the key because it is a property of the
    plantings, derived from their observability; the evaluator reads it from here, joined
    by scenario id. The validator does not read it: under the runtime rule a run's view
    does not move inside the interval, so its check is one read per scenario.
    """

    scenario_id: ScenarioId
    owned: OwnedEntities
    stable_interval: DateSpan


@dataclass(frozen=True, slots=True)
class PlantedWorldSpec:
    """Exactly the content of the world spec file: the planted world, nothing truth expects.

    The assembled world carries the keys and the fact base beside what it planted; this
    is the projection of it the file holds, so a decoder of the file rebuilds this type
    and structurally nothing more. The two digests are the other files' as sealed, cited
    so a swapped file is visible; the world version is not here, since it hashes this
    file and would define itself.
    """

    seed: int
    world_start: date
    generator_version: GeneratorVersion
    interpreter: tuple[int, int]
    vocabulary_digest: str
    org: OrgSpec
    slices: tuple[DateSpan, ...]
    plan: tuple[PlanRow, ...]
    scenarios: tuple[ScenarioPlanting, ...]
    scenario_specs_digest: str
    truth_manifest_digest: str

    def __post_init__(self) -> None:
        if not (len(self.slices) == len(self.plan) == len(self.scenarios)):
            raise ValueError(
                f"one slice, one plan row and one planting each, got {len(self.slices)}, "
                f"{len(self.plan)} and {len(self.scenarios)}"
            )
        ids = [planting.scenario_id for planting in self.scenarios]
        if len(set(ids)) != len(ids):
            raise ValueError(f"scenario ids are unique within a world, got {ids}")
        for row, planting in zip(self.plan, self.scenarios, strict=True):
            if row.scenario_id != planting.scenario_id:
                raise ValueError(
                    f"plan row {row.scenario_id} and planting {planting.scenario_id} disagree"
                )
        for name, value in (
            ("vocabulary_digest", self.vocabulary_digest),
            ("scenario_specs_digest", self.scenario_specs_digest),
            ("truth_manifest_digest", self.truth_manifest_digest),
        ):
            if not SHA256_HEX.fullmatch(value):
                raise ValueError(f"{name} is a SHA-256 hex, got {value!r}")


def planted_world_spec(
    world: WorldSpec, scenario_specs_digest: str, truth_manifest_digest: str
) -> PlantedWorldSpec:
    """The world spec's content for ``world``: every planting and interval, no key, no fact base."""
    return PlantedWorldSpec(
        seed=world.seed,
        world_start=world.world_start,
        generator_version=world.generator_version,
        interpreter=world.interpreter,
        vocabulary_digest=world.vocabulary_digest,
        org=world.org,
        slices=world.slices,
        plan=world.plan,
        scenarios=tuple(
            ScenarioPlanting(scenario.spec.id, scenario.owned, scenario.key.stable_interval)
            for scenario in world.scenarios
        ),
        scenario_specs_digest=scenario_specs_digest,
        truth_manifest_digest=truth_manifest_digest,
    )


def bundle(world: WorldSpec) -> Bundle:
    """The bundle of ``world``: specs and truth first, then the world spec citing their digests."""
    specs = _artifact(
        SCENARIO_SPECS, encode_scenario_specs([scenario.spec for scenario in world.scenarios])
    )
    truth = _artifact(TRUTH_MANIFEST, encode_truth_manifest(world))
    planted = planted_world_spec(world, specs.digest, truth.digest)
    spec = _artifact(WORLD_SPEC, encode_world_spec(planted))
    return Bundle(spec, specs, truth, world_version((spec, specs, truth)))


def world_version(artifacts: tuple[Artifact, ...]) -> WorldVersion:
    """The SHA-256 over the artifacts' canonical bytes in order, each prefixed by its name."""
    hasher = hashlib.sha256()
    for artifact in artifacts:
        hasher.update(artifact.name.encode("utf-8") + b"\n")
        hasher.update(artifact.content)
        hasher.update(b"\n")
    return WorldVersion(hasher.hexdigest())


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _artifact(name: str, data: JsonObject) -> Artifact:
    content = canonical_bytes(data)
    return Artifact(name, content, digest(content))


# --- The three documents ------------------------------------------------------------------


def encode_world_spec(spec: PlantedWorldSpec) -> JsonObject:
    """Provenance, organization, plan, slices, plantings, and the digests of the other two files."""
    return {
        "artifact": WORLD_SPEC,
        "provenance": {
            "seed": spec.seed,
            "world_start": spec.world_start.isoformat(),
            "generator_version": spec.generator_version,
            "interpreter": list(spec.interpreter),
            "vocabulary_digest": spec.vocabulary_digest,
        },
        "org": _org(spec.org),
        "plan": [_plan_row(row) for row in spec.plan],
        "slices": [_span(window) for window in spec.slices],
        "scenarios": [_planting(planting) for planting in spec.scenarios],
        "artifacts": {
            SCENARIO_SPECS: spec.scenario_specs_digest,
            TRUTH_MANIFEST: spec.truth_manifest_digest,
        },
    }


def encode_scenario_specs(specs: Sequence[ScenarioSpec]) -> JsonObject:
    """The agent-visible rows only: what each run is asked, nothing of what truth expects."""
    return {"artifact": SCENARIO_SPECS, "scenarios": [_spec(spec) for spec in specs]}


def encode_truth_manifest(world: WorldSpec) -> JsonObject:
    """Evaluator-only: every key, the construction records, the dated world-level fact base."""
    return {
        "artifact": TRUTH_MANIFEST,
        "scenarios": [_construction(scenario) for scenario in world.scenarios],
        "facts": _fact_base(world.facts),
    }


# --- Organization and plan --------------------------------------------------------------


def _org(org: OrgSpec) -> JsonObject:
    return {
        "seed": org.seed,
        "params": encode_org_params(org.params),
        "generator_version": org.generator_version,
        "teams": [_team(team) for team in org.teams],
        "employees": [_employee(employee) for employee in org.employees],
        "components": [_component(component) for component in org.components],
        "skills": list(org.skills),
    }


def _team(team: Team) -> JsonObject:
    return {"id": team.id, "name": team.name}


def _employee(employee: Employee) -> JsonObject:
    return {
        "id": employee.id,
        "name": employee.name,
        "team_id": employee.team_id,
        "manager_id": employee.manager_id,
        "skills": None if employee.skills is None else list(employee.skills),
        "location": employee.location,
        "country": employee.country,
        "timezone": employee.timezone,
        "grade": employee.grade.value,
        "employment_type": employee.employment_type.value,
    }


def _component(component: Component) -> JsonObject:
    return {"id": component.id, "name": component.name, "member_ids": list(component.member_ids)}


def _plan_row(row: PlanRow) -> JsonObject:
    return {
        "scenario_id": row.scenario_id,
        "tier": row.tier.value,
        "scenario_class": row.scenario_class.value,
        "modifiers": [modifier.value for modifier in row.modifiers],
    }


# --- Scenario records ---------------------------------------------------------------------


def _spec(spec: ScenarioSpec) -> JsonObject:
    return {
        "id": spec.id,
        "leave_id": spec.leave_id,
        "now": _instant(spec.now),
        "reference_timezone": spec.reference_timezone,
        "window": _span(spec.window),
    }


def _planting(planting: ScenarioPlanting) -> JsonObject:
    return {
        "scenario_id": planting.scenario_id,
        "stable_interval": _span(planting.stable_interval),
        "owned": _owned(planting.owned),
    }


def _construction(scenario: Scenario) -> JsonObject:
    """The key and the authored facts; the plantings are the world spec's row (one home)."""
    return {
        "key": _key(scenario.key),
        "authored_facts": [encode_fact(fact) for fact in scenario.authored_facts],
    }


def _key(key: ScenarioKey) -> JsonObject:
    """The key without its stable interval, which the world spec's row carries."""
    return {
        "scenario_id": key.scenario_id,
        "tier": key.tier.value,
        "scenario_class": key.scenario_class.value,
        "modifiers": [modifier.value for modifier in key.modifiers],
        "impacts": [_expected_impact(expected) for expected in key.impacts],
        "constraints": [_constraint(constraint) for constraint in key.constraints],
        "distractors": [_distractor(distractor) for distractor in key.distractors],
        "required_sources": [source.value for source in key.required_sources],
    }


def _expected_impact(expected: ExpectedImpact) -> JsonObject:
    return {
        "key": _impact_key(expected.key),
        "outcome": expected.outcome.value,
        "must_assess": [_authored(authored) for authored in expected.must_assess],
    }


def _impact_key(key: ImpactKey) -> JsonObject:
    return {
        "leave_id": key.leave_id,
        "subtype": key.subtype.value,
        "artifact": encode_ref(key.artifact),
    }


def _authored(authored: AuthoredVerdict) -> JsonObject:
    return {
        "employee_id": authored.employee_id,
        "verdict": authored.verdict.value,
        "reasons": [reason.value for reason in authored.reasons],
    }


def _constraint(constraint: ConstraintKey) -> JsonObject:
    return {"clause_id": constraint.clause_id, "applies_to": encode_ref(constraint.applies_to)}


def _distractor(distractor: NamedDistractor) -> JsonObject:
    return {"entity": encode_ref(distractor.entity), "reason": distractor.reason.value}


def _owned(owned: OwnedEntities) -> JsonObject:
    return {
        "leaves": [_planted(planted, _leave(planted.entity)) for planted in owned.leaves],
        "work_items": [
            _planted(planted, _work_item(planted.entity)) for planted in owned.work_items
        ],
        "events": [_planted(planted, _event(planted.entity)) for planted in owned.events],
        "documents": [_planted(planted, _document(planted.entity)) for planted in owned.documents],
    }


def _planted[T: Leave | WorkItem | CalendarEvent | Document](
    planted: Planted[T], record: JsonObject
) -> JsonObject:
    return {"record": record, "observable_from": planted.observable_from.isoformat()}


# --- Planted records ----------------------------------------------------------------------


def _leave(leave: Leave) -> JsonObject:
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "start": leave.start.isoformat(),
        "end": leave.end.isoformat(),
        "kind": leave.kind.value,
        "status": leave.status.value,
    }


def _work_item(item: WorkItem) -> JsonObject:
    return {
        "id": item.id,
        "title": item.title,
        "owner_id": item.owner_id,
        "status": item.status.value,
        "component_id": item.component_id,
        "opened_on": item.opened_on.isoformat(),
        "resolved_on": _optional_date(item.resolved_on),
        "due_on": _optional_date(item.due_on),
        "comments": [_comment(comment) for comment in item.comments],
    }


def _comment(comment: Comment) -> JsonObject:
    return {
        "id": comment.id,
        "world_date": comment.world_date.isoformat(),
        "author_id": comment.author_id,
        "text": comment.text,
    }


def _event(event: CalendarEvent) -> JsonObject:
    return {
        "id": event.id,
        "title": event.title,
        "start": _instant(event.start),
        "end": _instant(event.end),
        "attendee_ids": list(event.attendee_ids),
    }


def _document(document: Document) -> JsonObject:
    return {
        "id": document.id,
        "title": document.title,
        "kind": document.kind.value,
        "effective_from": document.effective_from.isoformat(),
        "sections": [{"id": section.id, "text": section.text} for section in document.sections],
    }


# --- Facts ----------------------------------------------------------------------------------


def _fact_base(base: FactBase) -> JsonObject:
    return {
        "facts": [encode_fact(fact) for fact in base.facts],
        "gaps": [encode_gap(gap) for gap in base.gaps],
    }


def encode_fact(fact: Fact) -> JsonObject:
    return {
        "subject": encode_ref(fact.subject),
        "predicate": fact.predicate.value,
        "value": encode_value(fact.value, predicate(fact.predicate).value_spec),
        "evidence": _evidence(fact.evidence),
        "observable_from": fact.observable_from.isoformat(),
    }


def encode_gap(gap: Gap) -> JsonObject:
    return {
        "subject": encode_ref(gap.subject),
        "predicate": gap.predicate.value,
        "evidence": _evidence(gap.evidence),
        "observable_from": gap.observable_from.isoformat(),
    }


def _evidence(evidence: EvidenceRef) -> JsonObject:
    return {
        "source": evidence.source.value,
        "target": encode_ref(evidence.target),
        "field": evidence.field,
    }


# --- Time ---------------------------------------------------------------------------------


def _span(span: DateSpan) -> JsonObject:
    return {"start": span.start.isoformat(), "end": span.end.isoformat()}


def _instant(instant: datetime) -> JsonObject:
    """An aware instant with its IANA zone beside the offset-bearing timestamp, when it has one."""
    return {"at": instant.isoformat(), "timezone": getattr(instant.tzinfo, "key", None)}


def _optional_date(day: date | None) -> str | None:
    return None if day is None else day.isoformat()
