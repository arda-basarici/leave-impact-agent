"""The three sealed artifacts of a world, their canonical bytes and digests, and the world version.

Three readers, three files (the bundle ruling at step 8, the names settled at its
review). The *world spec* — the organization, the plan, the slices, the provenance, and
the content digests of the other two files, so a swapped file is visible — is the
semantic realization: benchmark-private, read by the projectors and the validator, never
by the application, since the plan alone names which traps were planted. The *scenario
specs* hold the agent-visible rows only: what a run is asked, legitimate inputs and no
evaluator-only truth. The *truth manifest* is evaluator-only: every key, the
construction and observability records the audit reads, and the dated world-level fact
base. A fourth file is deliberately not here: the *world manifest* of the earlier
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
timestamp, because the zone is provenance for how a human read the time. Decoders arrive
with their first consumer, the validator, which reads the manifest against the live
systems.
"""

from __future__ import annotations

import hashlib
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
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.predicates import predicate
from leaveimpact.core.refs import EvidenceRef
from leaveimpact.core.values_json import encode_ref, encode_value
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.world.assembly import WorldSpec
from leaveimpact.world.org import encode_org_params
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


def bundle(world: WorldSpec) -> Bundle:
    """The bundle of ``world``: specs and truth first, then the world spec citing their digests."""
    specs = _artifact(SCENARIO_SPECS, encode_scenario_specs(world))
    truth = _artifact(TRUTH_MANIFEST, encode_truth_manifest(world))
    spec = _artifact(WORLD_SPEC, encode_world_spec(world, specs, truth))
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


def encode_world_spec(world: WorldSpec, specs: Artifact, truth: Artifact) -> JsonObject:
    """Organization, plan, slices, provenance, and the digests of the other two files."""
    return {
        "artifact": WORLD_SPEC,
        "provenance": {
            "seed": world.seed,
            "world_start": world.world_start.isoformat(),
            "generator_version": world.generator_version,
            "interpreter": list(world.interpreter),
            "vocabulary_digest": world.vocabulary_digest,
        },
        "org": _org(world),
        "plan": [_plan_row(row) for row in world.plan],
        "slices": [_span(window) for window in world.slices],
        "artifacts": {specs.name: specs.digest, truth.name: truth.digest},
    }


def encode_scenario_specs(world: WorldSpec) -> JsonObject:
    """The agent-visible rows only: what each run is asked, nothing of what truth expects."""
    return {
        "artifact": SCENARIO_SPECS,
        "scenarios": [_spec(scenario.spec) for scenario in world.scenarios],
    }


def encode_truth_manifest(world: WorldSpec) -> JsonObject:
    """Evaluator-only: every key, the construction records, the dated world-level fact base."""
    return {
        "artifact": TRUTH_MANIFEST,
        "scenarios": [_construction(scenario) for scenario in world.scenarios],
        "facts": _fact_base(world.facts),
    }


# --- Organization and plan --------------------------------------------------------------


def _org(world: WorldSpec) -> JsonObject:
    org = world.org
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


def _construction(scenario: Scenario) -> JsonObject:
    return {
        "key": _key(scenario.key),
        "owned": _owned(scenario.owned),
        "authored_facts": [_fact(fact) for fact in scenario.authored_facts],
    }


def _key(key: ScenarioKey) -> JsonObject:
    return {
        "scenario_id": key.scenario_id,
        "tier": key.tier.value,
        "scenario_class": key.scenario_class.value,
        "modifiers": [modifier.value for modifier in key.modifiers],
        "impacts": [_expected_impact(expected) for expected in key.impacts],
        "constraints": [_constraint(constraint) for constraint in key.constraints],
        "distractors": [_distractor(distractor) for distractor in key.distractors],
        "stable_interval": _span(key.stable_interval),
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
        "facts": [_fact(fact) for fact in base.facts],
        "gaps": [_gap(gap) for gap in base.gaps],
    }


def _fact(fact: Fact) -> JsonObject:
    return {
        "subject": encode_ref(fact.subject),
        "predicate": fact.predicate.value,
        "value": encode_value(fact.value, predicate(fact.predicate).value_spec),
        "evidence": _evidence(fact.evidence),
        "observable_from": fact.observable_from.isoformat(),
    }


def _gap(gap: Gap) -> JsonObject:
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
