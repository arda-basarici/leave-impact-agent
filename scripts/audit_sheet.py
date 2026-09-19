"""The step 16 audit sheet: one world's truth rendered for a human reader, one markdown file.

The hand audit that lets a world be called golden (DESIGN, "Two audit depths make golden an
honest word") reads every scenario against its key and every model-written text against
the facts it was asked to carry. Those live in three sealed objects a human cannot read
side by side: the world spec (the org, the plan, the plantings with their observable-from
dates), the truth manifest (every key, the authored facts, the dated fact base, the
materialization record) and the scenario specs (what each run is asked). This script
reads the three under the SSO profile and renders them as one sheet, scenario by scenario
in the plan's order, so the acceptance pass and the deep audit read from one document and
their rulings cite one digest.

Per scenario the sheet gives the spec row (the leave under investigation, ``now``, the
window), the key (impacts with their authored verdicts, constraints, distractors, required
sources, expected conflicts and unknowns), the outcome witness, the plantings with dates
(leaves, work items with their comments, events, documents with their sections), the
scenario's authored facts, the fact-base entries whose subject or evidence the scenario
cites (the deep audit's trace material, each with its evidence and observable-from date),
and the prose targets with their briefs, attempts, refusals and the checker's propositions
beside the accepted text. Before the scenarios, a header (versions, the organization's
parameters, models, prompt digests, the record's counters) and the rollups the audit items read
off (attempts per register, refusals by guard and by reason, targets above attempt four,
opening frames per register).

The outcome witness exists because the key's outcome is a claim over the whole candidate
universe while ``must_assess`` names only the authored subset, so a reader cannot recompute
the outcome from the key alone (the first acceptance pass found this on its first
scenario). The witness is the generator's own result, never a second implementation of
the rule: the semantic world is rebuilt from the sealed provenance (seed, parameters,
start, plan) with the generator's own assembly, its semantic digest is required to equal
the sealed one so the rebuilt objects are the sealed world's, and per impact the three
calls the whole-world verification makes (assess every employee, count the requirement,
derive the action) are rendered at the scenario's ``now`` under the dated view. The
verification proves every day of the stable interval under both views; the witness shows
the one day the run is asked about, and says so. A witness that disagrees with its key is
a defect of the generator's verification, reported in the sheet and never smoothed over.

The criterion universe exists because the witness is the rule's own count, so an
uncovered or unknown outcome, a claim over every employee, could be read off the sheet but
not proven from it (the step 16 panel, 2026-09-19). Per impact the block lists every
employee's facts of the four families the viability rule's criteria read (component
memberships, skills or the record's absence, leaves and events over the need's window,
employment type), rendered from the fact base under the same dated view with no call to
the viability or outcome functions; the reader derives the active criteria the way the
checklist's trace does and counts. The independence is from the rule, not from the data:
the dated view and the fact reads are the same code the rule uses, and the need's window
is the checklist's own statement (the investigated leave's span, or the meeting's day in
the reference timezone) restated here rather than the rule's derivation.

The cited fact-base entries are each cited entity's whole record, so they carry rows
dated after the scenario's ``now`` that belong to other scenarios' plantings; the sheet
lists those apart, under their own heading, so a reader neither counts them into the
dated view nor mistakes them for a rendering fault. They stay in the private sheet and
never enter a released golden scenario; the throwaway example keeps them, and its header
says why.

Reads only. The rendered sheet holds benchmark truth: it is written under ``data/audit/``,
which the repository ignores, and is never committed; the provenance artifact the audit
produces from it is versioned into the truth bucket beside the world.

The throwaway mode is the one exception, and it commits no truth: the world it renders is
generated here, on the workstation, from the generator's own recipe flags through the same
fresh stage the job runs (assemble, materialize, compose, bundle), and it stops there. The
bundle is never written to a bucket, never projected into a vendor, never scored; the
version in its header is the bundle's content hash and names nothing anywhere. That is
what lets the sheet be illustrated in the public tree before any golden scenario is
retired (DESIGN's per-scenario retirement ruling): the example at
``docs/examples/audit_sheet_throwaway.md`` shows the sheet's shape, prose beside its
brief included, on a world nobody will ever be evaluated against. The sections of rows
observable only after a scenario's ``now`` stay in that example, since the leak they would
carry, other scenarios' plantings, is of a world with nothing to protect; the header says
so. The prose stage spends a few model calls under the ambient credentials, the generator's
three model variables naming the writer, the checker and their region.

Usage: ``python scripts/audit_sheet.py <world_version>`` with ``AWS_PROFILE`` set renders a
sealed world; ``python scripts/audit_sheet.py --throwaway --seed N --world-start DATE
--plan golden …`` takes the generator's recipe flags after ``--throwaway`` and renders the
example.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import boto3

from leaveimpact.adapters.object_store.layout import (
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import Fact, FactBase, FactView, RunCondition
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.plans import expected_action
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import EntityRef, clause_ref, employee_ref
from leaveimpact.core.values import FactValue
from leaveimpact.core.values_json import encode_value
from leaveimpact.core.viability import Assessment, assess_impact
from leaveimpact.core.worldtime import DateSpan, InstantSpan
from leaveimpact.generator.entrypoint import (
    ConfigurationError,
    parse_recipe,
    prose_models_for,
    prose_models_from_env,
)
from leaveimpact.generator.fresh import fresh_world
from leaveimpact.generator.truth_record import decode_materialization
from leaveimpact.world.artifacts import Bundle, semantic_digest
from leaveimpact.world.assembly import SemanticWorld, assemble_semantic_world
from leaveimpact.world.construction import required_count_for
from leaveimpact.world.org import OrgSpec, decode_org_params
from leaveimpact.world.scenario import Scenario

TRUTH_BUCKET = os.environ.get("LEAVE_IMPACT_TRUTH_BUCKET", "leave-impact-truth-445743457479")
WORLD_BUCKET = os.environ.get("LEAVE_IMPACT_WORLD_BUCKET", "leave-impact-world-445743457479")
REGION = os.environ.get("LEAVE_IMPACT_AWS_REGION", "eu-central-1")
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "audit"
EXAMPLE_PATH = (
    Path(__file__).resolve().parent.parent / "docs" / "examples" / "audit_sheet_throwaway.md"
)

THROWAWAY_NOTES = (
    "throwaway world: generated on a workstation from the recipe above by the generator's "
    "own fresh stage (assemble, materialize, compose, bundle) and left there; never sealed, "
    "never projected into a vendor, never scored; the version is the bundle's content hash "
    "and names nothing in any bucket",
    "the sections of rows observable only after a scenario's `now` are kept in this sheet: "
    "the per-scenario retirement ruling excludes them from a released golden scenario "
    "because they leak other scenarios' plantings, and a throwaway world has nothing to "
    "protect",
)
"""What the example's header says that a sealed world's does not."""

Json = Mapping[str, Any]


# --- Reading ------------------------------------------------------------------------------


def fetch(s3: Any, bucket: str, key: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def throwaway_bundle(argv: Sequence[str]) -> Bundle:
    """A world generated here from the generator's recipe flags, its prose written by the
    models the environment names, and left unsealed: the bundle is the whole of it."""
    recipe = parse_recipe(argv)
    if recipe.resume is not None:
        raise ConfigurationError(
            "--resume names a sealed realization; a throwaway world is always fresh"
        )
    writer, checker = prose_models_for(prose_models_from_env(os.environ))
    fresh = fresh_world(recipe, writer, checker, print)
    for line in fresh.metrics.lines():
        print(line)
    return fresh.bundle


def rebuild(spec: Json) -> SemanticWorld:
    """The sealed world's semantic objects, rebuilt from its provenance by the generator's own
    assembly and admitted only when the semantic digest equals the sealed one.

    A digest that differs means the interpreter, the generator version or the code has
    moved since sealing, and a witness rendered from it would be of some other world;
    the mismatch is reported with both digests and nothing is rendered.
    """
    prov = spec["provenance"]
    semantic = assemble_semantic_world(
        prov["seed"],
        decode_org_params(spec["org"]["params"]),
        date.fromisoformat(prov["world_start"]),
        prov["plan_name"],
    )
    rebuilt, sealed = semantic_digest(semantic), prov["semantic_digest"]
    if rebuilt != sealed:
        raise RuntimeError(
            f"the rebuilt world is not the sealed one: semantic digest {rebuilt} rebuilt "
            f"under generator version {semantic.generator_version}, {sealed} sealed under "
            f"version {prov['generator_version']}"
        )
    return semantic


class Names:
    """Every org entity's display name by id, so the sheet reads ``emp_023 (Bob Kaya)``."""

    def __init__(self, org: Json) -> None:
        self._names: dict[str, str] = {}
        for kind in ("teams", "employees", "components"):
            for record in org.get(kind, []):
                self._names[record["id"]] = record["name"]

    def __call__(self, id: str | None) -> str:
        if id is None:
            return "—"
        name = self._names.get(id)
        return f"{id} ({name})" if name else str(id)

    def knows(self, id: object) -> bool:
        return isinstance(id, str) and id in self._names


