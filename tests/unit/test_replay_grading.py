"""The replay set's committed grading (`probes/replay-set/grading.json`, written by
`probes/replay-set/grade_replays.py` over the thirty replays' exports): one verdict per key
of the committed plan, every public name distinct and the scenario id's hyphenated form,
every verdict's run and attempt the admission the committed ledger recorded for that key,
the header's counts the verdicts' own, the record of the committed grader over committed inputs,
and a run graded correct whole exactly when its
disagreement list is empty and no oracle finding stands. The file is a record of a paid
batch; this test holds it to the ledger it was graded from so neither drifts alone."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLAN_DIR = ROOT / "probes" / "replay-set"


@pytest.fixture(scope="module")
def grading() -> dict[str, Any]:
    return json.loads((PLAN_DIR / "grading.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plan() -> dict[str, Any]:
    return json.loads((PLAN_DIR / "plan.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def admissions() -> dict[str, str]:
    """Each key's standing admission marker from the committed ledger, a released key
    reading from its later run as the generator and the grader read it."""
    standing: dict[str, str] = {}
    for line in (PLAN_DIR / "ledger.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record["kind"] == "released":
            standing.pop(record["key"], None)
        elif record["kind"] == "finished" and not record["stop_reasons"]:
            standing[record["key"]] = record["markers"]["launch.admitted"]
    return standing


def test_one_verdict_per_plan_key_under_its_scenarios_public_name(
    grading: dict[str, Any], plan: dict[str, Any]
) -> None:
    verdicts: list[dict[str, Any]] = grading["verdicts"]
    assert grading["world_version"] == plan["world_version"]
    assert [row["plan_key"] for row in verdicts] == sorted(plan["order"])
    assert [row["public_id"] for row in verdicts] == [
        key.rsplit("/", 1)[1].replace("_", "-") for key in sorted(plan["order"])
    ]
    assert all(row["scenario_id"] == row["plan_key"].rsplit("/", 1)[1] for row in verdicts)
    assert grading["runs_wanted"] == grading["runs_graded"] == len(plan["order"]) == 30
    assert grading["runs_without_export"] == []


def test_every_verdict_grades_the_run_the_ledger_admitted_for_its_key(
    grading: dict[str, Any], admissions: dict[str, str]
) -> None:
    for row in grading["verdicts"]:
        assert f"{row['run_id']}/{row['attempt']}" == admissions[row["plan_key"]]
        assert re.fullmatch(
            f"runs/{grading['world_version']}/{row['run_id']}-{row['attempt']}/"
            r"export-[0-9a-f]{40}\.json",
            row["export"]["key"],
        )


def test_the_record_is_of_the_committed_grader_and_committed_inputs(
    grading: dict[str, Any],
) -> None:
    """A record names the grader that wrote it: the first one carried a commit the grader
    was not in (the fourth external read). The digest reads line endings as LF, as the
    grader does, so a converting checkout and a plain one agree; a grader change makes
    the record stale until it is regenerated."""
    grader = PLAN_DIR / "grade_replays.py"
    digest = hashlib.sha256(grader.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert grading["grader_sha256"] == digest, "regenerate grading.json with the committed grader"
    assert grading["inputs_clean"] is True
    assert re.fullmatch(r"[0-9a-f]{40}", grading["tree"])


def test_the_headers_counts_are_the_verdicts_own(grading: dict[str, Any]) -> None:
    verdicts: list[dict[str, Any]] = grading["verdicts"]
    assert grading["correct_whole"] == sum(1 for row in verdicts if row["correct_whole"] is True)
    for tier, counts in grading["by_tier"].items():
        of_tier = [row for row in verdicts if row["tier"] == tier]
        assert counts == {
            "runs": len(of_tier),
            "correct_whole": sum(1 for row in of_tier if row["correct_whole"] is True),
        }
    assert sum(counts["runs"] for counts in grading["by_tier"].values()) == len(verdicts)


def test_correct_whole_is_no_disagreement_and_no_oracle_finding(grading: dict[str, Any]) -> None:
    for row in grading["verdicts"]:
        assert row["outcome"] == "graded"
        whole = not row["disagreements"] and not row["oracle_findings"]
        assert row["correct_whole"] is whole, row["public_id"]
