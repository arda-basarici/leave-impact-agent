"""The job seam's command line: each command parses to its request type, the publish and
inventory commands take this code's commit from the image's identity variable and refuse
without it, the rules come from the registration file (each pending value ``None``, and
the rules of a system that calls no model with no file), the admission request's file
decodes to the request the store takes, a malformed line or file is a configuration
fault, and a missing database is one too."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from leaveimpact.adapters.object_store.layout import world_manifest_key
from leaveimpact.adapters.wiring import ConfigurationError
from leaveimpact.agent import __main__ as job
from leaveimpact.agent.commands import (
    AbandonRequest,
    ApprovalDelivery,
    ImportRequest,
    InventoryRequest,
    PublishRequest,
    ThresholdRequest,
    WorkRequest,
)
from leaveimpact.agent.log_events import Admitted, Producer, encode_event
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import (
    DEVELOPMENT_ATTRIBUTION_TABLE,
    DEVELOPMENT_REDISPATCH_POLICY,
    RoleFilling,
)
from leaveimpact.agent.worker import AutomaticApproval, HumanApproval
from leaveimpact.core.call_settings import CallConfiguration, CallSetting
from leaveimpact.core.inventory import InventoryScope
from leaveimpact.core.registration_json import registration_bytes
from leaveimpact.core.run_ending import AbandonmentReason
from leaveimpact.core.run_record import PricingSelection
from leaveimpact.core.run_timing import HarnessRevision, TreeState
from tests.unit import format_fixtures as cases
from tests.unit import worker_support as support
from tests.unit.registration_fixture import DRAFT, named

COMMIT = "a" * 40
ENV = {job.CODE_VERSION: COMMIT}
ABOUT = ["--run", "run-12", "--attempt", "1"]
WORK = [
    "work",
    *ABOUT,
    "--nonce",
    "nonce-1",
    "--launch",
    "launcher:test",
    "--condition",
    "normal",
    "--level",
    "base",
    "--registration-commit",
    cases.COMMIT,
    "--model",
    "eu.vendor.model-v1",
    "--counting-model",
    "vendor.model-v1",
    "--context-allowance",
    "200000",
    "--max-tokens",
    "1024",
    "--temperature",
    "0",
    "--pricing-key",
    "vendor.model-v1",
    "--region",
    "eu-central-1",
]
PRICES = {
    "currency": "USD",
    "effective_from": "2026-09-01",
    "rates": [
        {
            "pricing_key": "vendor.model-v1",
            "region": "eu-central-1",
            "billing_mode": "on_demand",
            "token_class": token_class,
            "pico_usd_per_token": 1_100_000,
            "when_absent": "unknown",
        }
        for token_class in ("input_tokens", "output_tokens")
    ],
}


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
    imported = job.parse_request(
        [
            "import-spend",
            "--request",
            "import-1",
            "--ledger",
            "l",
            "--amount",
            "12",
            "--authority",
            "import:spike-2026-10-04",
            "--registration-commit",
            cases.COMMIT,
        ],
        {},
    )
    assert imported.request == ImportRequest(
        "import-1", "l", 12, "import:spike-2026-10-04", cases.COMMIT
    )
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
    assert job.rules_of(draft) == Rules(
        DEVELOPMENT_ATTRIBUTION_TABLE, DEVELOPMENT_REDISPATCH_POLICY
    ), "the draft holds both pending, so a run under it is read by the development values"
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


def test_the_work_line_parses_to_its_request_under_a_registration() -> None:
    parsed = job.parse_request(
        [*WORK, "--registration", "reg.json", "--prices", "prices.json", "--approval", "human"],
        ENV,
    )
    assert parsed.command is job.Command.WORK and parsed.registration == Path("reg.json")
    assert parsed.request == job.WorkLine(
        WorkRequest("run-12", 1, "nonce-1", "launcher:test"),
        "normal",
        "base",
        cases.COMMIT,
        RoleFilling(
            "investigator",
            CallConfiguration(
                "eu.vendor.model-v1",
                (CallSetting("max_tokens", 1024), CallSetting("temperature", 0)),
            ),
            PricingSelection("vendor.model-v1", "eu-central-1", "on_demand"),
            "vendor.model-v1",
            200_000,
        ),
        Path("prices.json"),
        "eu-central-1",
        HarnessRevision(COMMIT, TreeState.CLEAN),
        HumanApproval(),
    )
    default = job.parse_request([*WORK, "--registration", "r.json", "--prices", "p.json"], ENV)
    assert isinstance(default.request, job.WorkLine)
    assert default.request.approval == AutomaticApproval()
    with pytest.raises(ConfigurationError, match="work runs under a registration"):
        job.parse_request([*WORK, "--prices", "p.json"], ENV)
    with pytest.raises(ConfigurationError, match="LEAVEIMPACT_CODE_VERSION"):
        job.parse_request([*WORK, "--registration", "r.json", "--prices", "p.json"], {})


class _AdmissionlessStore:
    """A store whose attempt holds no admission; what the work command reads first after
    the registration and the price table."""

    loaded: list[tuple[str, int]] = []

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> Any:
        self.loaded.append((run_id, attempt))
        return SimpleNamespace(inputs=None)

    def close(self) -> None:
        pass


def test_the_work_command_decodes_its_files_composes_the_cell_and_reads_the_admission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The composition's order up to the store: the registration and the price table are
    decoded under the configuration phase, the cell's configuration is derived from the
    draft before the store is read, and an attempt with no admission is a refusal; nothing
    further is composed, so no host, store or client is needed."""
    registration = tmp_path / "registration.json"
    registration.write_bytes(registration_bytes(DRAFT))
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps(PRICES), encoding="utf-8")
    line = [*WORK, "--registration", str(registration), "--prices", str(prices)]
    env = {**ENV, job.DATABASE: "postgresql://unused"}
    store = _AdmissionlessStore()
    assert job.main(line, env, store) == 1  # type: ignore[arg-type]
    captured = capsys.readouterr()
    assert "refused: run run-12 attempt 1 holds no admission" in captured.err
    assert store.loaded == [("run-12", 1)]
    # A price table without the role's rate is the registration-phase's refusal, before the store.
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({**PRICES, "rates": []}), encoding="utf-8")
    line_bare = [*WORK, "--registration", str(registration), "--prices", str(bare)]
    status = job.main(line_bare, env, store)  # type: ignore[arg-type]
    assert status == 1 and "no rate for vendor.model-v1" in capsys.readouterr().err
    assert store.loaded == [("run-12", 1)]
    # A file that does not decode is reported by its name and the exception's type alone.
    prices.write_text('{"currency": "SECRET-MARKER-2026"}', encoding="utf-8")
    status = job.main(line, env, store)  # type: ignore[arg-type]
    captured = capsys.readouterr()
    assert status == 2 and "SECRET-MARKER" not in captured.err
    assert "the price table" in captured.err


