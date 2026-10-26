"""The written formats bumped with no vocabulary behind them (the demo milestone's live-path
step, its first group): what each readable set admits and refuses, that a log keeps the
format it was admitted under through every digest the tree cites, and that the fifteen
format 3 histories read under the new code to the digests computed on the tree before the
bump.

The pins in ``tests/fixtures/format3-digests-c83392b.json`` were written at commit c83392b
by a scratch script evaluating ``log_digest`` over each history and ``event_digest`` over its
admission event, both as that tree computed them; here the same histories, re-stamped to
format 3, are digested by the code that writes format 4 and held to those values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from leaveimpact.agent.log_events import (
    LOG_FORMAT_VERSION,
    READABLE_LOG_FORMATS,
    Admitted,
    event_bytes,
    event_digest,
    log_digest,
    log_format_of,
)
from leaveimpact.agent.log_reader import export_format_of
from leaveimpact.core.inventory import (
    INVENTORY_FORMAT_VERSION,
    READABLE_INVENTORY_FORMATS,
    decode_inventory_bytes,
    inventory_bytes,
)
from leaveimpact.core.run_export import EXPORT_FORMAT_VERSION, READABLE_EXPORT_FORMATS
from leaveimpact.core.run_export_json import decode_export_bytes, decode_run_export, export_bytes
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.test_core_inventory import INVENTORY

FIXTURES = Path(__file__).parents[1] / "fixtures"
PINS: dict[str, dict[str, object]] = json.loads(
    (FIXTURES / "format3-digests-c83392b.json").read_text(encoding="utf-8")
)


def test_the_written_format_is_the_last_readable_one_in_every_document() -> None:
    assert READABLE_LOG_FORMATS[-1] == LOG_FORMAT_VERSION == 4
    assert READABLE_EXPORT_FORMATS[-1] == EXPORT_FORMAT_VERSION == 4
    assert READABLE_INVENTORY_FORMATS[-1] == INVENTORY_FORMAT_VERSION == 2
    assert [export_format_of(version) for version in READABLE_LOG_FORMATS] == list(
        READABLE_EXPORT_FORMATS
    )
    with pytest.raises(ValueError, match="no export format is mapped for log format 2"):
        export_format_of(2)


def test_the_pins_cover_every_format_3_history_once() -> None:
    assert list(PINS) == list(cases.SEALED_AT_FORMAT_3)
    assert set(histories.HISTORIES) - set(PINS) == {"a declined attempt"}


@pytest.mark.parametrize("name", list(cases.SEALED_AT_FORMAT_3))
def test_a_format_3_history_digests_as_the_tree_before_the_bump_digested_it(name: str) -> None:
    history = histories.at_format(histories.HISTORIES[name](), 3)
    pin = PINS[name]
    assert pin["log_format"] == 3 and log_format_of(history) == 3
    assert log_digest(history) == pin["log_digest"]
    first = history[0].event
    assert isinstance(first, Admitted)
    assert event_digest(first, log_format=3) == pin["inputs_digest"]


def test_a_digest_moves_with_the_logs_format_and_not_with_the_writer() -> None:
    history = histories.HISTORIES["a cut call"]()
    older = histories.at_format(history, 3)
    assert log_format_of(history) == 4 and log_format_of(older) == 3
    assert log_digest(history) != log_digest(older)
    event = history[1].event
    assert event_bytes(event, log_format=3) != event_bytes(event, log_format=4)
    assert b'"log_format":3' in event_bytes(event, log_format=3)
    assert log_format_of(()) == LOG_FORMAT_VERSION
    with pytest.raises(ValueError, match="a log begins with its admission, got segment_started"):
        log_format_of(history[1:])


def test_frozen_inputs_admit_every_readable_log_format_and_refuse_another() -> None:
    inputs = histories.inputs(reservation=5)
    assert inputs.log_format_version == LOG_FORMAT_VERSION
    assert replace(inputs, log_format_version=3).log_format_version == 3
    with pytest.raises(ValueError, match="this code reads log formats 3 and 4, got 2"):
        replace(inputs, log_format_version=2)
    with pytest.raises(ValueError, match="this code reads log formats 3 and 4, got 5"):
        replace(inputs, log_format_version=5)


def test_the_published_sets_export_reads_as_format_3_byte_for_byte() -> None:
    content = (FIXTURES / "replay-scenario-004-export.json").read_bytes()
    sidecar = json.loads(
        (FIXTURES / "replay-scenario-004-export.sidecar.json").read_text(encoding="utf-8")
    )
    export = decode_export_bytes(content)
    assert export.format_version == 3
    assert export_bytes(export) == content
    assert hashlib.sha256(content).hexdigest() == sidecar["sha256"]


def test_an_export_outside_the_readable_set_refuses_before_anything_else() -> None:
    data = json.loads(export_bytes(cases.FIXTURES["a cut call"]()))
    assert data["format_version"] == 3
    for version in (2, 5):
        data["format_version"] = version
        with pytest.raises(ValueError, match=f"reads export formats 3 and 4, got {version}"):
            decode_run_export(data)


def test_a_format_1_inventory_reads_as_format_1_and_one_outside_the_set_refuses() -> None:
    assert INVENTORY.format_version == INVENTORY_FORMAT_VERSION
    older = replace(INVENTORY, format_version=1)
    assert decode_inventory_bytes(inventory_bytes(older)) == older
    assert decode_inventory_bytes(inventory_bytes(older)).format_version == 1
    assert inventory_bytes(older) != inventory_bytes(INVENTORY)
    with pytest.raises(ValueError, match="this code reads inventory formats 1 and 2, got 3"):
        replace(INVENTORY, format_version=3)
