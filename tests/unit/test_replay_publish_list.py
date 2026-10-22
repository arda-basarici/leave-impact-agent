"""The replay set's publish-list generator (`probes/replay-set/publish_list.py`): one
`publish` command per key of the plan in plan order, the run and attempt from the admission
marker and never typed, the public name the scenario id with a hyphen, the publisher
`operator`, a title only where the titles file gives one and quoted for the shell; a refusal
for an unfinished key, a stopped run, a malformed or missing admission, an admission of
another scenario, two rows for one name, and a title naming no row; a released key reads from
its later run. The real replay plan's order is the thirty golden scenarios."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "probes" / "replay-set" / "publish_list.py"
PLAN = ROOT / "probes" / "replay-set" / "plan.json"


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("replay_publish_list", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ORDER = ["agent/base/scenario_001", "agent/base/scenario_002"]


def finished(key: str, run_id: int, admitted: str | None, **markers: str) -> dict[str, Any]:
    scenario = key.rsplit("/", 1)[1]
    return {
        "kind": "finished",
        "key": key,
        "run_id": run_id,
        "stop_reasons": [],
        "markers": {"launch.admitted": admitted, "launch.scenario": scenario, **markers},
    }


def test_one_command_per_key_in_plan_order_with_the_admissions_run_and_attempt(
    generator: ModuleType,
) -> None:
    records = [
        finished(ORDER[1], 72, "run-72/1"),
        finished(ORDER[0], 71, "run-71/2"),
    ]
    lines = generator.publish_list(ORDER, records, {"scenario-002": "A payroll week's leave"})
    assert lines[: len(generator.PREAMBLE)] == list(generator.PREAMBLE)
    assert lines[len(generator.PREAMBLE) :] == [
        "docker compose run --rm app python -m leaveimpact.app publish --run run-71 --attempt 2 "
        "--as scenario-001 --by operator",
        "docker compose run --rm app python -m leaveimpact.app publish --run run-72 --attempt 1 "
        "--as scenario-002 --by operator --title 'A payroll week'\"'\"'s leave'",
    ]


def test_a_released_key_reads_from_its_later_run(generator: ModuleType) -> None:
    records = [
        finished(ORDER[0], 71, None),
        {"kind": "released", "key": ORDER[0]},
        finished(ORDER[0], 73, "run-73/1"),
        finished(ORDER[1], 72, "run-72/1"),
    ]
    rows = generator.rows_of(ORDER, records, {})
    assert [(row["run_id"], row["attempt"]) for row in rows] == [("run-73", 1), ("run-72", 1)]


@pytest.mark.parametrize(
    ("records", "reason"),
    [
        ([finished(ORDER[0], 71, "run-71/1")], "scenario_002 has no finished record"),
        (
            [
                {**finished(ORDER[0], 71, "run-71/1"), "stop_reasons": ["job conclusion failure"]},
                finished(ORDER[1], 72, "run-72/1"),
            ],
            "stopped the driver",
        ),
        (
            [finished(ORDER[0], 71, None), finished(ORDER[1], 72, "run-72/1")],
            "no admission marker",
        ),
        (
            [finished(ORDER[0], 71, "71/1"), finished(ORDER[1], 72, "run-72/1")],
            "no admission marker",
        ),
        (
            [
                {
                    **finished(ORDER[0], 71, "run-71/1"),
                    "markers": {"launch.admitted": "run-71/1", "launch.scenario": "scenario_009"},
                },
                finished(ORDER[1], 72, "run-72/1"),
            ],
            "admitted 'scenario_009', not the key's scenario",
        ),
    ],
)
def test_the_list_refuses_rather_than_guesses(
    generator: ModuleType, records: list[dict[str, Any]], reason: str
) -> None:
    with pytest.raises(generator.Refused, match=reason):
        generator.rows_of(ORDER, records, {})


def test_two_rows_for_one_name_and_a_title_naming_no_row_are_refused(
    generator: ModuleType,
) -> None:
    twice = ["agent/base/scenario_001", "rules_only/base/scenario_001"]
    records = [finished(twice[0], 71, "run-71/1"), finished(twice[1], 72, "run-72/1")]
    with pytest.raises(generator.Refused, match="scenario-001 would name both"):
        generator.rows_of(twice, records, {})
    records = [finished(ORDER[0], 71, "run-71/1"), finished(ORDER[1], 72, "run-72/1")]
    with pytest.raises(generator.Refused, match="titles name no row: scenario-031"):
        generator.rows_of(ORDER, records, {"scenario-031": "nowhere"})


def test_the_committed_plan_names_the_thirty_golden_scenarios(generator: ModuleType) -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert len(plan["order"]) == 30
    names = [generator.public_id_of(key.rsplit("/", 1)[1]) for key in plan["order"]]
    assert names == [f"scenario-{n:03d}" for n in range(1, 31)]