# --- Value rendering ----------------------------------------------------------------------


def ref(data: Json | None, names: Names) -> str:
    if data is None:
        return "—"
    return f"{data.get('kind')}:{names(data.get('id'))}"


def value(data: Json | None, names: Names) -> str:
    """A tagged value's payload, entity ids named; a ref-shaped payload reads as a ref."""
    if data is None:
        return "—"
    payload = data.get("value")
    if isinstance(payload, dict) and "id" in payload:
        return ref(payload, names)
    if isinstance(payload, list):
        return (
            "["
            + ", ".join(names(item) if names.knows(item) else str(item) for item in payload)
            + "]"
        )
    if names.knows(payload):
        return names(payload)
    return str(payload)


def typed_value(payload: FactValue, predicate_name: Any, names: Names) -> str:
    """A run-time fact value rendered as the sheet renders the sealed one: through the same
    encoder the artifacts use, so an entity reads by name and a span by its dates."""
    return value(encode_value(payload, predicate(predicate_name).value_spec), names)


def fact_text(item: Any, names: Names) -> str:
    """A run-time ``Fact`` as ``subject predicate = value <- source``, the sealed rendering's
    shape without the date, which the witness's one-day view already fixes."""
    return (
        f"{item.subject.kind.value}:{names(item.subject.id)} {item.predicate.value} = "
        f"{typed_value(item.value, item.predicate, names)} <- {item.evidence.source.value}"
    )


