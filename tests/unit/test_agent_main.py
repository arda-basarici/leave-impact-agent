"""The job seam's command line: each command parses to its request type, the publish and
inventory commands take this code's commit from the image's identity variable and refuse
without it, the rules come from the registration file (each pending value ``None``, and
the rules of a system that calls no model with no file), the admission request's file
decodes to the request the store takes, a malformed line or file is a configuration
fault, a missing database is one too, and an attempt at a recorded stop is closed over the
run log alone."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.adapters.object_store.layout import world_manifest_key
from leaveimpact.adapters.wiring import ConfigurationError
from leaveimpact.agent import __main__ as job
from leaveimpact.agent.commands import (
    AbandonRequest,
    ApprovalDelivery,
    ImportRequest,
    InventoryRequest,
    PublishRequest,
    ReviewRequest,
    ThresholdRequest,
    WorkRequest,
)
from leaveimpact.agent.graph import NoPreparation
from leaveimpact.agent.log_events import Admitted, EventKind, Producer, encode_event, kind_of
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import (
    DEVELOPMENT_ATTRIBUTION_TABLE,
    DEVELOPMENT_REDISPATCH_POLICY,
    RoleFilling,
    effective_rules,
    model_system_provenance,
)
from leaveimpact.agent.worker import AutomaticApproval, HumanApproval, Worker
from leaveimpact.core.call_settings import CallConfiguration, CallSetting
from leaveimpact.core.inventory import InventoryScope
from leaveimpact.core.pricing import basis_for, decode_price_table
from leaveimpact.core.registration_json import registration_bytes
from leaveimpact.core.run_ending import AbandonmentReason
from leaveimpact.core.run_record import FailureCategory, PricingSelection, SystemKind
from leaveimpact.core.run_timing import HarnessRevision, TreeState
from tests.unit import format_fixtures as cases
from tests.unit import worker_support as support
from tests.unit.log_store_memory import MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.registration_fixture import DRAFT, named, pending_roles
from tests.unit.throwaway_world import loaded_world

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
    "--system",
    "agent",
]
"""The investigator's work line; the system is the last pair, so ``for_system`` can swap it."""


def for_system(system: str) -> list[str]:
    """``WORK`` naming ``system`` as the cell's system."""
    return [*WORK[:-2], "--system", system]


RULES_ONLY_WORK = [
    *WORK[: WORK.index("--model")],
    "--region",
    "eu-central-1",
    "--system",
    "rules_only",
]
"""The work line of a rules-only cell: the cell, the registration's commit and the region,
no model flag."""


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
            "when_absent": when_absent,
        }
        for token_class, when_absent in (
            ("input_tokens", "unknown"),
            ("output_tokens", "unknown"),
            ("cache_read_input_tokens", "zero"),
            ("cache_write_input_tokens", "zero"),
        )
    ],
}
"""One rate for the four classes a dispatch's worst case is priced over; the two cache
classes read as zero when a response omits them, as the committed table's do."""


def test_each_command_parses_to_its_request() -> None:
    reviewed = job.parse_request(["review-approval", *ABOUT, "--registration", "reg.json"], {})
    assert reviewed.request == ReviewRequest("run-12", 1)
    assert reviewed.command is job.Command.REVIEW_APPROVAL
    assert reviewed.registration == Path("reg.json")
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
        SystemKind.AGENT,
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
    # The baselines step, fork 15: the line names the cell's system, and the role filled is
    # the one that system runs, the reader for both one-call baselines.
    for system in ("single_shot", "full_context"):
        reader = job.parse_request(
            [*for_system(system), "--registration", "r.json", "--prices", "p.json"], ENV
        )
        assert isinstance(reader.request, job.WorkLine)
        assert reader.request.system is SystemKind(system)
        assert reader.request.role is not None and reader.request.role.name == "reader"
    # The first live run's step, fork 4: rules only runs through the same line with no
    # model flag; a model flag on it is refused by name, as a missing one is on a model system.
    with pytest.raises(ConfigurationError, match="rules only runs no model; --model, .* refused"):
        job.parse_request(
            [*for_system("rules_only"), "--registration", "r.json", "--prices", "p.json"], ENV
        )
    rules_only = job.parse_request(
        [*RULES_ONLY_WORK, "--registration", "r.json", "--prices", "p.json"], ENV
    )
    assert isinstance(rules_only.request, job.WorkLine)
    assert rules_only.request.system is SystemKind.RULES_ONLY and rules_only.request.role is None
    with pytest.raises(ConfigurationError, match="agent runs a model; --model, --counting-model"):
        job.parse_request(
            [*RULES_ONLY_WORK[:-2], "--system", "agent", "--registration", "r.json"]
            + ["--prices", "p.json"],
            ENV,
        )
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
    registration.write_bytes(registration_bytes(pending_roles(DRAFT)))
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
        return SimpleNamespace(inputs=support.admitted_inputs(), closed=None, stopped=None)


