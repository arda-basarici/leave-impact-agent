"""The phase C evaluation reader: the reported artifact's tables, printed from the file.

FINDINGS cites the reported evaluation's numbers (each arm's correct-whole count, the
primary comparison and its interval, the tier breakdowns, the level contrasts, the
mechanism stages, the arms not run) and a number cited needs a script in the tree behind
it. This reads one evaluation artifact the evaluator job sealed and prints those tables;
it computes nothing the artifact does not already hold, so a figure printed here is the
artifact's own, and a disagreement between a printed figure and a document is a document
error. The operational side (cost per cell, calls, saturation) is `tally.py`'s, read from
the runs' exports rather than from the evaluation.

The artifact is read from a local path rather than fetched, so the script runs without
credentials; the file's sha256 and the identity it reads back (format, label, world
version, inventory digest, run count) are checked against the values recorded below,
which are the reported evaluation's, so a different artifact, or the same one altered,
is refused by name rather than printed as if it were the one FINDINGS cites. Fetching
the file is one command in the runbook.

Usage, from the repository root:

    uv run python probes/phase-c-dispatch/report.py \
        data/phase-c-dispatch/evaluation-39061375799-1.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPORTED = {
    "sha256": "fc0607bb65c5535de2280268a785029e866e66cdb9418797e1cc975a86ea0721",
    "format_version": 10,
    "label": "reported",
    "world": "2e6705ba7d11095a9b797abe08495c5497a7c5fe560fa587868763f11192341c",
    "inventory_digest": "6adafc5d19238c26662e68639a9f07b8ac9fbe44351863d670a21a10508d9621",
    "runs": 240,
}
SYSTEM_ORDER = ["agent", "full_context", "single_shot", "rules_only"]
TIERS = ["structured", "fragmented", "adversarial"]


def refuse_unless_reported(artifact: dict, raw: bytes) -> None:
    found = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "format_version": artifact["format_version"],
        "label": artifact["label"],
        "world": artifact["world"]["version"],
        "inventory_digest": artifact["harness_inventory"]["digest"],
        "runs": len(artifact["listing"]),
    }
    differing = {k: (REPORTED[k], found[k]) for k in REPORTED if REPORTED[k] != found[k]}
    if differing:
        raise SystemExit(f"not the reported evaluation; differing (expected, found): {differing}")


def interval_text(interval: dict | None, unresolved: str | None) -> str:
    if interval is None:
        return f"[{unresolved}]"
    return f"{interval['low']:+.2f} to {interval['high']:+.2f}"


def stratum_row(rows: list[dict], kind: str, name: str) -> dict:
    (row,) = [r for r in rows if r["stratum"] == {"kind": kind, "name": name}]
    return row


def check_of(cell: dict, check: str, reading: str) -> dict:
    (row,) = [c for c in cell["checks"] if c["check"] == check and c["reading"] == reading]
    return row


def measure_of(cell: dict, measure: str) -> dict:
    (row,) = [m for m in cell["measures"] if m["measure"] == measure]
    return row


def arm_name(arm: dict) -> str:
    return f"{arm['system']['kind']} {arm['level']}"


def arm_order(arm: dict) -> tuple[int, str]:
    return SYSTEM_ORDER.index(arm["system"]["kind"]), arm["level"]


def count_text(numerator: int | float, denominator: int) -> str:
    return f"{int(numerator)} of {denominator}"


def print_identity(artifact: dict) -> None:
    registration = artifact["registration"]
    inventory = artifact["harness_inventory"]
    coverage = artifact["coverage"]
    plan = artifact["analysis"]["plan"]
    incidents = artifact["analysis"]["incidents"] + artifact["analysis"]["provenance_incidents"]
    changed = ", ".join(c["path"] for c in artifact["evaluator"]["changed"])
    print("identity")
    print(f"  format {artifact['format_version']}, label {artifact['label']}")
    print(f"  world {artifact['world']['version']}")
    print(f"  evaluator commit {artifact['evaluator']['commit']}")
    print(
        f"  registration {registration['status']}, frozen at {registration['frozen_commit']}, "
        f"digest {registration['digest']}"
    )
    print(f"  evaluated_by_changed_code {artifact['evaluated_by_changed_code']}: {changed}")
    print(
        f"  inventory {inventory['digest']} at {inventory['attempts']} attempts, "
        f"taken {inventory['taken_at']}"
    )
    print("  coverage " + ", ".join(f"{k} {v}" for k, v in coverage.items() if k != "unexported"))
    print(
        f"  plan: confidence {plan['confidence']}, resamples {plan['resamples']}, "
        f"counted attempt {plan['counted_attempt']}, missing repeat {plan['missing_repeat']}"
    )
    print(f"  incidents {len(incidents)}")


def print_arms(arms: list[dict]) -> None:
    print("\narms: correct whole end to end, passed of scenarios, Wilson 95 percent; by tier")
    print(
        f"  {'arm':<22}{'overall':>9}{'wilson':>15}"
        + "".join(f"{t:>14}" for t in TIERS)
        + f"{'strict precision':>18}"
    )
    for arm in sorted(arms, key=arm_order):
        overall = stratum_row(arm["cells"], "overall", "overall")
        check = check_of(overall, "correct_whole", "end_to_end")
        wilson = f"{check['wilson']['low']:.2f} to {check['wilson']['high']:.2f}"
        tiers = [
            check_of(stratum_row(arm["cells"], "tier", tier), "correct_whole", "end_to_end")
            for tier in TIERS
        ]
        precision = measure_of(overall, "strict precision: all claims")
        print(
            f"  {arm_name(arm):<22}{count_text(check['passed'], check['scenarios']):>9}{wilson:>15}"
            + "".join(f"{count_text(t['passed'], t['scenarios']):>14}" for t in tiers)
            + f"{count_text(precision['numerator'], precision['denominator']):>18}"
        )


def print_comparison(title: str, comparison: dict) -> None:
    if comparison.get("unavailable") is not None:
        print(f"\n{title}: unavailable, {comparison['unavailable']}")
        return
    overall = comparison["overall"]
    print(f"\n{title}: {overall['first_arm']} against {overall['second_arm']}")
    print(
        f"  {'stratum':<14}{'paired':>7}{'first':>7}{'second':>8}{'both':>6}{'first only':>12}"
        f"{'second only':>13}{'neither':>9}{'difference, 95 percent':>25}"
    )
    for row in [overall] + comparison["breakdowns"]:
        both, first_only, second_only, neither = row["two_by_two"]
        print(
            f"  {row['stratum']['name']:<14}{row['paired']:>7}"
            f"{both + first_only:>7}{both + second_only:>8}"
            f"{both:>6}{first_only:>12}{second_only:>13}{neither:>9}"
            f"{interval_text(row['interval'], row['unresolved']):>25}"
        )


def print_mechanism(mechanism: dict) -> None:
    stages = mechanism["stages"]
    print(
        f"\nmechanism, {mechanism['name']}: "
        + " then ".join(stages)
        + ", all predicates, numerator of denominator"
    )
    print(f"  {'arm':<22}" + "".join(f"{s:>12}" for s in stages))
    for arm in sorted(mechanism["arms"], key=arm_order):
        overall = [s for s in arm["stages"] if s["stratum"]["kind"] == "overall"]
        print(
            f"  {arm_name(arm):<22}"
            + "".join(f"{count_text(s['numerator'], s['denominator']):>12}" for s in overall)
        )


def print_headroom_and_unbuilt(analysis: dict) -> None:
    print("\nheadroom: scenarios the rules-only baseline does not pass")
    for row in analysis["headroom"]:
        print(f"  {row['condition']} at {row['level']}: {row['not_passed']} of {row['scenarios']}")
    print("\nnot run")
    for row in analysis["unbuilt"]:
        cell = row["cell"]
        print(
            f"  {cell['system']} under {cell['condition']} at {cell['level']}: "
            f"{row['why']} ({row['detail']})"
        )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: report.py <evaluation artifact path>", file=sys.stderr)
        return 2
    raw = Path(argv[1]).read_bytes()
    artifact = json.loads(raw.decode("utf-8"))
    refuse_unless_reported(artifact, raw)
    analysis = artifact["analysis"]
    print_identity(artifact)
    print_arms(analysis["arms"])
    print_comparison("primary", analysis["primary"])
    for comparison in analysis["secondary"]:
        print_comparison("secondary", comparison)
    for comparison in analysis["level_contrasts"]:
        print_comparison("level contrast", comparison)
    print_mechanism(analysis["mechanism"])
    print_headroom_and_unbuilt(analysis)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