def fact(data: Json, names: Names) -> str:
    """``subject predicate = value`` with the evidence and the date when the record has them."""
    subject, predicate = ref(data.get("subject"), names), data.get("predicate")
    line = f"{subject} {predicate} = {value(data.get('value'), names)}"
    evidence = data.get("evidence")
    if evidence:
        line += f"  <- {evidence_of(evidence, names)}"
    if "observable_from" in data:
        line += f"  (from {data['observable_from']})"
    return line


def gap(data: Json, names: Names) -> str:
    return (
        f"{ref(data.get('subject'), names)} {data.get('predicate')} = GAP"
        f"  <- {evidence_of(data.get('evidence', {}), names)}"
        f"  (from {data.get('observable_from')})"
    )


def evidence_of(evidence: Json, names: Names) -> str:
    """``source target.field``; a whole-record evidence has no field and reads without one."""
    field = evidence.get("field")
    where = ref(evidence.get("target"), names)
    return f"{evidence.get('source')} {where}" + (f".{field}" if field else "")


def instant(data: Json | None) -> str:
    if data is None:
        return "—"
    return f"{data.get('at')} [{data.get('timezone')}]"


def span(data: Json | None) -> str:
    if data is None:
        return "—"
    return f"{data.get('start')} … {data.get('end')}"


def quoted(text: str) -> list[str]:
    return ["> " + text.replace("\n", "\n> "), ""]


# --- Sections -----------------------------------------------------------------------------


def header(
    version: str, spec: Json, truth: Json, record: Any, notes: Sequence[str] = ()
) -> list[str]:
    prov = spec.get("provenance", {})
    facts = truth.get("facts", {})
    out = [f"# Audit sheet, world `{version[:12]}…`", ""]
    out.append(f"- world version `{version}`")
    out.append(
        f"- seed {prov.get('seed')}, start {prov.get('world_start')}, "
        f"plan {prov.get('plan_name')}, "
        f"generator version {prov.get('generator_version')}, semantic digest "
        f"`{str(prov.get('semantic_digest'))[:12]}…`"
    )
    params = spec.get("org", {}).get("params", {})
    out.append("- org parameters: " + ", ".join(f"{name}={val}" for name, val in params.items()))
    out.append(
        "- outcome witness: the semantic world rebuilt from this provenance by the generator's "
        "assembly, semantic digest verified equal; per impact the generator's own assessment "
        "at the scenario's `now` under the dated view"
    )
    for role, configured in (("writer", record.writer), ("checker", record.checker)):
        settings = [(s.name, s.value) for s in configured.settings]
        out.append(f"- {role} `{configured.model_id}` {settings}")
    out.append("- prompt digests: " + ", ".join(f"{n} `{d[:8]}`" for n, d in record.prompt_digests))
    out.append(
        f"- attempt cap {record.attempt_cap}, prose targets {len(record.targets)}, "
        f"scenarios {len(truth.get('scenarios', []))}, fact base "
        f"{len(facts.get('facts', []))} facts, {len(facts.get('gaps', []))} gaps"
    )
    if record.metrics is not None:
        out.append(
            "- record counters: " + ", ".join(f"{n}={v}" for n, v in record.metrics.counters)
        )
    out += [f"- {note}" for note in notes]
    out.append("")
    return out


def rollups(record: Any, briefs: Json, texts: Mapping[str, str]) -> list[str]:
    by_register: dict[str, list[int]] = defaultdict(list)
    reason_totals: Counter[str] = Counter()
    guard_totals: Counter[str] = Counter()
    frames: dict[str, Counter[str]] = defaultdict(Counter)
    above_four = []
    for target in record.targets:
        register = briefs.get(target.target_id, {}).get("register", "?")
        by_register[register].append(target.attempts)
        if target.attempts > 4:
            above_four.append((target.target_id, target.attempts))
        for refusal in target.refusals:
            guard_totals[refusal.guard.value] += 1
            for reason, count in refusal.reasons or ():
                reason_totals[reason.value] += count
        text = texts.get(target.target_id, "")
        if text.startswith("["):
            text = text.split("] ", 1)[-1]
        frames[register][" ".join(text.split()[:4])] += 1

    out = ["## Rollups", ""]
    for register, attempts in sorted(by_register.items()):
        hist = Counter(attempts)
        out.append(
            f"- {register}: {len(attempts)} targets, first-attempt {hist.get(1, 0)}, "
            f"attempts histogram {dict(sorted(hist.items()))}"
        )
    out.append(f"- refusals by guard: {dict(guard_totals)}")
    out.append(f"- refusal findings by reason: {dict(reason_totals)}")
    out.append(f"- targets accepted above attempt four (struggling briefs): {above_four or 'none'}")
    out.append("- opening frames (first four words) per register:")
    for register, counter in sorted(frames.items()):
        for frame, count in counter.most_common():
            out.append(f'    - {register}: {count} × "{frame} …"')
    out.append("")
    return out