def test_a_manifest_that_does_not_decode_is_reported_without_what_it_held(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The group's review, second finding: the manifest codec's refusal names the fields it
    found, so a malformed object in the world store could print its own field names to the
    public log; the entry reports the key and the exception's type."""
    registration = tmp_path / "registration.json"
    registration.write_bytes(registration_bytes(pending_roles(DRAFT)))
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


class _Log(MemoryLog):
    """The in-memory log as the entry's store: the entry closes what it was handed."""

    def close(self) -> None:
        pass


def test_an_attempt_at_a_recorded_stop_is_closed_over_the_run_log_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The FIXLOG's session-86 case, ruled as fork 9 of the first live run's step: the log
    holds a recorded stopping failure and its segment was never ended (the process died
    between the stop and its closing); the work command closes the attempt by that failure
    through the terminal worker, under an environment that names no object store, no vendor
    host and no database, so any store the path reached would have failed it. The export
    then carries the recorded ending and the dead segment's unrecorded end.

    The history is made by the real worker over the configuration the line composes, since
    the terminal path compares the two before it claims; the throttled script fails the
    first call by infrastructure at its last dispatch's send.
    """
    registration = pending_roles(DRAFT)
    registration_file = tmp_path / "registration.json"
    registration_file.write_bytes(registration_bytes(registration))
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps(PRICES), encoding="utf-8")
    line = [*WORK, "--registration", str(registration_file), "--prices", str(prices)]
    parsed = job.parse_request(line, ENV).request
    assert isinstance(parsed, job.WorkLine) and parsed.role is not None
    configuration = model_system_provenance(
        registration,
        SystemKind.AGENT,
        "normal",
        "base",
        preregistration_commit=cases.COMMIT,
        pricing=basis_for(decode_price_table(PRICES), (parsed.role.pricing,)),
        role=parsed.role,
    )
    rules = effective_rules(registration)
    world = loaded_world("golden")
    context = world.context_of(world.scenarios[0])
    inputs = configuration.frozen_for(support.admitted_inputs(context))
    turns, client = support.throttled_script(context)
    worked = _Log()
    worked.seed(support.admission(inputs))
    Worker(
        worked,
        configuration,
        parsed.harness,
        "launcher:test",
        rules,
        turns,
        NoPreparation(),
        client,
        support.ScriptedCounter(),
        systems_holding(world).ports,
        AutomaticApproval(),
        InMemorySaver(),
        sleep=lambda seconds: None,
    ).work("run-12", 1, nonce="nonce-0")
    events = worked.events("run-12", 1)
    assert kind_of(events[-1].event) is EventKind.FAILED
    stopped = _Log()
    stopped.seed(events[:-1])
    before = stopped.load("run-12", 1, rules=rules)
    assert before.stopped is not None and before.closed is None
    assert before.current_segment is not None and not before.current_segment.ended
    status = job.main(line, ENV, stopped)  # type: ignore[arg-type]
    captured = capsys.readouterr()
    assert status == 0, captured.err
    assert captured.out.splitlines() == [
        "worked=run-12/1",
        "ending=closed",
        "detail=failed",
        "generation=2",
    ]
    export = export_of(stopped.load("run-12", 1, rules=rules))
    failure = export.record.failure
    assert failure is not None and failure.category is FailureCategory.INFRASTRUCTURE
    assert (failure.category, failure.site) == (before.stopped.category, before.stopped.site)
    assert [segment.end_recorded for segment in export.record.timing.segments] == [False, True]