class _AdmittedStore(_AdmissionlessStore):
    """A store whose attempt holds the fixtures' admission, so the work command reaches the
    world store."""

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> Any:
        self.loaded.append((run_id, attempt))
        return SimpleNamespace(inputs=support.admitted_inputs())


def test_a_manifest_that_does_not_decode_is_reported_without_what_it_held(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The group's review, second finding: the manifest codec's refusal names the fields it
    found, so a malformed object in the world store could print its own field names to the
    public log; the entry reports the key and the exception's type."""
    registration = tmp_path / "registration.json"
    registration.write_bytes(registration_bytes(DRAFT))
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps(PRICES), encoding="utf-8")
    version = support.admitted_inputs().context.world_version
    held = tmp_path / "store" / "world" / world_manifest_key(version)
    held.parent.mkdir(parents=True)
    held.write_text('{"SECRET-MARKER-2026": 1}', encoding="utf-8")
    env = {
        **ENV,
        job.DATABASE: "postgresql://unused",
        "LEAVE_IMPACT_OBJECT_STORE_ROOT": str(tmp_path / "store"),
    }
    line = [*WORK, "--registration", str(registration), "--prices", str(prices)]
    status = job.main(line, env, _AdmittedStore())  # type: ignore[arg-type]
    captured = capsys.readouterr()
    assert status == 1 and captured.out == ""
    assert "SECRET-MARKER" not in captured.err
    assert "the world manifest at" in captured.err and "ValueError" in captured.err
    held.unlink()
    status = job.main(line, env, _AdmittedStore())  # type: ignore[arg-type]
    assert status == 1 and "holds no manifest at worlds/" in capsys.readouterr().err


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


def test_a_request_file_that_does_not_decode_is_reported_without_what_it_held(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The group's review, first finding: a codec's refusal quotes the value it refused, and
    the job's log is public; the entry prints the file's name and the exception's type."""
    tree = encode_event(Admitted(support.admitted_inputs()))
    tree["inputs"]["context"]["now"]["at"] = "SECRET-MARKER-2026"  # type: ignore[index]
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {"request_id": "r", "admitter": "a", "ledger_id": None, "admitted": tree}
        ),
        encoding="utf-8",
    )
    status = job.main(["admit", "--request", str(request)], {})
    captured = capsys.readouterr()
    assert status == 2 and captured.out == ""
    assert "SECRET-MARKER" not in captured.err
    assert "the request file" in captured.err and "ValueError" in captured.err
    registration = tmp_path / "registration.json"
    registration.write_text('{"format_version": "SECRET-MARKER-2026"}', encoding="utf-8")
    status = job.main(["publish", *ABOUT, "--registration", str(registration)], ENV)
    captured = capsys.readouterr()
    assert status == 2 and "SECRET-MARKER" not in captured.err
    assert "the registration" in captured.err
    status = job.main(["admit", "--request", str(tmp_path / "absent.json")], {})
    captured = capsys.readouterr()
    assert status == 2 and "absent.json" in captured.err and "FileNotFoundError" in captured.err