def key_section(key: Json, stable_interval: Json | None, names: Names) -> list[str]:
    out = ["#### Key", ""]
    out.append(f"- stable interval {span(stable_interval)}")
    out.append(f"- required sources: {', '.join(key.get('required_sources', [])) or 'none'}")
    for impact in key.get("impacts", []):
        ik = impact.get("key", {})
        out.append(
            f"- impact {ik.get('subtype')} on {ref(ik.get('artifact'), names)} "
            f"(leave {ik.get('leave_id')}) -> outcome **{impact.get('outcome')}**"
        )
        for authored in impact.get("must_assess", []):
            reasons = ", ".join(authored.get("reasons", [])) or "no reason"
            out.append(
                f"    - must assess {names(authored.get('employee_id'))}: "
                f"**{authored.get('verdict')}** ({reasons})"
            )
    for constraint in key.get("constraints", []):
        out.append(
            f"- constraint {constraint.get('clause_id')} applies to "
            f"{ref(constraint.get('applies_to'), names)}"
        )
    for distractor in key.get("distractors", []):
        out.append(
            f"- distractor {ref(distractor.get('entity'), names)}: {distractor.get('reason')}"
        )
    for conflict in key.get("expected_conflicts", []):
        out.append(
            f"- expected conflict on {ref(conflict.get('entity'), names)} "
            f"{conflict.get('predicate')}: resolves to "
            f"{value(conflict.get('resolved_value'), names)} by {conflict.get('authority_rule')}"
        )
    for unknown in key.get("expected_unknowns", []):
        out.append(
            f"- expected unknown for {names(unknown.get('employee_id'))}: "
            f"{unknown.get('required_fact')} of {ref(unknown.get('subject'), names)} "
            f"({unknown.get('reason')})"
        )
    out.append("")
    return out


def witness_section(scenario: Scenario, org: OrgSpec, facts: FactBase, names: Names) -> list[str]:
    """The generator's own outcome per impact at the scenario's ``now`` under the dated view:
    the three calls the whole-world verification makes, rendered, with every non-viable and
    unknown candidate named and its agreement with the key stated.

    The facts every candidate's assessment read are the need's own (the event's schedule,
    the ticket's component, the clause's requirement) and are rendered once per impact; a
    non-viable candidate is listed with the rule's reasons and every fact beyond those,
    whatever its subject, since the excluding fact is as often another entity's (a clashing
    meeting's schedule, a leave record) as the person's. A candidate with no fact beyond the
    need's carries no excluding fact from the rule: the criterion is known false against
    the person's own record (a skill the record does not list, an employment type the
    clause does not admit), and that record is in the criterion universe below. The sheet
    once said "failed by absence" here, a phrase the panel found colliding with closure's
    "absent", the gap that yields an unknown; the two are different findings. An unknown
    candidate is listed with each unresolved question. The leaver is marked. ``must_assess``
    is compared verdict by verdict too, so the sheet says in its own words whether the
    sealed key is what the rules derive today.
    """
    today = scenario.spec.today
    view = facts.at(today, RunCondition.all_reachable())
    universe = [employee.id for employee in org.employees]
    leave = scenario.investigated_leave.span
    leaver = scenario.investigated_leave.employee_id
    timezone = scenario.spec.reference_timezone

    def who(employee_id: Any) -> str:
        return names(employee_id) + (" [the leaver]" if employee_id == leaver else "")
    out = [
        f"#### Outcome witness (dated view at {today}, the generator's own assessment "
        "over every employee)",
        "",
    ]
    for expected in scenario.key.impacts:
        assessments = assess_impact(
            view, expected.key, universe, scenario.key.constraints, leave, timezone
        )
        required = required_count_for(view, expected.key, scenario.key.constraints, leave, timezone)
        outcome = expected_action((a.verdict for a in assessments), required)
        by_verdict: dict[str, list[Assessment]] = defaultdict(list)
        for assessment in assessments:
            by_verdict[assessment.verdict.value].append(assessment)
        viable = by_verdict.get("viable", [])
        unknown = by_verdict.get("unknown", [])
        non_viable = by_verdict.get("non_viable", [])
        agreement = (
            "agrees with the key"
            if outcome is expected.outcome
            else f"**DISAGREES WITH THE KEY ({expected.outcome.value})**"
        )
        out.append(
            f"- impact {expected.key.subtype.value} on {names(expected.key.artifact.id)}: "
            f"required {required}; viable {len(viable)}, unknown {len(unknown)}, "
            f"non-viable {len(non_viable)} -> **{outcome.value}**, {agreement}"
        )
        shared = set.intersection(*(set(a.evidence) for a in assessments))
        for need_fact in sorted(shared, key=lambda f: (f.subject.id, f.predicate.value)):
            out.append(f"    - need: {fact_text(need_fact, names)}")
        out.append("    - viable: " + (", ".join(who(a.employee_id) for a in viable) or "none"))
        for assessment in unknown:
            questions = "; ".join(
                f"{u.predicate.value} of {names(u.subject.id)} ({u.reason.value})"
                for u in assessment.unresolved
            )
            out.append(f"    - {who(assessment.employee_id)}: unknown, {questions}")
        for assessment in non_viable:
            reasons = ", ".join(reason.value for reason in assessment.reasons)
            beyond = [fact_text(f, names) for f in assessment.evidence if f not in shared]
            excluded = "; ".join(beyond) or (
                "no excluding fact from the rule: known false on the record, "
                "see the criterion universe"
            )
            out.append(f"    - {who(assessment.employee_id)}: non-viable, {reasons} ({excluded})")
        by_employee = {a.employee_id: a for a in assessments}
        mismatched = [
            f"{names(authored.employee_id)} authored {authored.verdict.value} "
            f"{[r.value for r in authored.reasons]}, derived "
            f"{by_employee[authored.employee_id].verdict.value} "
            f"{[r.value for r in by_employee[authored.employee_id].reasons]}"
            for authored in expected.must_assess
            if (
                by_employee[authored.employee_id].verdict,
                by_employee[authored.employee_id].reasons,
            )
            != (authored.verdict, authored.reasons)
        ]
        out.append(
            "    - must-assess verdicts: "
            + (
                "every authored verdict derived"
                if not mismatched
                else "**MISMATCH** " + "; ".join(mismatched)
            )
        )
    out.append("")
    return out


