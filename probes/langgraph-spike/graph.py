"""The spike's minimal graph: the prefetch, a model and tool loop, the approval interrupt and
the terminal state, each node appending to the event log before it returns.

The order of writes is the one the acceptance spike's ruling 3 fixes. Tool node: look up the
result, execute, append, return, then the framework writes its checkpoint. Model node: look
up the outcome, append an intent, invoke, append the outcome, return. The prefetch is one
node making the tool sequence once per planned read.

Approval: the node holds only the interrupt, and the interrupt names what is to be approved,
the model call whose claims the run ends with and the digest of that call's logged outcome.
Whoever delivers the approval reads that from the paused graph, appends an approval event
that carries it, and then resumes. ``deliver_approval`` refuses to append unless the graph
is paused at the approval, so an approval cannot enter the log before the claims it approves
exist, and the node refuses a resume whose approval event does not name the outcome the log
holds. The event's identifier is deterministic and so guessable; what binds an approval to
a run's claims is its content, never its identifier. The handoff has three seams: before the
approval event's commit (the append's own), after the commit and before the resume is
delivered, and inside the node once the resume has arrived.

Checkpointed state is the cursor and nothing a result could be rebuilt from: the number of
completed model turns, where the loop goes next, and for every result a node reached its
position and the digest of its logged event. The digests are what the crash check compares
with the log; the results themselves are read from the log at every node entry. No message
and no record crosses the saver's serializer.

The configuration a pass accepts is set here: the synchronous saver on its own autocommit
connection built the way ``from_conn_string`` builds one, ``durability="sync"`` on every
invocation, and no retry policy. The framework applies a graph-wide default to the nodes
only when the graph is compiled, so the policies are read off the compiled graph, where a
node's and the graph's own both live, and anything but none refuses the build.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

import psycopg
from eventlog import (
    APPLICATION,
    APPROVAL,
    MODEL_INTENT,
    MODEL_OUTCOME,
    RUN_TERMINAL,
    EventLog,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row
from replay import (
    PREFETCH_PREFIX,
    SYSTEM,
    LoggedExecutor,
    call_position,
    conversation,
    outcome_content,
    phases_before,
    request_digest,
    tool_prefix,
)
from seams import cross

from leaveimpact.agent.execution import ReadPorts, run_prefetch
from leaveimpact.core.run_trace import ModelCallId, ModelCallOutcome, ModelOrigin
from leaveimpact.core.worldtime import RunContext

DURABILITY = "sync"
TURN_CEILING = 8
"""A loop bug stops here; the script is three turns."""


def _merged(held: dict[str, str], reached: dict[str, str]) -> dict[str, str]:
    return {**held, **reached}


class State(TypedDict):
    """The cursor: completed model turns, the loop's next node, and the digest of each logged
    result a node reached, by position."""

    turn: int
    route: str
    results: Annotated[dict[str, str], _merged]


INITIAL: State = {"turn": 0, "route": "", "results": {}}


@dataclass(frozen=True)
class Harness:
    """What the nodes work with: the log, the ports, the model, the run's context, how the
    usage the provider reported for an answer is read (the scripted model's own report here,
    the capture recorder's raw response on the live path), and the system prompt."""

    log: EventLog
    ports: ReadPorts
    model: BaseChatModel
    context: RunContext
    usage_of: Callable[[AIMessage], dict[str, int] | None]
    system: str = SYSTEM


def saver_on(
    url: str,
    schema: str,
    saver_class: type[PostgresSaver] = PostgresSaver,
    application: str = APPLICATION,
) -> PostgresSaver:
    """The synchronous saver, or the subclass ``saver_class`` of it, on a connection of its
    own named ``application``, its tables created in ``schema``."""
    connection = psycopg.Connection[DictRow].connect(
        make_conninfo(url, options=f"-c search_path={schema}", application_name=application),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    saver = saver_class(connection)
    saver.setup()
    return saver


def build(harness: Harness, saver: PostgresSaver) -> Any:
    """The compiled graph over ``harness``, checkpointed by ``saver``."""
    log = harness.log

    def prefetch(state: State) -> dict[str, Any]:
        executor = LoggedExecutor(harness.ports, log=log, prefix=PREFETCH_PREFIX, earlier=())
        if run_prefetch(executor, harness.context).leave is None:
            raise RuntimeError("the spike's scenario returns its leave; this one did not")
        return {"results": executor.digests}

    def model(state: State) -> dict[str, Any]:
        turn = state["turn"] + 1
        if turn > TURN_CEILING:
            raise RuntimeError(f"the loop reached turn {turn}, past its ceiling")
        call = call_position(turn)
        held = log.find(MODEL_OUTCOME, call)
        if held is None:
            messages = conversation(harness.context, log.events(), state["turn"], harness.system)
            digest = request_digest(messages)
            dispatch = 1 + sum(e.data["call"] == call for e in log.events(MODEL_INTENT))
            log.append(
                MODEL_INTENT,
                f"{call}/{dispatch}",
                {"call": call, "dispatch_attempt": dispatch, "request_digest": digest},
            )
            answer = harness.model.invoke(messages)
            if not isinstance(answer, AIMessage):
                raise RuntimeError(f"the model answered with {type(answer).__name__}")
            content = outcome_content(call, dispatch, digest, answer, harness.usage_of(answer))
            held = log.append(MODEL_OUTCOME, call, content)
        outcome = ModelCallOutcome(held.data["outcome"])
        # Any answered response that asks for no read ends the loop: claims, and equally a
        # text, a refusal or an output the claims codec rejects, each a completed run that
        # states no claim (the export format's reading of them).
        route = "tools" if outcome is ModelCallOutcome.TOOL_CALLS else "approval"
        return {"turn": turn, "route": route, "results": {call: held.digest}}

    def tools(state: State) -> dict[str, Any]:
        turn = state["turn"]
        call = call_position(turn)
        answered = log.find(MODEL_OUTCOME, call)
        if answered is None:
            raise RuntimeError(f"graph state is at {call}, the log holds no outcome for it")
        executor = LoggedExecutor(
            harness.ports, log=log, prefix=tool_prefix(turn), earlier=phases_before(turn)
        )
        for asked in answered.data["tool_calls"]:
            executor.call(ModelOrigin(ModelCallId(call)), asked["tool"], asked["arguments"])
        return {"results": executor.digests}

    def approval(state: State) -> dict[str, Any]:
        call = call_position(state["turn"])
        delivered = interrupt({"approves": call, "outcome_digest": state["results"][call]})
        cross("approval", "node:resumed")
        held = log.find(APPROVAL, "1")
        claims = log.find(MODEL_OUTCOME, call)
        if held is None or claims is None or held.event_id != delivered:
            raise RuntimeError(
                f"resumed with {delivered!r}, which is not an approval the log holds"
            )
        if (held.data["approves"], held.data["outcome_digest"]) != (call, claims.digest):
            raise RuntimeError(
                f"the logged approval is of {held.data['approves']} at "
                f"{held.data['outcome_digest']}, the run's claims are {call} at {claims.digest}"
            )
        return {"results": {APPROVAL: held.digest}}

    def terminal(state: State) -> dict[str, Any]:
        held = log.find(RUN_TERMINAL, "1") or log.append(RUN_TERMINAL, "1", {"status": "completed"})
        return {"results": {RUN_TERMINAL: held.digest}}

    builder = StateGraph(State)
    for node in (prefetch, model, tools, approval, terminal):
        builder.add_node(node.__name__, node)
    builder.add_edge(START, "prefetch")
    builder.add_edge("prefetch", "model")
    builder.add_conditional_edges(
        "model", lambda state: state["route"], {"tools": "tools", "approval": "approval"}
    )
    builder.add_edge("tools", "model")
    builder.add_edge("approval", "terminal")
    builder.add_edge("terminal", END)
    graph = builder.compile(checkpointer=saver)
    policies = retry_policies(graph)
    if any(policies.values()):
        raise RuntimeError(
            f"the spike runs with no retry policy; the compiled graph holds {policies}"
        )
    return graph


def retry_policies(graph: Any) -> dict[str, list[str]]:
    """The retry policies the compiled ``graph`` holds, its own under ``graph`` and each node's
    under the node's name, as their representations; every list is empty when none is set."""
    held = {"graph": [repr(policy) for policy in graph.retry_policy or ()]}
    for name, node in graph.nodes.items():
        held[name] = [repr(policy) for policy in node.retry_policy or ()]
    return held


def run_to_interrupt(graph: Any, thread: str) -> dict[str, Any]:
    """Run the graph from its start until it stops, which a healthy run does at the approval."""
    return graph.invoke(INITIAL, _config(thread), durability=DURABILITY)


def deliver_approval(graph: Any, log: EventLog, thread: str) -> dict[str, Any]:
    """Append the approval of what the paused graph asks to have approved, then resume it.

    Raises ``RuntimeError``, with nothing appended, unless the graph is paused at the
    approval with exactly one interrupt.
    """
    paused = graph.get_state(_config(thread))
    if paused.next != ("approval",) or len(paused.interrupts) != 1:
        raise RuntimeError(
            f"an approval is delivered to a graph paused at the approval; this one is at "
            f"{paused.next} with {len(paused.interrupts)} interrupts"
        )
    asked = paused.interrupts[0].value
    held = log.append(APPROVAL, "1", {"decision": "approved", **asked})
    return resume_with(graph, held.event_id, thread)


def resume_with(graph: Any, approval_event: str, thread: str) -> dict[str, Any]:
    """Resume the paused graph with an approval event the log already holds."""
    cross("approval", "delivery:before")
    return graph.invoke(Command(resume=approval_event), _config(thread), durability=DURABILITY)


def _config(thread: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread}}
