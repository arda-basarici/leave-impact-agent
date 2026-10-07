"""The job seam's command line: each command parses to its request type, the publish and
inventory commands take this code's commit from the image's identity variable and refuse
without it, the rules come from the registration file (each pending value ``None``, and
the rules of a system that calls no model with no file), the admission request's file
decodes to the request the store takes, a malformed line or file is a configuration
fault, and a missing database is one too."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from leaveimpact.adapters.wiring import ConfigurationError
from leaveimpact.agent import __main__ as job
from leaveimpact.agent.commands import (
    AbandonRequest,
    ApprovalDelivery,
    InventoryRequest,
    PublishRequest,
    ThresholdRequest,
)
from leaveimpact.agent.log_events import Admitted, Producer, encode_event
from leaveimpact.agent.log_transition import Rules
from leaveimpact.core.inventory import InventoryScope
from leaveimpact.core.registration_json import registration_bytes
from leaveimpact.core.run_ending import AbandonmentReason
from tests.unit import format_fixtures as cases
from tests.unit import worker_support as support
from tests.unit.registration_fixture import DRAFT, named

COMMIT = "a" * 40
ENV = {job.CODE_VERSION: COMMIT}
ABOUT = ["--run", "run-12", "--attempt", "1"]


def test_each_command_parses_to_its_request() -> None:
    delivered = job.parse_request(
        ["deliver-approval", *ABOUT, "--approver", "approver:a", "--payload-digest", "f" * 64], {}
    )
    assert delivered.request == ApprovalDelivery("run-12", 1, "approver:a", "f" * 64)
    assert delivered.command is job.Command.DELIVER_APPROVAL and delivered.registration is None
    abandoned = job.parse_request(
        ["abandon", *ABOUT, "--authority", "operator:x", "--reason", "cancelled"], {}
    )
    assert abandoned.request == AbandonRequest(
        "run-12", 1, "operator:x", AbandonmentReason.CANCELLED
    )
    published = job.parse_request(["publish", *ABOUT, "--registration", "reg.json"], ENV)
    assert published.request == PublishRequest("run-12", 1, COMMIT)
    assert published.registration == Path("reg.json")
    listed = job.parse_request(
        [
            "inventory",
            "--world-version",
            "ab" * 32,
            "--registration-commit",
            cases.COMMIT,
            "--ledger",
            "l",
        ],
        ENV,
    )
    assert listed.request == InventoryRequest(InventoryScope("ab" * 32, cases.COMMIT, "l"), COMMIT)  # type: ignore[arg-type]
    threshold = job.parse_request(
        [
            "set-threshold",
            "--ledger",
            "l",
            "--amount",
            "5",
            "--authority",
            "operator:x",
            "--registration-commit",
            cases.COMMIT,
            "--limit",
            "9",
        ],
        {},
    )
    assert threshold.request == ThresholdRequest("l", 5, "operator:x", cases.COMMIT, 9)
    admitting = job.parse_request(["admit", "--request", "req.json"], {})
    assert admitting.request == job.AdmitFile(Path("req.json"))


@pytest.mark.parametrize(
    "argv",
    [
        ["work", *ABOUT],
        ["publish", "--run", "run-12"],
        ["abandon", *ABOUT, "--authority", "x", "--reason", "bored"],
        [],
    ],
)
def test_a_line_that_is_no_command_is_a_configuration_fault(argv: list[str]) -> None:
    with pytest.raises(ConfigurationError, match="not a command"):
        job.parse_request(argv, ENV)


def test_publish_and_inventory_refuse_without_this_codes_commit() -> None:
    with pytest.raises(
        ConfigurationError, match="LEAVEIMPACT_CODE_VERSION is the forty-hex commit"
    ):
        job.parse_request(["publish", *ABOUT], {})
    with pytest.raises(ConfigurationError, match="LEAVEIMPACT_CODE_VERSION"):
        job.parse_request(["publish", *ABOUT], {job.CODE_VERSION: "abc"})


def test_the_rules_come_from_the_registration_file_or_are_a_model_free_systems(
    tmp_path: Path,
) -> None:
    assert job.rules_of(None) == Rules(None, None)
    draft = tmp_path / "draft.json"
    draft.write_bytes(registration_bytes(DRAFT))
    assert job.rules_of(draft) == Rules(None, None), "the draft's table and policy are pending"
    settled = tmp_path / "settled.json"
    settled.write_bytes(registration_bytes(named(DRAFT)))
    rules = job.rules_of(settled)
    assert rules.table is not None and rules.redispatch is not None
    assert rules == Rules(named(DRAFT).attribution, named(DRAFT).run_accounting.redispatch)  # type: ignore[arg-type]


def test_the_admission_requests_file_decodes_to_the_request_the_store_takes() -> None:
    inputs = support.admitted_inputs()
    content = json.dumps(
        {
            "request_id": "req-1",
            "admitter": "launcher:test",
            "ledger_id": "ledger-1",
            "admitted": encode_event(Admitted(inputs)),
        }
    )
    request = job.admission_request_of(content, Rules(None, None))
    assert (request.request_id, request.admitter, request.ledger_id) == (
        "req-1",
        Producer("launcher:test"),
        "ledger-1",
    )
    assert request.inputs == inputs
    with pytest.raises(ValueError, match="surplus"):
        job.admission_request_of(json.dumps({"request_id": "r", "extra": 1}), Rules(None, None))


def test_a_missing_database_is_a_configuration_fault(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        job.main(
            [
                "set-threshold",
                "--ledger",
                "l",
                "--amount",
                "1",
                "--authority",
                "x",
                "--registration-commit",
                cases.COMMIT,
                "--limit",
                "2",
            ],
            {},
        )
        == 2
    )
    assert "DATABASE_URL names the run log's database" in capsys.readouterr().err
    assert job.main(["publish", *ABOUT], {}) == 2
    assert "LEAVEIMPACT_CODE_VERSION" in capsys.readouterr().err