def need_window(view: FactView, artifact: EntityRef, leave: DateSpan, timezone: str) -> str:
    """The days the need covers, as the checklist states them: the investigated leave's span
    for a deadline or a responsibility, the meeting's day in the reference timezone for a
    meeting. The meeting's schedule is a fact read; unreadable at ``now``, said so."""
    if artifact.kind is not EntityKind.EVENT:
        return f"{leave.start} … {leave.end} (the investigated leave's span)"
    scheduled = view.facts_about(artifact, PredicateName.SCHEDULED_AT)
    if not scheduled:
        return "unreadable: the meeting has no visible schedule at now"
    span = scheduled[0].value
    assert isinstance(span, InstantSpan)
    days = span.local_dates(timezone)
    return f"{days.start} … {days.end} (the meeting's day in {timezone})"


def window_days(view: FactView, artifact: EntityRef, leave: DateSpan, timezone: str) -> DateSpan:
    """The need's days as a span, for the overlap reads; the leave's when unreadable."""
    if artifact.kind is EntityKind.EVENT:
        scheduled = view.facts_about(artifact, PredicateName.SCHEDULED_AT)
        if scheduled:
            span = scheduled[0].value
            assert isinstance(span, InstantSpan)
            return span.local_dates(timezone)
    return leave


def with_source(item: Fact, names: Names, world_start: date) -> str:
    """A fact's value with its source, and its date when it entered after the world's start:
    ``ios (corpus clause_019, from 2026-09-24)`` beside ``python (frappe)``."""
    rendered = typed_value(item.value, item.predicate, names)
    where = item.source.value
    if item.evidence.target.kind is not EntityKind.EMPLOYEE:
        where += f" {names(item.evidence.target.id)}"
    if item.observable_from > world_start:
        where += f", from {item.observable_from}"
    return f"{rendered} ({where})"


