"""The agent's entry under the instance's environment, which is exactly what `compose.yaml`
hands the container: the names in its ``environment:`` block with the instance's values,
and the image's code version. A command that reaches the object store must get past its
configuration on those names alone; the fourth live dispatch's publish was refused for a
truth-bucket name the application is never given, because that branch still built the
two-bucket stores. The fakes of the lifecycle tests have no such check, so this one reads
the compose file itself."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from leaveimpact.adapters.wiring import (
    ConfigurationError,
    stores_from_env,
    world_store_from_env,
)
from leaveimpact.agent import __main__ as job
from tests.unit.log_store_memory import MemoryLog

COMPOSE = Path(__file__).resolve().parents[2] / "compose.yaml"


class _Log(MemoryLog):
    """The in-memory log as the entry's store: the entry closes what it was handed."""

    def close(self) -> None:
        pass


INSTANCE_VALUES = {
    "DATABASE_URL": "postgresql://leaveimpact:x@postgres:5432/leaveimpact",
    "LEAVE_IMPACT_WORLD_BUCKET": "leave-impact-world-445743457479",
    "LEAVE_IMPACT_AWS_REGION": "eu-central-1",
}


def compose_environment() -> dict[str, str]:
    """The app service's environment as the instance has it: every name compose passes,
    the deploy's values for the store, empty for the rest (compose's ``:-`` defaults), and
    the image's code version, which the Dockerfile sets and compose does not."""
    text = COMPOSE.read_text()
    block = re.search(r"^  app:\n(.*?)^  postgres:", text, re.MULTILINE | re.DOTALL)
    assert block is not None, "compose.yaml names the app service before postgres"
    names = re.findall(r"^      ([A-Z_]+):", block.group(1), re.MULTILINE)
    assert "LEAVE_IMPACT_WORLD_BUCKET" in names
    env = {name: INSTANCE_VALUES.get(name, "") for name in names}
    env["LEAVEIMPACT_CODE_VERSION"] = "a" * 40
    return env


def test_compose_never_names_the_truth_bucket() -> None:
    env = compose_environment()
    assert "LEAVE_IMPACT_TRUTH_BUCKET" not in env
    with pytest.raises(ConfigurationError, match="TRUTH_BUCKET"):
        stores_from_env(env)
    store = world_store_from_env(env)
    assert store.bucket == INSTANCE_VALUES["LEAVE_IMPACT_WORLD_BUCKET"]


def test_the_publish_command_gets_past_its_configuration_on_compose_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The entry builds the publisher from the environment before it reads the log, and a
    configuration fault is exit 2 by its contract: under compose's names the command gets
    past that point. What ends it is the in-memory log's refusal of an attempt it does not
    hold, exit 1, which comes after the publisher was built and before any put; the S3
    client is constructed and never called."""
    line = ["publish", "--run", "run-12", "--attempt", "1"]
    status = job.main(line, compose_environment(), _Log())  # type: ignore[arg-type]
    err = capsys.readouterr().err
    assert status != 2, err
    assert "TRUTH_BUCKET" not in err and "is not set" not in err
