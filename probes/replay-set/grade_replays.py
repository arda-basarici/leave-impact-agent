"""The replay set graded locally: every export of the plan's admitted runs, read from the
world bucket and graded with the evaluator's own `grade_run` against the golden world, the
outcomes summarized to counts and written beside the plan (the step's fork 5, as amended).

Why local and not an `evaluate-run.yml` dispatch: the golden world's `runs/` prefix holds
eight older runs (the October 13 to 16 development and smoke runs), and a workflow
evaluation orders every run by run id and would take the earliest run of a scenario as the
intended one, so the older runs would take the replays' slots. This probe grades exactly
the runs the replay ledger admitted and nothing else, through the same grader. It is the
operator's reading for the three introduced examples (a pass with a visible limitation, a
miss if any, a refusal or conflict the rules make) and enters no registered comparison.

Reads under the administrator profile from the workstation (`AWS_PROFILE=leave-impact`),
the two buckets the contract names unless the environment names others. The result file
carries scenario ids, tiers, outcome kinds and counts, and for a miss where the rows fall
short in the reading `correct_whole` makes and which plan checks found what, by kind;
never a claim's text, a payload, a person or a world's content. Verdict rows are keyed by
the public name the surface will carry.

    AWS_PROFILE=leave-impact uv run python probes/replay-set/grade_replays.py \
        [--plan-dir probes/replay-set] [--out probes/replay-set/grading.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from leaveimpact.adapters.object_store.layout import runs_prefix
from leaveimpact.adapters.wiring import store_readers, stores_from_env
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.run_export_json import decode_export_bytes
from leaveimpact.evaluator.grading import (
    Excluded,
    Graded,
    Limited,
    action_matches,
    correct_whole,
    grade_run,
)
from leaveimpact.evaluator.harness_inventory import is_inventory_object
from leaveimpact.evaluator.rows import ClaimRows, Expectation
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
ADMITTED = re.compile(r"^(run-\d+)/(\d+)$")
DEFAULT_ENV = {
    "LEAVE_IMPACT_WORLD_BUCKET": "leave-impact-world-445743457479",
    "LEAVE_IMPACT_TRUTH_BUCKET": "leave-impact-truth-445743457479",
    "LEAVE_IMPACT_AWS_REGION": "eu-central-1",
}


def admitted_runs(records: list[dict]) -> dict[str, tuple[str, int]]:
    """Each finished key's admitted run and attempt, a released key reading from its later
    run; a finished record with stop reasons or without an admission is left out and named."""
    standing: dict[str, dict] = {}
    for record in records:
        if record["kind"] == "released":
            standing.pop(record["key"], None)
        elif record["kind"] == "finished":
            standing[record["key"]] = record
    runs: dict[str, tuple[str, int]] = {}
    for key, finished in standing.items():
        admitted = ADMITTED.match(str(finished["markers"].get("launch.admitted") or ""))
        if finished["stop_reasons"] or admitted is None:
            print(
                f"left out: {key} run {finished['run_id']} (stopped or not admitted)",
                file=sys.stderr,
            )
            continue
        runs[key] = (admitted.group(1), int(admitted.group(2)))
    return runs


def summary_of(outcome: Graded | Limited | Excluded) -> dict:
    """The outcome as counts and names: what an operator reads to pick an example, and
    nothing of the report's or the world's text."""
    header = outcome.header
    row: dict = {
        "run_id": header.run_id,
        "attempt": header.attempt,
        "scenario_id": str(header.scenario_id),
        "status": header.status.value,
        "outcome": type(outcome).__name__.lower(),
    }
    if isinstance(outcome, Excluded):
        row["reason"] = outcome.reason.value
        return row
    if isinstance(outcome, Limited):
        row["reason"] = outcome.reason.value
        row["structural_problems"] = len(outcome.structural_problems)
    else:
        row["correct_whole"] = correct_whole(outcome)
        rows = outcome.rows
        row["rows"] = {
            name: len(getattr(rows, name))
            for name in (
                "impacts",
                "constraints",
                "assessments",
                "actions",
                "conflicts",
                "unknowns",
            )
        }
        row["structural_problems"] = len(rows.structural_problems)
        row["disagreements"] = disagreements_of(rows)
        row["oracle_findings"] = (
            None if outcome.oracle_findings is None else len(outcome.oracle_findings)
        )
        row["oracle_finding_kinds"] = (
            None
            if outcome.oracle_findings is None
            else sorted(
                f"{finding.family.value}: "
                + (finding.result if isinstance(finding.result, str) else finding.result.kind.value)
                + (" (uncheckable)" if finding.uncheckable else "")
                for finding in outcome.oracle_findings
            )
        )
    row["condition"] = sorted(source.value for source in outcome.condition.reachable)
    row["report_findings"] = (
        None if outcome.report_findings is None else len(outcome.report_findings)
    )
    row["coverage_gaps"] = None if outcome.coverage is None else len(outcome.coverage)
    row["integrity_findings"] = len(outcome.integrity)
    row["harness_findings"] = len(outcome.harness_findings)
    return row


def disagreements_of(rows: ClaimRows) -> list[str]:
    """Where the rows fall short of correct whole, one line per kind and respect, in the
    reading `correct_whole` makes (an unexpected or unmatched row, a required row nobody
    reported, a reported payload that differs); empty exactly when the rows alone would grade
    the run correct whole. The counts explain a miss without a claim's text."""
    payload_flags = {
        "assessments": lambda row: (row.verdict_matches, row.reasons_match),
        "actions": lambda row: (action_matches(row),),
        "conflicts": lambda row: (row.value_matches, row.rule_matches, row.observations_hold),
        "unknowns": lambda row: (row.reason_matches,),
    }
    lines: list[str] = []
    for kind in ("impacts", "constraints", "assessments", "actions", "conflicts", "unknowns"):
        kind_rows = getattr(rows, kind)
        flags = payload_flags.get(kind, lambda row: ())
        counts = {
            "unexpected": sum(1 for r in kind_rows if r.expectation is Expectation.UNEXPECTED),
            "not matched": sum(1 for r in kind_rows if r.expectation is Expectation.NOT_MATCHED),
            "required and not reported": sum(
                1 for r in kind_rows if r.expectation is Expectation.REQUIRED and r.claim_id is None
            ),
            "payload differs": sum(1 for r in kind_rows if False in flags(r)),
        }
        lines.extend(f"{kind}: {n} {respect}" for respect, n in counts.items() if n)
    return lines


