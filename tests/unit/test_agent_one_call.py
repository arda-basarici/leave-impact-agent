"""The one-call baselines' turns through the worker: the one request's shape over the prefetch
and the harness's reads, its finalization purpose, what follows it and what an abstention
or an unanswered corpus does to it (the baselines step, forks 2, 7 and 9).

Every test runs the real turns over the skeleton against in-memory ports holding the golden
world, with the preparation scripted to issue the system's one read and the client answering
the forced fact call with one truthful fact. The claims:

- the request is one user message, the investigator's opening, skill list and prefetch
  blocks, then the one harness operation's block, then the finalization text; the tools are
  the harness's alone with the fact tool forced; ``input_reads`` names the prefetch and the
  harness operations; the finalization is entered before the intent and the call is the
  finalization (fork 2 as amended, fork 9);
- the request restated for the call in progress is the same bytes, and nothing is asked
  after the call's outcome;
- the fact the model states on a document the harness read is admitted and composed, so a
  one-call run ends with claims through the shared composer;
- an abstention asks no call: no count, no send, the empty payload (fork 7);
- a harness read the corpus did not answer is shown as the error envelope and the call is
  still made (fork 7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.agent.admissions import admitted_statements
from leaveimpact.agent.answer_parse import FACT_TOOL
from leaveimpact.agent.assets import FINALIZATION, PromptAssets, load_prompt_assets
from leaveimpact.agent.log_events import (
    DispatchIntent,
    FinalizationEntered,
    FrozenInputs,
    LoggedEvent,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import call_purpose, fold
from leaveimpact.agent.one_call import OneCallTurns
from leaveimpact.agent.worker import (
    AutomaticApproval,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.run_account import CallPurpose
from leaveimpact.core.run_record import System
from leaveimpact.core.tools import Role
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.log_store_memory import MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world
from tests.unit.worker_support import ContentScriptedClient, ScriptedCounter, ScriptedPreparation

RULES = histories.RULES
RUN, ATTEMPT = "run-12", 1

type HarnessRead = tuple[str, tuple[str, dict[str, object]]]
"""A policy and the one read issued under it: the tool and its arguments."""

SEARCH: HarnessRead = (
    "single_shot_query",
    ("search", {"query": "handover or coverage", "limit": 10}),
)
DOCUMENTS: HarnessRead = ("full_context_documents", ("documents", {}))
SYSTEMS: dict[str, tuple[System, HarnessRead]] = {
    "single_shot": (histories.SINGLE_SHOT, SEARCH),
    "full_context": (histories.FULL_CONTEXT, DOCUMENTS),
}


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def assets() -> PromptAssets:
    return load_prompt_assets(Role.READER)


@dataclass
class Bench:
    """One worker over a fresh in-memory log, the one-call turns, a scripted preparation and
    the content-scripted client answering the forced call with one fact."""

    log: MemoryLog
    inputs: FrozenInputs
    turns: OneCallTurns
    preparation: ScriptedPreparation
    client: ContentScriptedClient
    ports: Any
    counter: ScriptedCounter = field(default_factory=ScriptedCounter)

    def work(self) -> WorkerEnding:
        worker = Worker(
            self.log,
            WorkerConfiguration.of(self.inputs),
            cases.REVISION,
            "launch-1",
            RULES,
            self.turns,
            self.preparation,
            self.client,
            self.counter,
            self.ports,
            AutomaticApproval(),
            InMemorySaver(),
            sleep=lambda seconds: None,
        )
        return worker.work(RUN, ATTEMPT, nonce=f"nonce-{uuid4().hex[:8]}")

    def events(self) -> tuple[LoggedEvent, ...]:
        return self.log.events(RUN, ATTEMPT)

    def state(self, events: tuple[LoggedEvent, ...] | None = None) -> Any:
        return fold(self.events() if events is None else events, RULES)


def bench(world: SealedWorld, system: str, *, outage: str | None = None) -> Bench:
    """The ``system``'s run over the golden world's first scenario, the people system's
    ``outage`` method unreachable when given."""
    admitted, (policy, read) = SYSTEMS[system]
    context = world.context_of(world.scenarios[0])
    inputs = support.reader_inputs(context, admitted)
    planted = support.a_planted_requirement(world)
    client = ContentScriptedClient(
        (
            support.answered(
                support.fact_tool("tu_final", histories.entry_of(planted.stated)),
                stop_reason="tool_use",
            ),
        )
    )
    ports = systems_holding(world).ports
    if outage is not None:
        ports = support.with_unreachable(ports, outage)
    log = MemoryLog()
    log.seed(support.admission(inputs))
    turns = OneCallTurns(load_prompt_assets(Role.READER))
    return Bench(log, inputs, turns, ScriptedPreparation(policy, (read,)), client, ports)


# --- Readers of a body -----------------------------------------------------------------------


def messages_of(body: JsonObject) -> list[JsonObject]:
    return cast("list[JsonObject]", body["messages"])


def texts_of(message: JsonObject) -> list[str]:
    return [cast(str, block["text"]) for block in cast("list[JsonObject]", message["content"])]


def tool_names(body: JsonObject) -> list[str]:
    config = cast(JsonObject, body["toolConfig"])
    return [
        cast(str, cast(JsonObject, cast(JsonObject, tool)["toolSpec"])["name"])
        for tool in cast("list[object]", config["tools"])
    ]


def the_intent(events: tuple[LoggedEvent, ...]) -> LoggedEvent:
    (logged,) = [e for e in events if isinstance(e.event, DispatchIntent)]
    return logged


# --- The one request ---------------------------------------------------------------------------


@pytest.mark.parametrize("system", sorted(SYSTEMS))
def test_the_one_request_shows_the_prefetch_then_the_harness_read_then_the_ask(
    world: SealedWorld, assets: PromptAssets, system: str
) -> None:
    """Forks 2 and 9: one user message, the investigator's form, then the harness
    operation's block in the same form, then the finalization text last; the fact tool alone
    and forced; ``input_reads`` the prefetch's operations then the harness's."""
    made = bench(world, system)
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    (body,) = made.client.bodies
    (message,) = messages_of(body)
    assert message["role"] == "user"
    texts = texts_of(message)
    policy, (tool, _) = SYSTEMS[system][1]
    prefetched = [t for t in texts[2:-2] if t.startswith("{")]
    assert len(prefetched) == len(texts) - 4 and len(prefetched) >= 1
    assert all(f'"tool":"{tool}"' not in t for t in prefetched)
    harness_block = texts[-2]
    assert f'"tool":"{tool}"' in harness_block and '"records":[' in harness_block
    assert texts[-1] == assets.text(FINALIZATION)
    assert texts[0].startswith("The leave under investigation")
    assert texts[1].startswith("Skill list")
    assert tool_names(body) == [FACT_TOOL]
    assert cast(JsonObject, body["toolConfig"])["toolChoice"] == {"tool": {"name": FACT_TOOL}}
    intent = the_intent(made.events()).event
    assert isinstance(intent, DispatchIntent) and intent.role == "reader"
    prefetch_ids = [f"prefetch/{n}" for n in range(1, len(prefetched) + 1)]
    assert list(intent.input_reads) == [*prefetch_ids, f"{policy}/1"]


@pytest.mark.parametrize("system", sorted(SYSTEMS))
def test_the_call_is_the_finalization_and_nothing_is_asked_after_it(
    world: SealedWorld, system: str
) -> None:
    """Fork 2: the finalization is entered before the intent and the call is accounted as the
    finalization; one count, one send; call 2 answers ``None``; the request restated for the
    call in progress is the sent bytes."""
    made = bench(world, system)
    made.work()
    events = made.events()
    intent = the_intent(events)
    entered = [e for e in events if isinstance(e.event, FinalizationEntered)]
    assert len(entered) == 1 and entered[0].position < intent.position
    state = made.state()
    assert call_purpose(state, 1) is CallPurpose.FINALIZATION
    assert len(made.client.bodies) == 1 and len(made.counter.asked) == 1
    assert made.turns.request_for(state, 2) is None
    restated = made.turns.request_for(made.state(events[: intent.position - 1]), 1)
    assert restated is not None and restated.body == made.client.bodies[0] and restated.final
    with pytest.raises(ValueError, match="neither in progress nor the next"):
        made.turns.request_for(state, 3)


def test_a_fact_stated_on_a_document_the_harness_read_is_admitted_and_composed(
    world: SealedWorld,
) -> None:
    """The harness's enumeration shows every document, so the planted requirement the model
    states truthfully in the forced call is admitted against the harness read and the run
    ends with claims through the shared composer; the export round-trips the one call."""
    made = bench(world, "full_context")
    made.work()
    state = made.state()
    planted = support.a_planted_requirement(world)
    assert admitted_statements(state) == (planted.stated,)
    export = export_of(state)
    assert len(export.trace.model_calls) == 1
    assert export.trace.claims == made.turns.payload_for(state).claims
    assert export.trace.claims != ()


def test_an_abstention_asks_no_call(world: SealedWorld) -> None:
    """Fork 7: the opening read unreachable, the leave not returned: the preparation is not
    asked, the turns ask nothing, no count and no send; the approval with the empty payload."""
    made = bench(world, "single_shot", outage="leave")
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    assert made.client.bodies == [] and made.counter.asked == []
    assert made.preparation.outcomes == []
    state = made.state()
    assert made.turns.request_for(state, 1) is None
    assert made.turns.payload_for(state).claims == ()


def test_an_unanswered_harness_read_is_shown_as_its_error_and_the_call_is_still_made(
    world: SealedWorld,
) -> None:
    """Fork 7: the corpus unreachable at the harness read: the block shows the unreachable
    source as the surface renders it, the operation is named among the input reads, and the
    one call is made."""
    made = bench(world, "single_shot")
    made.ports = support.with_corpus_unreachable(made.ports, "search")
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    (body,) = made.client.bodies
    (message,) = messages_of(body)
    harness_block = texts_of(message)[-2]
    assert '"tool":"search"' in harness_block
    assert '"unreachable":{"source":"corpus"}' in harness_block
    intent = the_intent(made.events()).event
    assert isinstance(intent, DispatchIntent)
    assert intent.input_reads[-1] == "single_shot_query/1"
