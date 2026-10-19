"""The committed public results, as CI validates them without truth access: each committed
file is read by package name, is of the declared types at the current format, records the
artifact it was cut from, and holds a commit or a digest only in the fields declared to
hold one, so an embargoed world's digest cannot ride in it unnoticed. The equivalence with
the artifact itself is the offline acceptance command's, not this test's."""

from __future__ import annotations

import json
import re
from typing import cast

from leaveimpact.results.codec import public_results_bytes
from leaveimpact.results.committed import M2_REPORTED, committed_results, committed_results_bytes
from leaveimpact.results.public import PUBLIC_RESULTS_FORMAT, Cell
from tests.unit.test_evaluator_public_results import HEX, HEX_FIELDS, leaves

# The reported evaluation of the investigator milestone's exit (FINDINGS `phase-c`): the
# artifact's byte digest, pinned so a regenerated file from another artifact is a change here.
REPORTED_ARTIFACT = "fc0607bb65c5535de2280268a785029e866e66cdb9418797e1cc975a86ea0721"
SCENARIO_ID = re.compile(r"scenario_\d+")


def test_the_m2_results_are_of_the_declared_types_and_record_the_reported_artifact() -> None:
    results = committed_results(M2_REPORTED)
    assert results.format_version == PUBLIC_RESULTS_FORMAT
    assert results.provenance.artifact_digest == REPORTED_ARTIFACT
    assert results.provenance.label == "reported"
    assert results.provenance.registration_status == "bound"
    assert results.provenance.runs_listed == (("eligible", 240),)
    assert results.disclosures.world_disclosure == "embargoed"
    assert results.disclosures.repeats_per_scenario == 1
    assert public_results_bytes(results) == committed_results_bytes(M2_REPORTED)


def test_the_m2_results_carry_a_digest_or_a_commit_only_where_one_is_declared() -> None:
    text = committed_results_bytes(M2_REPORTED).decode("utf-8")
    assert '"listing"' not in text and not SCENARIO_ID.search(text)
    hex_fields = {
        path
        for path, value in leaves(cast("object", json.loads(text)))
        if isinstance(value, str) and len(value) in (40, 64) and set(value) <= HEX
    }
    assert hex_fields == HEX_FIELDS


def _overall(arm_system: str, level: str) -> Cell:
    (arm,) = [a for a in committed_results().arms if a.system == arm_system and a.level == level]
    (cell,) = [c for c in arm.cells if c.stratum.kind == "overall"]
    return cell


def test_the_m2_results_hold_the_figures_findings_cites() -> None:
    """FINDINGS `phase-c` cites the reported evaluation's headline figures from the probe
    reader over the artifact; the committed file holds the same ones, so a regeneration
    that moved a cited figure is a change here before it is a change in prose."""
    results = committed_results()
    whole = {
        (arm.system, arm.level): next(
            check
            for check in _overall(arm.system, arm.level).checks or ()
            if check.check == "correct_whole" and check.reading == "end_to_end"
        )
        for arm in results.arms
    }
    assert {key: int(check.passed) for key, check in whole.items()} == {
        ("agent", "base"): 24,
        ("agent", "padded"): 24,
        ("full_context", "base"): 30,
        ("full_context", "padded"): 14,
        ("single_shot", "base"): 22,
        ("single_shot", "padded"): 10,
        ("rules_only", "base"): 10,
        ("rules_only", "padded"): 10,
    }
    wilson = whole[("agent", "padded")].wilson
    assert wilson is not None and (round(wilson.low, 2), round(wilson.high, 2)) == (0.63, 0.90)
    primary = results.primary.overall
    assert primary is not None and primary.interval is not None
    assert primary.two_by_two == (14, 10, 0, 6)
    assert (round(primary.interval.low, 2), round(primary.interval.high, 2)) == (0.20, 0.47)
    assert results.mechanism is not None
    stages = {
        (arm.system, arm.level): tuple(
            stage.numerator for stage in arm.stages if stage.stratum.kind == "overall"
        )
        for arm in results.mechanism.arms
    }
    assert stages[("agent", "padded")] == (31, 26, 26, 25)
    assert stages[("full_context", "padded")] == (31, 6, 6, 6)
    total = sum(_overall(arm.system, arm.level).cost.pico_usd for arm in results.arms)
    assert total == 9_959_447_300_000
    assert [(row.not_passed, row.scenarios) for row in results.headroom] == [(20, 30), (20, 30)]
    assert all(
        not cell.accounting.limited and not cell.accounting.excluded
        for arm in results.arms
        for cell in arm.cells
    )