def tier_of(world: SealedWorld, scenario_id: str) -> str | None:
    scenario = world.scenario(ScenarioId(scenario_id))
    return None if scenario is None else str(scenario.key.tier.value)


def grade(plan_dir: Path, env: dict[str, str]) -> dict:
    plan = json.loads((plan_dir / "plan.json").read_text(encoding="utf-8"))
    ledger_bytes = (plan_dir / "ledger.jsonl").read_bytes()
    records = [
        json.loads(line) for line in ledger_bytes.decode("utf-8").splitlines() if line.strip()
    ]
    version = WorldVersion(plan["world_version"])
    readers = store_readers(stores_from_env(env))
    world = load_sealed_world(version, readers.truth, readers.world)
    wanted = admitted_runs(records)
    by_prefix = {
        f"{runs_prefix(version)}{run}-{attempt}/": key for key, (run, attempt) in wanted.items()
    }
    verdicts: list[dict] = []
    for key in sorted(readers.world.list_keys(runs_prefix(version))):
        if is_inventory_object(version, key):
            continue
        prefix = key[: key.rfind("/") + 1]
        plan_key = by_prefix.get(prefix)
        if plan_key is None:
            continue
        stored = readers.world.get(key)
        if stored is None:
            raise RuntimeError(f"{key} was listed and is gone")
        export = decode_export_bytes(stored.content)
        outcome = grade_run(world, export)
        row = summary_of(outcome)
        row["plan_key"] = plan_key
        row["public_id"] = plan_key.rsplit("/", 1)[1].replace("_", "-")
        row["tier"] = tier_of(world, row["scenario_id"])
        row["export"] = {
            "key": key,
            "version_id": stored.version_id,
            "sha256": hashlib.sha256(stored.content).hexdigest(),
            "bytes": len(stored.content),
        }
        verdicts.append(row)
    graded_keys = {row["plan_key"] for row in verdicts}
    missing = sorted(set(wanted) - graded_keys)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, capture_output=True, text=True, check=True
    ).stdout.strip()
    return {
        "world_version": str(version),
        "plan": plan_dir.name,
        "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "graded_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "tree": head,
        "runs_wanted": len(wanted),
        "runs_graded": len(verdicts),
        "runs_without_export": missing,
        "correct_whole": sum(1 for row in verdicts if row.get("correct_whole") is True),
        "by_tier": {
            tier: {
                "runs": sum(1 for row in verdicts if row["tier"] == tier),
                "correct_whole": sum(
                    1
                    for row in verdicts
                    if row["tier"] == tier and row.get("correct_whole") is True
                ),
            }
            for tier in sorted({str(row["tier"]) for row in verdicts})
        },
        "verdicts": sorted(verdicts, key=lambda row: row["public_id"]),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="the replay set graded locally")
    parser.add_argument("--plan-dir", type=Path, default=HERE)
    parser.add_argument("--out", type=Path, default=HERE / "grading.json")
    args = parser.parse_args(argv)
    env = {**DEFAULT_ENV, **{k: v for k, v in os.environ.items() if k.startswith("LEAVE_IMPACT_")}}
    result = grade(args.plan_dir.resolve(), env)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(
        f"{'public id':<14}{'tier':<13}{'outcome':<10}{'whole':<7}{'oracle':<8}{'gaps':<6}"
        f"{'integrity':<10}reason or disagreements"
    )
    for row in result["verdicts"]:
        print(
            f"{row['public_id']:<14}{str(row['tier']):<13}{row['outcome']:<10}"
            f"{str(row.get('correct_whole', '-')):<7}{str(row.get('oracle_findings', '-')):<8}"
            f"{str(row.get('coverage_gaps', '-')):<6}{str(row.get('integrity_findings', '-')):<10}"
            f"{row.get('reason', '')}{'; '.join(row.get('disagreements', ()))}"
        )
    print(
        f"graded {result['runs_graded']} of {result['runs_wanted']} wanted; correct whole "
        f"{result['correct_whole']}; by tier {result['by_tier']}; without export "
        f"{result['runs_without_export']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
