"""The ``publish`` command over fakes: the row written from a closed run of the served world
with the one line it prints, each of the store's refusals as exit 1 with the reason on
stderr, an identical repeat as exit 0 saying nothing changed, the environment's missing
registration as exit 2, a slug or a registration digest the rules refuse as exit 1 before
any log read, and the log session closed on every path."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from leaveimpact.agent.log_events import LoggedEvent
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.__main__ import main
from leaveimpact.app.public import PublicationDraft, PublicId, PublishableRow
from leaveimpact.app.store import (
    AlreadyPublished,
    AppStoreUnavailable,
    AttemptPublished,
    PublicationConflict,
    Published,
    PublishOutcome,
    SlugTaken,
)
from leaveimpact.core.ids import ScenarioId
from tests.unit import log_histories as histories
from tests.unit.log_store_memory import MemoryLog
from tests.unit.publishable_fixture import (
    CLOSED,
    CONFIGURATION,
    OTHER_WORLD,
    SERVED,
    history_in_world,
)
from tests.unit.registration_fixture import COMMITTED_FILE

DSN = "postgresql://nobody@localhost/none"
ENV = {
    "DATABASE_URL": DSN,
    "LEAVEIMPACT_REGISTRATION_FILE": "/app/preregistration/registration.json",
}
AT = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
ROW = PublishableRow(
    PublicId("example"),
    "run-12",
    1,
    SERVED,
    ScenarioId("scenario_003"),
    "A title",
    AT,
    "operator:a",
)
PUBLISHED = Published(ROW)
PUBLISH = ["publish", "--run", "run-12", "--attempt", "1", "--as", "example", "--by", "operator:a"]


class Session:
    """A log session over the in-memory log, its closing recorded."""

    def __init__(self, memory: MemoryLog) -> None:
        self.memory = memory
        self.closed = False

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        return self.memory.load(run_id, attempt, rules=rules)

    def events_after(
        self, run_id: str, attempt: int, *, after: int
    ) -> tuple[LoggedEvent, ...]:
        return self.memory.events_after(run_id, attempt, after=after)

    def close(self) -> None:
        self.closed = True


class Store:
    """An app store answering ``publish`` with a scripted outcome and keeping the draft."""

    def __init__(self, outcome: PublishOutcome | Exception) -> None:
        self.outcome = outcome
        self.drafts: list[PublicationDraft] = []

    def publish(self, draft: PublicationDraft) -> PublishOutcome:
        self.drafts.append(draft)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class Rig:
    """The seams bound: the log with the served world's closed run and another world's, the
    store, the committed registration's bytes."""

    def __init__(self, outcome: PublishOutcome | Exception = PUBLISHED) -> None:
        memory = MemoryLog()
        memory.seed(history_in_world(CLOSED, SERVED))
        memory.seed(history_in_world(CLOSED, OTHER_WORLD, run_id="run-13"))
        self.session = Session(memory)
        self.store = Store(outcome)
        self.registration_paths: list[str] = []

    def run(self, argv: list[str], env: dict[str, str] | None = None) -> int:
        def registration(path: str) -> bytes:
            self.registration_paths.append(path)
            return COMMITTED_FILE.read_bytes()

        # The fixture histories were admitted under the fixtures' rules, so the command folds
        # under those; the registration's own reading is the read model's test.
        return main(
            argv,
            ENV if env is None else env,
            store=lambda dsn: self.store,  # type: ignore[arg-type, return-value]
            log=lambda dsn: self.session,
            configuration=lambda: CONFIGURATION,
            registration=registration,
            rules=lambda configuration, content: histories.RULES,
        )


def test_a_closed_run_of_the_served_world_is_published_with_the_admissions_world_and_scenario(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rig = Rig()
    assert rig.run([*PUBLISH, "--title", "A title"]) == 0
    assert rig.registration_paths == ["/app/preregistration/registration.json"]
    assert rig.store.drafts == [
        PublicationDraft(
            PublicId("example"),
            "run-12",
            1,
            SERVED,
            ScenarioId("scenario_003"),
            "A title",
            "operator:a",
        )
    ]
    assert rig.session.closed
    assert capsys.readouterr().out == (
        f"published example: run run-12 attempt 1, world {SERVED} scenario scenario_003, at "
        "2026-10-20T12:00:00+00:00 by operator:a\n"
    )


def test_an_identical_repeat_changes_nothing_and_exits_0(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rig = Rig(AlreadyPublished(ROW))
    assert rig.run(PUBLISH) == 0
    assert capsys.readouterr().out == (
        "already published example at 2026-10-20T12:00:00+00:00 by operator:a; nothing changed\n"
    )


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (SlugTaken(ROW), "example already names run run-12 attempt 1"),
        (AttemptPublished(ROW), "run run-12 attempt 1 is already published as example"),
        (
            PublicationConflict(ROW),
            "example is published with title 'A title' by 'operator:a'; a repeat states other "
            "content and changes nothing",
        ),
        (
            AppStoreUnavailable("the app store did not answer: OperationalError"),
            "the app store did not answer",
        ),
    ],
)
def test_the_stores_refusals_exit_1_with_the_reason(
    outcome: PublishOutcome | Exception, reason: str, capsys: pytest.CaptureFixture[str]
) -> None:
    rig = Rig(outcome)
    assert rig.run(PUBLISH) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"leaveimpact.app: refused: {reason}")
    assert rig.session.closed


def test_an_attempt_the_draft_refuses_writes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    rig = Rig()
    other = [*PUBLISH[:2], "run-13", *PUBLISH[3:]]
    assert rig.run(other) == 1
    assert rig.store.drafts == []
    assert rig.session.closed
    assert f"run run-13 attempt 1 is a run of world {OTHER_WORLD}" in capsys.readouterr().err


def test_a_bad_slug_or_a_foreign_registration_is_refused_before_the_log(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rig = Rig()
    assert rig.run([*PUBLISH[:5], "--as", "Not A Slug", "--by", "operator:a"]) == 1
    assert "a public id is lowercase letters" in capsys.readouterr().err
    tampered = Rig()

    def foreign(path: str) -> bytes:
        return b"{}"

    code = main(
        PUBLISH,
        ENV,
        store=lambda dsn: tampered.store,  # type: ignore[arg-type, return-value]
        log=lambda dsn: tampered.session,
        configuration=lambda: CONFIGURATION,
        registration=foreign,
    )
    assert code == 1
    assert "registration file's digest" in capsys.readouterr().err
    assert tampered.store.drafts == [] and not tampered.session.closed


def test_the_environment_without_the_registration_or_the_database_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rig = Rig()
    assert rig.run(PUBLISH, {"DATABASE_URL": DSN}) == 2
    assert "LEAVEIMPACT_REGISTRATION_FILE is not set" in capsys.readouterr().err
    assert rig.run(PUBLISH, {}) == 2
    assert "DATABASE_URL is not set" in capsys.readouterr().err
    assert rig.run(["publish", "--run", "run-12"], ENV) == 2
    assert rig.store.drafts == []
