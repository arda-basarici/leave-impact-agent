"""The two one-call baselines' preparations through the worker: what each issues, from what,
and that a recovery issues the same (the baselines step, forks 7 and 8 as amended).

Every test runs the real preparation under the prepare node over in-memory ports holding
the golden world, the turns and the client scripted (the two-call script), so the claims are
about the one read and nothing about the request. The claims:

- the single-shot preparation issues one search under its policy, the registered literal
  as written with the registered limit, or a template rendered over the records the
  prefetch returned for the leaver: every rendered part is a component of the leaver's own
  work items, the text the registration's rendering gives;
- the full-context preparation issues one enumeration under its policy, every document the
  port holds, in the port's shown order;
- a recovery from any cut around the harness read renders the same query and makes the
  read at most once more: before the read's append it is made again and logged once, after
  it the held read is replayed and the port is not asked.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.agent.admissions import trace_operations
from leaveimpact.agent.graph import Preparation
from leaveimpact.agent.log_events import FrozenInputs, HarnessReadKey, LoggedEvent, OperationEvent
from leaveimpact.agent.preparations import FullContextPreparation, SingleShotPreparation
from leaveimpact.agent.worker import (
    AutomaticApproval,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core.entities import Document
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.query_protocol import QueryInput, TemplateQuery, render_query
from leaveimpact.core.run_record import System
from leaveimpact.core.run_trace import HarnessOrigin, Operation, RecordsOutcome, records_of
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.log_store_memory import MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world

RULES = histories.RULES
RUN, ATTEMPT = "run-12", 1


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


class CountingMethod:
    """A port whose one method counts its calls and passes every call through."""

    def __init__(self, inner: object, method: str) -> None:
        self._inner = inner
        self._method = method
        self.calls = 0

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name != self._method:
            return attribute

        def counted(*args: Any, **kwargs: Any) -> Any:
            self.calls += 1
            return attribute(*args, **kwargs)

        return counted


@dataclass
class Bench:
    """One worker over a fresh in-memory log, the two-call script and the real preparation,
    the corpus port's ``method`` counted."""

    log: MemoryLog
    inputs: FrozenInputs
    preparation: Preparation
    ports: Any
    corpus: CountingMethod
    turns: Any
    client: Any

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
            support.ScriptedCounter(),
            self.ports,
            AutomaticApproval(),
            InMemorySaver(),
            sleep=lambda seconds: None,
        )
        return worker.work(RUN, ATTEMPT, nonce=f"nonce-{uuid4().hex[:8]}")

    def events(self) -> tuple[LoggedEvent, ...]:
        return self.log.events(RUN, ATTEMPT)

    def harness_reads(self) -> list[Operation]:
        state = self.log.load(RUN, ATTEMPT, rules=RULES)
        return [op for op in trace_operations(state) if isinstance(op.origin, HarnessOrigin)]


SYSTEMS: dict[str, tuple[System, Preparation, str]] = {
    "single_shot": (histories.SINGLE_SHOT, SingleShotPreparation(), "search"),
    "full_context": (histories.FULL_CONTEXT, FullContextPreparation(), "documents"),
}


def bench(
    world: SealedWorld,
    system: str,
    *,
    inputs: FrozenInputs | None = None,
    events: tuple[LoggedEvent, ...] | None = None,
) -> Bench:
    admitted, preparation, method = SYSTEMS[system]
    context = world.context_of(world.scenarios[0])
    frozen = inputs if inputs is not None else support.admitted_inputs(context, system=admitted)
    turns, client = support.two_call_script(context)
    ports = systems_holding(world).ports
    corpus = CountingMethod(ports.documents, method)
    ports = replace(ports, documents=corpus)  # type: ignore[arg-type]
    log = MemoryLog()
    log.seed(events if events is not None else support.admission(frozen))
    return Bench(log, frozen, preparation, ports, corpus, turns, client)


def leaver_component_names(world: SealedWorld) -> set[str]:
    """The names of the components the leaver's own planted work items belong to, from the
    sealed world and never from a run's reads; every scenario's plantings, since the first
    scenario's leaver owns items another scenario planted."""
    scenario = world.scenarios[0]
    leave = next(p.entity for p in scenario.owned.leaves if p.entity.id == scenario.spec.leave_id)
    leaver = EmployeeId(leave.employee_id)
    items = (p.entity for held in world.scenarios for p in held.owned.work_items)
    owned = {item.component_id for item in items if item.owner_id == leaver}
    return {component.name for component in world.org.components if component.id in owned}