def universe_section(
    scenario: Scenario, org: OrgSpec, facts: FactBase, names: Names, world_start: date
) -> list[str]:
    """Every employee's facts of the four families the criteria read, per impact, under the
    dated view at the scenario's ``now``: the human's material for proving an outcome over
    the whole organization without the rule's count (the module docstring says why).

    Per impact the block states the need's window, the artifact's component and every
    constraint in the key with what its clause requires, all as facts, so the reader
    derives the active criteria (the checklist's trace step 3) before reading the people.
    Then one line per employee in id order: component memberships; the skills the record
    lists with their sources, or the record's absence as a gap; every leave overlapping the
    window and every event on the window's days the person attends, with the event's
    schedule; the employment type. Nothing here is graded: a leave listed is a fact, not a
    verdict, and an event listed under a deadline need is a fact the rule never asks about.
    """
    today = scenario.spec.today
    view = facts.at(today, RunCondition.all_reachable())
    leave = scenario.investigated_leave.span
    leaver = scenario.investigated_leave.employee_id
    timezone = scenario.spec.reference_timezone
    out = [
        f"#### Criterion universe (dated view at {today}, every employee's facts the criteria "
        "read, no rule applied)",
        "",
    ]
    for expected in scenario.key.impacts:
        artifact = expected.key.artifact
        out.append(f"- impact {expected.key.subtype.value} on {names(artifact.id)}")
        out.append(f"    - need window: {need_window(view, artifact, leave, timezone)}")
        if artifact.kind is EntityKind.WORK_ITEM:
            components = view.facts_about(artifact, PredicateName.IN_COMPONENT)
            out.append(
                "    - artifact's component: "
                + (", ".join(fact_text(f, names) for f in components) or "none visible")
            )
        for constraint in scenario.key.constraints:
            stated = view.facts_about(clause_ref(constraint.clause_id), PredicateName.REQUIRES)
            out.append(
                f"    - constraint {constraint.clause_id} names "
                f"{constraint.applies_to.kind.value}:{names(constraint.applies_to.id)}; "
                + (
                    "; ".join(fact_text(f, names) for f in stated)
                    or "no visible requirement at now"
                )
            )
        days = window_days(view, artifact, leave, timezone)
        attended_by: dict[EntityRef, list[EntityRef]] = defaultdict(list)
        for attendance in view.facts_of(PredicateName.ATTENDS_EVENT):
            assert isinstance(attendance.value, EntityRef)
            attended_by[attendance.value].append(attendance.subject)
        for employee in org.employees:
            who = employee_ref(employee.id)
            members = [
                names(f.value.id) if isinstance(f.value, EntityRef) else str(f.value)
                for f in view.facts_about(who, PredicateName.MEMBER_OF_COMPONENT)
            ]
            skills = [
                with_source(f, names, world_start)
                for f in view.facts_about(who, PredicateName.HAS_SKILL)
            ]
            if view.gaps_about(who, PredicateName.HAS_SKILL):
                skills.append("skills record absent (GAP)")
            leaves = [
                f"{f.value.start} … {f.value.end}"
                for f in view.facts_about(who, PredicateName.ON_LEAVE)
                if isinstance(f.value, DateSpan) and f.value.overlaps(days)
            ]
            events: list[str] = []
            for event in attended_by.get(who, []):
                for scheduled in view.facts_about(event, PredicateName.SCHEDULED_AT):
                    span = scheduled.value
                    assert isinstance(span, InstantSpan)
                    if span.local_dates(timezone).overlaps(days):
                        when = typed_value(span, PredicateName.SCHEDULED_AT, names)
                        events.append(f"{names(event.id)} {when}")
            employed = [
                typed_value(f.value, PredicateName.EMPLOYED_AS, names)
                for f in view.facts_about(who, PredicateName.EMPLOYED_AS)
            ]
            mark = " [the leaver]" if employee.id == leaver else ""
            out.append(
                f"    - {names(employee.id)}{mark}: components [{', '.join(members)}]; "
                f"skills [{', '.join(skills) or 'none listed'}]; "
                f"leaves over the window [{', '.join(leaves) or 'none'}]; "
                f"events on the window's days [{', '.join(events) or 'none'}]; "
                f"employed_as {', '.join(employed) or '—'}"
            )
        out.append(f"    - {len(org.employees)} employees listed")
    out.append("")
    return out


def plantings_section(owned: Json, names: Names) -> list[str]:
    out = ["#### Plantings", ""]
    for planted in owned.get("leaves", []):
        r = planted["record"]
        out.append(
            f"- leave {r['id']}: {names(r['employee_id'])} {r['start']} … {r['end']}, "
            f"{r['kind']}, {r['status']} (observable from {planted['observable_from']})"
        )
    for planted in owned.get("work_items", []):
        r = planted["record"]
        out.append(
            f'- work item {r["id"]} "{r["title"]}": owner {names(r.get("owner_id"))}, '
            f"{r['status']}, component {names(r.get('component_id'))}, opened {r['opened_on']}, "
            f"due {r.get('due_on') or '—'}, resolved {r.get('resolved_on') or '—'} "
            f"(observable from {planted['observable_from']})"
        )
        for comment in r.get("comments", []):
            out.append(
                f"    - comment {comment['id']} by {names(comment['author_id'])} on "
                f"{comment['world_date']}: {comment['text']}"
            )
    for planted in owned.get("events", []):
        r = planted["record"]
        out.append(
            f'- event {r["id"]} "{r["title"]}": '
            f"{instant(r.get('start'))} … {instant(r.get('end'))}, "
            f"attendees {', '.join(names(a) for a in r.get('attendee_ids', []))} "
            f"(observable from {planted['observable_from']})"
        )
    for planted in owned.get("documents", []):
        r = planted["record"]
        out.append(
            f'- document {r["id"]} "{r["title"]}": {r["kind"]}, '
            f"effective from {r['effective_from']} "
            f"(observable from {planted['observable_from']})"
        )
        for section in r.get("sections", []):
            out.append(f"    - section {section['id']}: {section['text']}")
    out.append("")
    return out


