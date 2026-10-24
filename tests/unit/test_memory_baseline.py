"""The memory baseline's committed reading (`probes/memory-baseline/reading.json`, written
by `reduce.py` over the capture of 2026-10-24) and what was set from it: the reading
regenerates from the committed capture exactly, its rule block is the rule recomputed over
its own levels, and the two Compose limits and the stream's subscription bound equal the
rule's outputs. The limits are numbers with a script behind them; this test is what keeps
`compose.yaml`, the stream module and the reading from moving alone."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from leaveimpact.app.stream import SUBSCRIPTION_BOUND

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "probes" / "memory-baseline"
CAPTURE = ROOT / "probes" / "captures" / "memory-baseline" / "2026-10-24"


@pytest.fixture(scope="module")
def reduce() -> ModuleType:
    spec = importlib.util.spec_from_file_location("memory_baseline_reduce", PROBE / "reduce.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def reading() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((PROBE / "reading.json").read_text(encoding="utf-8")))


def compose_limits() -> dict[str, str]:
    """Each service's `mem_limit` in the production Compose file, by service name."""
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    limits: dict[str, str] = {}
    service = None
    for line in text.splitlines():
        heading = re.match(r"^  (\w+):\s*$", line)
        if heading:
            service = heading.group(1)
        limit = re.match(r"^    mem_limit:\s*(\S+)\s*$", line)
        if limit and service is not None:
            limits[service] = limit.group(1)
    return limits


def test_the_reading_regenerates_from_the_committed_capture(
    reduce: ModuleType, reading: dict[str, Any]
) -> None:
    source = CAPTURE / "host.out.txt"
    assert reading["capture"] == CAPTURE.name
    assert reading["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert cast(Any, reduce).reduce_capture(CAPTURE) == reading


def test_the_rule_block_is_the_rule_over_the_levels(
    reduce: ModuleType, reading: dict[str, Any]
) -> None:
    rule = reading["rule"]
    host_total = reading["host"]["total_bytes"]
    assert cast(Any, reduce).apply_rule(reading["levels"], host_total) == rule
    limit_of = cast(Any, reduce).limit_of
    for name in ("app", "postgres"):
        service = rule[name]
        assert service["limit_bytes"] == limit_of(service["peak_current_bytes"])
        assert service["limit_bytes"] >= service["peak_current_bytes"] * rule["headroom"]
        assert service["limit_bytes"] % rule["rounding_bytes"] == 0
        assert service["limit_clears_headroom_on_kernel_peak"] is True
    assert rule["host"]["fits"] is True, "fork 2: the limits and the reservation under the host"
    assert rule["bound"]["subscription_bound"] is not None, "the combined level fits the limit"


def test_every_level_ran_clean(reading: dict[str, Any]) -> None:
    """The criterion's (a) and (b): no transport error, every page read 200, every stream
    fetch 200 (none reached the bound: a looper's fetch is short), three samples a level."""
    for label, level in reading["levels"].items():
        assert level["samples"] == 3, label
        for container in ("leaveimpact-app-1", "leaveimpact-postgres-1", "proxy-caddy-1"):
            assert "absent" not in level["containers"][container], (label, container)
        if label != "idle":
            loader = level["loader"]
            assert loader["errors"] == 0, label
            assert set(loader["reads"]) <= {"200"}, label
            assert set(loader["stream_fetches"]) <= {"200"}, label


def test_the_limits_and_the_bound_are_the_rules_outputs(reading: dict[str, Any]) -> None:
    rule = reading["rule"]
    limits = compose_limits()
    assert limits["app"] == rule["app"]["mem_limit"]
    assert limits["postgres"] == rule["postgres"]["mem_limit"]
    assert rule["bound"]["subscription_bound"] == SUBSCRIPTION_BOUND