# --- What each issues --------------------------------------------------------------------------


def test_the_single_shot_preparation_searches_the_registered_literal_at_the_registered_limit(
    world: SealedWorld,
) -> None:
    made = bench(world, "single_shot")
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    (read,) = made.harness_reads()
    assert read.origin == HarnessOrigin("single_shot_query") and read.tool == "search"
    assert dict(read.arguments) == {
        "query": "handover or coverage",
        "limit": made.inputs.search_limit,
    }
    assert isinstance(read.outcome, RecordsOutcome) and made.corpus.calls == 1


def test_the_single_shot_preparation_renders_a_template_over_the_prefetchs_records(
    world: SealedWorld,
) -> None:
    """Fork 5's rendering at the harness: a template of the leaver's component names and one
    literal part renders over what the prefetch returned, so every rendered part is a
    component of the leaver's own work items or the literal, the join is the grammar's
    disjunction, and the text is what the pure rendering gives over the same records."""
    context = world.context_of(world.scenarios[0])
    protocol = TemplateQuery((QueryInput.COMPONENT_NAMES, "requires"), "handover")
    admitted = support.admitted_inputs(context, system=histories.SINGLE_SHOT)
    inputs = replace(admitted, query_protocol=protocol)
    made = bench(world, "single_shot", inputs=inputs)
    made.work()
    (read,) = made.harness_reads()
    query = read.arguments["query"]
    assert isinstance(query, str) and query != "handover"
    parts = query.split(" or ")
    assert parts[-1] == "requires" and len(parts) >= 2
    assert set(parts[:-1]) <= leaver_component_names(world)
    state = made.log.load(RUN, ATTEMPT, rules=RULES)
    assert read.position is not None
    prefetched = [
        op
        for op in trace_operations(state)
        if op.position is not None and op.position < read.position
    ]
    returned = tuple(r for op in prefetched for r in records_of(op.outcome))
    leave = next(r.value for r in returned if r.value.id == context.leave_id)
    assert query == render_query(protocol, returned, leave)  # type: ignore[arg-type]


def test_the_full_context_preparation_enumerates_every_document_the_port_holds(
    world: SealedWorld,
) -> None:
    made = bench(world, "full_context")
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    (read,) = made.harness_reads()
    assert read.origin == HarnessOrigin("full_context_documents") and read.tool == "documents"
    assert dict(read.arguments) == {}
    assert isinstance(read.outcome, RecordsOutcome)
    shown = [r.value.id for r in read.outcome.records]
    held = [r.value.id for r in made.ports.documents.documents()]
    assert shown == held and len(shown) > 1
    assert all(isinstance(r.value, Document) for r in read.outcome.records)
    assert made.corpus.calls == 2, "the run's read and this test's"


# --- Recovery ----------------------------------------------------------------------------------


@pytest.mark.parametrize("system", sorted(SYSTEMS))
@pytest.mark.parametrize("appended", [False, True])
def test_a_recovery_around_the_harness_read_issues_the_same_read_at_most_once_more(
    world: SealedWorld, system: str, appended: bool
) -> None:
    """Fork 1 for the real preparations: cut just before the harness read's append (the read
    is made once more and logged once) or just after it (the held read is replayed and the
    port is not asked); either way the recovered log holds the uninterrupted run's read, by
    key, arguments and resolution."""
    reference = bench(world, system)
    reference.work()
    whole = reference.events()
    read_position = next(
        e.position
        for e in whole
        if isinstance(e.event, OperationEvent) and isinstance(e.event.key, HarnessReadKey)
    )
    cut = read_position if appended else read_position - 1
    recovering = bench(world, system, events=whole[:cut])
    ending = recovering.work()
    assert ending.kind is WorkerEndingKind.CLOSED and ending.generation == 2
    assert recovering.corpus.calls == (0 if appended else 1)
    held = [
        (e.event.key, e.event.resolution)
        for e in recovering.events()
        if isinstance(e.event, OperationEvent)
    ]
    first = [
        (e.event.key, e.event.resolution) for e in whole if isinstance(e.event, OperationEvent)
    ]
    assert held == first
    assert [op.arguments for op in recovering.harness_reads()] == [
        op.arguments for op in reference.harness_reads()
    ]