def cited_ids(key: Json, spec_row: Json, owned: Json) -> set[str]:
    """Every entity id the key or the scenario's plantings name: the deep trace's subjects."""
    ids: set[str | None] = set()

    def add_ref(data: Json | None) -> None:
        if data:
            ids.add(data.get("id"))

    for impact in key.get("impacts", []):
        add_ref(impact.get("key", {}).get("artifact"))
        for authored in impact.get("must_assess", []):
            ids.add(authored.get("employee_id"))
    for constraint in key.get("constraints", []):
        add_ref(constraint.get("applies_to"))
        ids.add(constraint.get("clause_id"))
    for distractor in key.get("distractors", []):
        add_ref(distractor.get("entity"))
    for conflict in key.get("expected_conflicts", []):
        add_ref(conflict.get("entity"))
    for unknown in key.get("expected_unknowns", []):
        ids.add(unknown.get("employee_id"))
        add_ref(unknown.get("subject"))
    ids.add(spec_row.get("leave_id"))
    for kind in ("leaves", "work_items", "events", "documents"):
        for planted in owned.get(kind, []):
            r = planted["record"]
            ids.add(r["id"])
            ids.add(r.get("employee_id") or r.get("owner_id"))
    return {id for id in ids if id is not None}


def fact_base_section(facts: Json, ids: set[str], names: Names, today: str) -> list[str]:
    """The fact-base entries whose subject or evidence target the scenario cites, the ones
    in the dated view first and the ones observable only after ``now`` apart under their
    own heading: a cited entity's whole record includes other scenarios' later plantings,
    and a reader counts only the dated view."""

    def cited(entry: Json) -> bool:
        subject = (entry.get("subject") or {}).get("id")
        target = ((entry.get("evidence") or {}).get("target") or {}).get("id")
        return subject in ids or target in ids

    def in_view(entry: Json) -> bool:
        return str(entry.get("observable_from", "")) <= today

    entries = [(entry, fact) for entry in facts.get("facts", []) if cited(entry)]
    entries += [(entry, gap) for entry in facts.get("gaps", []) if cited(entry)]
    dated = sorted(render(entry, names) for entry, render in entries if in_view(entry))
    later = sorted(render(entry, names) for entry, render in entries if not in_view(entry))
    out = ["#### Fact base, cited entries (in the dated view)", ""]
    out += [f"- {row}" for row in dated] or ["- none"]
    out.append("")
    if later:
        out += [
            "#### Fact base, cited entries observable only after now (other scenarios' "
            "plantings; not in this dated view; excluded from a released golden scenario, "
            "kept in a throwaway example)",
            "",
        ]
        out += [f"- {row}" for row in later]
        out.append("")
    return out


def target_section(target: Any, brief: Json, text: str, names: Names) -> list[str]:
    tgt = brief.get("target", {})
    where = tgt.get("work_item_id") or tgt.get("document_id")
    author = (
        f", by {names(tgt.get('author_id'))} on {tgt.get('world_date')}"
        if tgt.get("author_id")
        else ""
    )
    out = [
        f"##### {target.target_id} — {brief.get('register', '?')} in {where}, "
        f"position {tgt.get('position')}{author}"
    ]
    out.append(
        f"- accepted on attempt {target.attempts}; request `{target.request_digest[:8]}`, "
        f"body `{target.accepted_body_digest[:8]}`"
    )
    for refusal in target.refusals:
        reasons = ", ".join(f"{count} {reason.value}" for reason, count in (refusal.reasons or ()))
        out.append(
            f"- attempt {refusal.attempt}: refused by {refusal.guard.value} "
            f"({refusal.count}: {reasons})"
        )
    for required in brief.get("required", []):
        out.append(f"- required ({required.get('role')}): {fact(required.get('fact', {}), names)}")
    for allowed in brief.get("allowed", []):
        out.append(f"- allowed: {fact(allowed, names)}")
    out.append(
        "- propositions read: "
        + "; ".join(
            f"{names(p.subject.id) if p.subject else 'text'} {p.predicate.value} "
            f"{typed_value(p.value, p.predicate, names)} "
            f"[{p.polarity.value}/{p.assertion_mode.value}]"
            for p in target.propositions
        )
    )
    out.append("")
    out += quoted(text)
    return out


