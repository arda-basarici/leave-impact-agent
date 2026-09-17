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
sources, expected conflicts and unknowns), the plantings with dates (leaves, work items
with their comments, events, documents with their sections), the scenario's authored
facts, the fact-base entries whose subject or evidence the scenario cites (the deep
audit's trace material, each with its evidence and observable-from date), and the prose
targets with their briefs, attempts, refusals and the checker's propositions beside the
accepted text. Before the scenarios, a header (versions, models, prompt digests, sealed
counters) and the rollups the audit items read off (attempts per register, refusals by
guard and by reason, targets above attempt four, opening frames per register).

Reads only. The rendered sheet holds benchmark truth: it is written under ``data/audit/``,
which the repository ignores, and is never committed; the provenance artifact the audit
produces from it is versioned into the truth bucket beside the world.

Usage: ``python scripts/audit_sheet.py <world_version>`` with ``AWS_PROFILE`` set.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import boto3

from leaveimpact.adapters.object_store.layout import (
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.generator.truth_record import decode_materialization

TRUTH_BUCKET = os.environ.get("LEAVE_IMPACT_TRUTH_BUCKET", "leave-impact-truth-445743457479")
WORLD_BUCKET = os.environ.get("LEAVE_IMPACT_WORLD_BUCKET", "leave-impact-world-445743457479")
REGION = os.environ.get("LEAVE_IMPACT_AWS_REGION", "eu-central-1")
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "audit"

Json = Mapping[str, Any]


# --- Reading ------------------------------------------------------------------------------


def fetch(s3: Any, bucket: str, key: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


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


def header(version: str, spec: Json, truth: Json, record: Any) -> list[str]:
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
            "- sealed counters: " + ", ".join(f"{n}={v}" for n, v in record.metrics.counters)
        )
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


def fact_base_section(facts: Json, ids: set[str], names: Names) -> list[str]:
    """The dated fact-base entries whose subject or evidence target the scenario cites."""

    def cited(entry: Json) -> bool:
        subject = (entry.get("subject") or {}).get("id")
        target = ((entry.get("evidence") or {}).get("target") or {}).get("id")
        return subject in ids or target in ids

    out = ["#### Fact base, cited entries", ""]
    rows = [fact(entry, names) for entry in facts.get("facts", []) if cited(entry)]
    rows += [gap(entry, names) for entry in facts.get("gaps", []) if cited(entry)]
    out += [f"- {row}" for row in sorted(rows)] or ["- none"]
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
            f"{names(p.subject.id) if p.subject else 'text'} {p.predicate.value} {p.value} "
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
    out += plantings_section(owned, names)
    authored = construction.get("authored_facts", [])
    if authored:
        out += (
            ["#### Authored facts", ""] + [f"- {fact(entry, names)}" for entry in authored] + [""]
        )
    out += fact_base_section(facts, cited_ids(key, spec_row, owned), names)
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


def render(version: str, spec: Json, truth: Json, specs: Sequence[Json], record: Any) -> str:
    names = Names(spec.get("org", {}))
    texts: dict[str, str] = {}
    walk_texts(spec, texts)
    constructions = {c["key"]["scenario_id"]: c for c in truth.get("scenarios", [])}
    spec_rows = by_id(specs, "id")
    plantings = by_id(spec.get("scenarios", []), "scenario_id")
    briefs = {b["target"]["id"]: b for c in truth.get("scenarios", []) for b in c.get("briefs", [])}
    record_targets = {t.target_id: t for t in record.targets}

    out = header(version, spec, truth, record)
    out += rollups(record, briefs, texts)
    out += ["## Scenarios, in the plan's order", ""]
    for row in spec.get("plan", []):
        sid = row["scenario_id"]
        out += scenario_section(
            row,
            constructions.get(sid, {}),
            spec_rows.get(sid, {}),
            plantings.get(sid, {}),
            truth.get("facts", {}),
            record_targets,
            texts,
            names,
        )
    return "\n".join(out)


def main() -> int:
    version = WorldVersion(sys.argv[1])
    s3 = boto3.Session(region_name=REGION).client("s3")
    truth_bytes = fetch(s3, TRUTH_BUCKET, truth_manifest_key(version))
    spec = json.loads(fetch(s3, TRUTH_BUCKET, world_spec_key(version)))
    specs = json.loads(fetch(s3, WORLD_BUCKET, scenario_specs_key(version))).get("scenarios", [])
    truth = json.loads(truth_bytes)
    record = decode_materialization(truth_bytes)
    assert record is not None, "no materialization record sealed"

    sheet = render(version, spec, truth, specs, record)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"audit_sheet_{version[:8]}.md"
    path.write_text(sheet, encoding="utf-8")
    print(f"wrote {path}")
    print(sheet[: sheet.index("## Scenarios, in the plan's order")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