def scenario_section(
    row: Json,
    construction: Json,
    spec_row: Json,
    planting: Json,
    facts: Json,
    record_targets: Mapping[str, Any],
    texts: Mapping[str, str],
    names: Names,
    witness: list[str],
    universe: list[str],
    today: str,
) -> list[str]:
    key = construction.get("key", {})
    owned = planting.get("owned", {})
    modifiers = ", ".join(key.get("modifiers", [])) or "none"
    out = [
        f"### {row['scenario_id']} — tier {key.get('tier')}, {key.get('scenario_class')}, "
        f"modifiers {modifiers}",
        "",
        f"- asked: leave {spec_row.get('leave_id')}, now {instant(spec_row.get('now'))}, "
        f"reference timezone {spec_row.get('reference_timezone')}, "
        f"window {span(spec_row.get('window'))}",
        "",
    ]
    out += key_section(key, planting.get("stable_interval"), names)
    out += witness
    out += universe
    out += plantings_section(owned, names)
    authored = construction.get("authored_facts", [])
    if authored:
        out += (
            ["#### Authored facts", ""] + [f"- {fact(entry, names)}" for entry in authored] + [""]
        )
    out += fact_base_section(facts, cited_ids(key, spec_row, owned), names, today)
    briefs = construction.get("briefs", [])
    if briefs:
        out += ["#### Prose targets", ""]
        for brief in briefs:
            tid = brief.get("target", {}).get("id")
            target = record_targets.get(tid)
            if target is None:
                out += [f"##### {tid} — no materialization record", ""]
                continue
            out += target_section(
                target, brief, texts.get(tid, "(text not found in the world spec)"), names
            )
    return out


# --- Assembly -----------------------------------------------------------------------------


def walk_texts(node: Any, found: dict[str, str]) -> None:
    """Every comment and section text in the world spec, keyed by id, found by shape."""
    if isinstance(node, dict):
        for comment in node.get("comments", []) or []:
            if isinstance(comment, dict) and "text" in comment:
                found[comment.get("id")] = comment["text"]
        for section in node.get("sections", []) or []:
            if isinstance(section, dict) and "text" in section:
                found[section.get("id")] = section["text"]
        for child in node.values():
            walk_texts(child, found)
    elif isinstance(node, list):
        for item in node:
            walk_texts(item, found)


def by_id(rows: Iterable[Json], field: str) -> dict[str, Json]:
    return {row[field]: row for row in rows}


def render(
    version: str,
    spec: Json,
    truth: Json,
    specs: Sequence[Json],
    record: Any,
    semantic: SemanticWorld,
    notes: Sequence[str] = (),
) -> str:
    names = Names(spec.get("org", {}))
    texts: dict[str, str] = {}
    walk_texts(spec, texts)
    constructions = {c["key"]["scenario_id"]: c for c in truth.get("scenarios", [])}
    spec_rows = by_id(specs, "id")
    plantings = by_id(spec.get("scenarios", []), "scenario_id")
    briefs = {b["target"]["id"]: b for c in truth.get("scenarios", []) for b in c.get("briefs", [])}
    record_targets = {t.target_id: t for t in record.targets}
    scenarios = {scenario.spec.id: scenario for scenario in semantic.scenarios}
    world_start = date.fromisoformat(spec["provenance"]["world_start"])

    out = header(version, spec, truth, record, notes)
    out += rollups(record, briefs, texts)
    out += ["## Scenarios, in the plan's order", ""]
    for row in spec.get("plan", []):
        sid = row["scenario_id"]
        scenario = scenarios[sid]
        out += scenario_section(
            row,
            constructions.get(sid, {}),
            spec_rows.get(sid, {}),
            plantings.get(sid, {}),
            truth.get("facts", {}),
            record_targets,
            texts,
            names,
            witness_section(scenario, semantic.org, semantic.facts, names),
            universe_section(scenario, semantic.org, semantic.facts, names, world_start),
            scenario.spec.today.isoformat(),
        )
    return "\n".join(out)


def main() -> int:
    if sys.argv[1:2] == ["--throwaway"]:
        try:
            unsealed = throwaway_bundle(sys.argv[2:])
        except ConfigurationError as error:
            print(f"audit_sheet --throwaway: {error}", file=sys.stderr)
            return 2
        version = unsealed.world_version
        spec_bytes, specs_bytes, truth_bytes = (a.content for a in unsealed.artifacts)
        notes: Sequence[str] = THROWAWAY_NOTES
        path = EXAMPLE_PATH
    else:
        version = WorldVersion(sys.argv[1])
        s3 = boto3.Session(region_name=REGION).client("s3")
        spec_bytes = fetch(s3, TRUTH_BUCKET, world_spec_key(version))
        specs_bytes = fetch(s3, WORLD_BUCKET, scenario_specs_key(version))
        truth_bytes = fetch(s3, TRUTH_BUCKET, truth_manifest_key(version))
        notes = ()
        path = OUT_DIR / f"audit_sheet_{version[:8]}.md"
    spec = json.loads(spec_bytes)
    specs = json.loads(specs_bytes).get("scenarios", [])
    truth = json.loads(truth_bytes)
    record = decode_materialization(truth_bytes)
    assert record is not None, "no materialization record sealed"
    semantic = rebuild(spec)

    sheet = render(version, spec, truth, specs, record, semantic, notes)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sheet, encoding="utf-8")
    print(f"wrote {path}")
    print(sheet[: sheet.index("## Scenarios, in the plan's order")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
