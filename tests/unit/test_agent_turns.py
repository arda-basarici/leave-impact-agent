"""The investigator's turns through the real worker over the sealed throwaway world: the prompt
assets loaded from the package with the opening's two parameters; the first request as the
opening, the skill list and one block per prefetch operation, the ten read tools and the fact
tool under ``auto``; the loop request as the conversation rebuilt from the log with every
``toolUse`` answered, a read's envelope, a refused call's closed correction, an unparsed
call's fixed correction, a fact call's admissions by index and reason; the finalization
request after an answer with no read, the fact tool alone and forced, flagged ``final``;
nothing after the finalization call; the restatement equality at every prefix a recovery
can resume from; the payload as the shared composer's, equal to the baseline's claims when
the model read nothing and empty on an abstention; and the capture's fourth reading, no
scenario id and no world version in any request under either condition, on first execution
or rebuilt from the log, with what the model itself wrote going back as it arrived.

The smoke, at the unit level (the step's fork 16): the stating script through every node
to a closed attempt, the forced finalization call stating a requirement the guard admits,
the restatement equality from every prefix; the text-only finalization answer as its own
case; and a read contradicting the enumeration failing the run at that read on the first
process and on every recovery, the unit-level crash cut. The HR-outage smoke is the
abstention test above (the opening read unreachable, no count, no send)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from string import Template
from typing import Any, cast
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from leaveimpact.agent.admissions import admitted_statements
from leaveimpact.agent.answer_parse import FACT_TOOL
from leaveimpact.agent.assets import (
    ASSET_NAMES,
    FINALIZATION,
    OPENING,
    SYSTEM,
    PromptAssets,
    load_prompt_assets,
)
from leaveimpact.agent.composer import rules_only_composition
from leaveimpact.agent.log_events import (
    CountStarted,
    DispatchIntent,
    FinalizationEntered,
    FrozenInputs,
    LoggedEvent,
    kind_of,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import fold
from leaveimpact.agent.registered import NOVA_TOOL_USE_CUT
from leaveimpact.agent.rules_only import investigate
from leaveimpact.agent.surface import ARGUMENTS_CORRECTION, FACT_TOOL_DEFINITION
from leaveimpact.agent.turns import InvestigatorTurns
from leaveimpact.agent.worker import (
    AutomaticApproval,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core import Caps
from leaveimpact.core.jsonshape import JsonObject, canonical_json
from leaveimpact.core.model_calls import ServiceError
from leaveimpact.core.run_account import CallPurpose
from leaveimpact.core.run_ending import OperationSite
from leaveimpact.core.run_record import FailureCategory
from leaveimpact.core.run_trace import OperationId
from leaveimpact.core.skills import SKILLS
from leaveimpact.core.timeshape import encode_instant
from leaveimpact.core.tools import Role, role_surface, surface_correction
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.log_store_memory import MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world
from tests.unit.worker_support import ContentScriptedClient, ScriptedCounter

RULES = histories.RULES
RUN, ATTEMPT = "run-12", 1
PREFETCH = ("leave", "employees", "leaves_within", "components", "work_items", "events_within")
"""The opening read and the five planned calls in the plan's order, every source reachable."""
READ_TOOLS = tuple(s.name for s in role_surface(Role.INVESTIGATOR))


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def assets() -> PromptAssets:
    return load_prompt_assets()


@dataclass
class Bench:
    """One worker over a fresh in-memory log, the real turns and the content-scripted client."""

    log: MemoryLog
    inputs: FrozenInputs
    turns: InvestigatorTurns
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


def bench(
    world: SealedWorld,
    *,
    events: tuple[LoggedEvent, ...] | None = None,
    probe_tool: str = "probe_tool",
    outage: str | None = None,
    caps: Caps | None = None,
    script: support.RunScript[Any] | None = None,
) -> Bench:
    """The reference run of the real turns unless ``script`` names another, which then also
    says what the ports are (a contradicting source); ``outage`` makes one read unreachable."""
    context = world.context_of(world.scenarios[0])
    inputs = support.investigator_inputs(context)
    if caps is not None:
        inputs = replace(inputs, caps=caps)
    ports = systems_holding(world).ports
    if script is None:
        turns, client = support.investigator_script(world, context, probe_tool=probe_tool)
    else:
        # The bench's scripts are all the real turns over the content-scripted client; the
        # registry's type is the protocols', so a child can drive a scripted run by name.
        built, answering = script.over(world, context)
        turns, client = cast(InvestigatorTurns, built), cast(ContentScriptedClient, answering)
        ports = script.ports(ports)
    log = MemoryLog()
    log.seed(events if events is not None else support.admission(inputs))
    if outage is not None:
        ports = support.with_unreachable(ports, outage)
    return Bench(log, inputs, turns, client, ports)


# --- Readers of a body -----------------------------------------------------------------------


def messages_of(body: JsonObject) -> list[JsonObject]:
    return cast("list[JsonObject]", body["messages"])


def content_of(message: JsonObject) -> list[JsonObject]:
    return cast("list[JsonObject]", message["content"])


def text_of(block: JsonObject) -> str:
    return cast(str, block["text"])


def tool_names(body: JsonObject) -> list[str]:
    config = cast(JsonObject, body["toolConfig"])
    return [
        cast(str, cast(JsonObject, cast(JsonObject, tool)["toolSpec"])["name"])
        for tool in cast("list[object]", config["tools"])
    ]


def tool_choice(body: JsonObject) -> object:
    return cast(JsonObject, body["toolConfig"])["toolChoice"]


def result_json(block: JsonObject) -> JsonObject:
    result = cast(JsonObject, block["toolResult"])
    (content,) = cast("list[JsonObject]", result["content"])
    return cast(JsonObject, content["json"])


def prefetch_block(block: JsonObject) -> JsonObject:
    return cast(JsonObject, json.loads(text_of(block)))


def digests_per_call(events: tuple[LoggedEvent, ...]) -> dict[int, set[str]]:
    held: dict[int, set[str]] = {}
    for logged in events:
        if isinstance(logged.event, DispatchIntent):
            held.setdefault(logged.event.call, set()).add(logged.event.request_digest)
    return held


def intents_of(events: tuple[LoggedEvent, ...]) -> list[tuple[int, DispatchIntent]]:
    """Each intent with its index in ``events``."""
    return [(i, e.event) for i, e in enumerate(events) if isinstance(e.event, DispatchIntent)]


# --- The assets ------------------------------------------------------------------------------


def test_the_three_assets_load_from_the_package_with_their_digests(assets: PromptAssets) -> None:
    assert tuple(name for name, _ in assets.digests()) == tuple(sorted(ASSET_NAMES))
    assert all(len(digest) == 64 for _, digest in assets.digests())
    assert [role for role, _, _ in assets.prompt_digests("investigator")] == ["investigator"] * 3
    # The finalization names the fact tool; the system text stopped naming it at the prompt
    # check, whose removal round showed the sentence moving nothing (the tool list and the
    # forced last turn carry the name).
    assert FACT_TOOL in assets.text(FINALIZATION) and FACT_TOOL not in assets.text(SYSTEM)
    assert set(Template(assets.text(OPENING)).get_identifiers()) == {"leave_id", "now"}
    opening = assets.opening(leave_id="leave_005", now='{"at":"x","timezone":"y"}')
    assert "leave_005" in opening and '{"at":"x","timezone":"y"}' in opening
    assert "$" not in opening
    with pytest.raises(ValueError, match="no prompt asset named"):
        assets.text("closing")


# --- The three request shapes ----------------------------------------------------------------


def test_the_reference_run_makes_three_calls_and_closes_completed(world: SealedWorld) -> None:
    """Two loop calls and the finalization the system declares: the event sits below the
    third call's first event, its count, so the call is accounted as the finalization and
    the export's position shows the entry (fork 2)."""
    made = bench(world)
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    kinds = [kind_of(e.event).value for e in made.events()]
    assert kinds.count("dispatch_intent") == 3 and len(made.client.sends) == 3
    assert kinds.count("finalization_entered") == 1
    third_count = [i for i, kind in enumerate(kinds) if kind == "count_started"][2]
    assert kinds.index("finalization_entered") == third_count - 1
    state = made.state()
    assert state.account.purpose_of("call-3") is CallPurpose.FINALIZATION
    assert state.account.purpose_of("call-2") is CallPurpose.LOOP
    export = export_of(state)
    assert len(export.trace.model_calls) == 3 and export.trace.claims
    assert export.trace.finalization_entered == kinds.index("finalization_entered") + 1


TIGHT = Caps(20, 9_300, 2, 4_700, "input_plus_output_cached_included", cases.METHOD)
"""A token cap whose loop room (4,600) holds no worst case (4,608) and whose whole (9,300)
holds one: the first loop allocation enters finalization, and the finalization call fits."""


def test_a_finalization_the_account_entered_recounts_the_finalization_request_and_runs_whole(
    world: SealedWorld,
) -> None:
    """Amendment 5's one legitimate recount: the loop request is counted, the account refuses
    its allocation, the entry is appended, and the finalization request, other bytes, is
    counted anew above the entry; the loop's count stays below it. One send, the call the
    finalization, and a recovery from every prefix restates every request byte for byte."""
    reference = bench(world, caps=TIGHT)
    assert reference.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    whole = reference.events()
    kinds = [kind_of(e.event).value for e in whole]
    first = kinds.index("count_started")
    assert kinds[first : first + 6] == [
        "count_started",
        "count_outcome",
        "finalization_entered",
        "count_started",
        "count_outcome",
        "dispatch_intent",
    ]
    counted = [e.event.key.request_digest for e in whole if isinstance(e.event, CountStarted)]
    ((_, intent),) = intents_of(whole)
    assert len(counted) == 2 and counted[0] != counted[1] == intent.request_digest
    assert len(reference.client.sends) == 1
    assert tool_names(reference.client.bodies[0]) == [FACT_TOOL]
    assert reference.state().account.purpose_of("call-1") is CallPurpose.FINALIZATION
    for cut in range(2, len(whole)):
        recovering = bench(world, events=whole[:cut], caps=TIGHT)
        ending = recovering.work()
        assert ending.kind is WorkerEndingKind.CLOSED and ending.generation == 2, cut
        recovered = recovering.events()
        assert recovered[:cut] == whole[:cut]
        assert digests_per_call(recovered) == digests_per_call(whole), cut
        assert support.settled(recovered) == support.settled(whole), cut
        for body in recovering.client.bodies:
            assert canonical_json(body) == canonical_json(reference.client.bodies[0]), cut


def test_the_first_request_is_the_opening_the_skills_and_one_block_per_prefetch_read(
    world: SealedWorld, assets: PromptAssets
) -> None:
    made = bench(world)
    made.work()
    first = made.client.bodies[0]
    context = made.inputs.context
    (user,) = messages_of(first)
    blocks = content_of(user)
    assert user["role"] == "user" and len(blocks) == 2 + len(PREFETCH)
    stamp = canonical_json(encode_instant(context.now))
    assert text_of(blocks[0]) == assets.opening(leave_id=str(context.leave_id), now=stamp)
    skills = text_of(blocks[1])
    assert skills.startswith("Skill list (id: name):")
    assert all(f"- {skill.id}: {skill.name}" in skills for skill in SKILLS)
    rendered = [prefetch_block(block) for block in blocks[2:]]
    assert [block["tool"] for block in rendered] == list(PREFETCH)
    assert rendered[0]["arguments"] == {"id": str(context.leave_id)}
    opening_result = cast(JsonObject, rendered[0]["result"])
    assert opening_result["tool"] == "leave" and "record" in opening_result
    assert opening_result["observed_at"] == encode_instant(context.now)
    assert first["system"] == [{"text": assets.text(SYSTEM)}]
    assert tool_names(first) == [*READ_TOOLS, FACT_TOOL]
    assert tool_choice(first) == {"auto": {}}
    assert first["inferenceConfig"] == {"maxTokens": cases.OUTPUT_MAXIMUM, "temperature": 0}
    (_, intent), *_ = intents_of(made.events())
    assert len(intent.input_reads) == len(PREFETCH)


def test_the_loop_request_answers_every_tool_use_of_the_answer_as_arrived(
    world: SealedWorld,
) -> None:
    made = bench(world)
    made.work()
    second = made.client.bodies[1]
    context = made.inputs.context
    _, assistant, results = messages_of(second)
    assert assistant["role"] == "assistant"
    uses = [cast(JsonObject, b["toolUse"]) for b in content_of(assistant) if "toolUse" in b]
    assert [use["name"] for use in uses] == ["employee", "probe_tool", "leave", FACT_TOOL]
    assert results["role"] == "user"
    blocks = content_of(results)
    assert [cast(JsonObject, b["toolResult"])["toolUseId"] for b in blocks] == [
        "tu_emp",
        "tu_probe",
        "tu_bad",
        "tu_facts",
    ]
    read, probe, unparsed, facts = (result_json(b) for b in blocks)
    assert read["tool"] == "employee" and "record" in read
    assert probe["refused"] == {"correction": surface_correction(role_surface(Role.INVESTIGATOR))}
    assert "tool" not in probe, "a name the role does not declare is not written back"
    assert unparsed["refused"] == {"correction": ARGUMENTS_CORRECTION}
    assert unparsed["tool"] == "leave" and "not an object" not in canonical_json(unparsed)
    assert facts["tool"] == FACT_TOOL
    assert facts["entries"] == [
        {"index": 0, "refused": "missing_anchor"},
        {"index": 1, "refused": "undecodable"},
    ]
    assert facts["counts"] == {"missing_anchor": 1, "undecodable": 1}
    assert "kafka" not in canonical_json(facts) and "not an entry" not in canonical_json(facts)
    for each in (read, probe, unparsed, facts):
        assert each["observed_at"] == encode_instant(context.now)
    assert tool_names(second) == [*READ_TOOLS, FACT_TOOL] and tool_choice(second) == {"auto": {}}
    _, (_, intent), _ = intents_of(made.events())
    assert len(intent.input_reads) == len(PREFETCH) + 2, "the employee read and the refused call"


def test_the_finalization_request_follows_an_answer_with_no_read_and_forces_the_fact_tool(
    world: SealedWorld, assets: PromptAssets
) -> None:
    made = bench(world)
    made.work()
    third = made.client.bodies[2]
    messages = messages_of(third)
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant", "user"]
    assert content_of(messages[-1]) == [{"text": assets.text(FINALIZATION)}]
    assert tool_names(third) == [FACT_TOOL]
    assert tool_choice(third) == {"tool": {"name": FACT_TOOL}}
    state = made.state()
    request = made.turns.request_for(state, 3)
    assert request is not None and request.final
    assert canonical_json(request.body) == canonical_json(third)
    assert made.turns.request_for(state, 4) is None, "after the finalization call, nothing"
    first = made.turns.request_for(state, 1)
    assert first is not None and not first.final
    with pytest.raises(ValueError, match="neither in progress nor the next"):
        made.turns.request_for(state, 5)


def test_a_finalization_the_account_entered_is_asked_at_the_first_call(world: SealedWorld) -> None:
    """The first loop allocation does not fit: the finalization request is the opening, the
    prefetch and the finalization text in one user message, the fact tool alone and forced;
    below the event the same prefix gives the loop request."""
    made = bench(world)
    made.work()
    whole = made.events()
    cut = [kind_of(e.event).value for e in whole].index("count_started")
    below = whole[:cut]
    template = whole[cut]
    entered = LoggedEvent(cut + 1, template.timestamp, template.envelope, FinalizationEntered())
    request = made.turns.request_for(made.state((*below, entered)), 1)
    assert request is not None and request.final
    (user,) = messages_of(request.body)
    assert text_of(content_of(user)[-1]).startswith("This is the last turn.")
    assert tool_names(request.body) == [FACT_TOOL]
    loop = made.turns.request_for(made.state(below), 1)
    assert loop is not None and not loop.final and tool_choice(loop.body) == {"auto": {}}


NOVA_CUT = ServiceError(424, "ModelErrorException", 400, NOVA_TOOL_USE_CUT, 0, "req-cut")
"""The one evidenced behaviour-attributed service error: the fixtures' table reads it as the
model's own doing, so the call ends as behaviour with no answer."""


@dataclass
class SendOrderedClient(ContentScriptedClient):
    """The content-scripted client answering by send order instead: a call ended as behaviour
    contributes no assistant message, so the request after it carries the same count as the
    one before it and a script keyed by that count would answer the same twice."""

    def send(self, requested_profile: str, body: JsonObject) -> support.Sent:
        self.sends.append((requested_profile, support.request_digest(body)))
        self.bodies.append(body)
        return self.answers[len(self.sends) - 1]


def test_a_loop_call_ended_as_behaviour_is_followed_by_the_finalization(
    world: SealedWorld, assets: PromptAssets
) -> None:
    """The close's review, first finding: the first wiring had no reading for a call ended as
    behaviour, asked the turns for the next call and raised on the call with no answer,
    closing the run as a harness defect. The ended call is read as an answer with no read:
    the finalization follows, over a conversation the ended call contributes nothing to."""
    made = bench(world)
    carrier, author, quote = support.a_read_comment(world)
    entry = {"carrier": carrier, "predicate": "has_skill", "subject": author, "value": "kafka"}
    made.client = SendOrderedClient(
        (
            support.observed(NOVA_CUT),
            support.answered(
                support.fact_tool("tu_final", {**entry, "quote": quote}), stop_reason="tool_use"
            ),
        )
    )
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    assert len(made.client.sends) == 2
    state = made.state()
    second = made.client.bodies[1]
    (user,) = messages_of(second)
    assert text_of(content_of(user)[-1]) == assets.text(FINALIZATION)
    assert tool_names(second) == [FACT_TOOL]
    assert tool_choice(second) == {"tool": {"name": FACT_TOOL}}
    request = made.turns.request_for(state, 2)
    assert request is not None and request.final
    assert canonical_json(request.body) == canonical_json(second)
    assert made.turns.request_for(state, 3) is None, "after the finalization call, nothing"
    export = export_of(state)
    assert [call.answer is None for call in export.trace.model_calls] == [True, False]
    assert export.record.failure is None


def test_a_finalization_ended_as_behaviour_ends_the_run_with_the_payload_of_what_it_has(
    world: SealedWorld,
) -> None:
    """The same finding at the last turn: the finalization call ends as behaviour, the system
    asks nothing more, and the run completes through its approval with the baseline's
    payload, since nothing was admitted."""
    made = bench(world)
    made.client = ContentScriptedClient(
        (support.answered(support.text("Nothing further to read.")), support.observed(NOVA_CUT))
    )
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    assert len(made.client.sends) == 2
    state = made.state()
    assert made.turns.request_for(state, 3) is None
    assert admitted_statements(state) == ()
    baseline = investigate(made.inputs.context, systems_holding(world).ports)
    assert made.turns.payload_for(state).claims == baseline.claims
    assert export_of(state).trace.claims == baseline.claims


# --- The restatement equality ------------------------------------------------------------------


def test_a_recovery_from_every_prefix_restates_every_request_byte_for_byte(
    world: SealedWorld,
) -> None:
    reference = bench(world)
    reference.work()
    whole = reference.events()
    digests = digests_per_call(whole)
    assert len(digests) == 3 and all(len(held) == 1 for held in digests.values())
    for cut in range(2, len(whole)):
        recovering = bench(world, events=whole[:cut])
        ending = recovering.work()
        assert ending.kind is WorkerEndingKind.CLOSED and ending.generation == 2, cut
        recovered = recovering.events()
        assert recovered[:cut] == whole[:cut]
        assert digests_per_call(recovered) == digests, cut
        assert support.settled(recovered) == support.settled(whole), cut
        for body in recovering.client.bodies:
            turn = support.assistant_turns(body)
            assert canonical_json(body) == canonical_json(reference.client.bodies[turn]), cut


def test_a_request_in_progress_is_a_function_of_the_prefix_below_its_first_intent(
    world: SealedWorld,
) -> None:
    """At every prefix from the intent on, the call's request digests to the intent's."""
    made = bench(world)
    made.work()
    whole = made.events()
    for ordinal, (index, intent) in enumerate(intents_of(whole), start=1):
        assert intent.call == ordinal
        for cut in range(index + 1, len(whole) + 1):
            request = made.turns.request_for(made.state(whole[:cut]), ordinal)
            assert request is not None, (ordinal, cut)
            assert support.request_digest(request.body) == intent.request_digest, (ordinal, cut)


# --- The payload ---------------------------------------------------------------------------------


def test_the_payload_is_the_baselines_claims_when_the_model_read_nothing(
    world: SealedWorld,
) -> None:
    made = bench(world)
    made.work()
    whole = made.events()
    cut = [kind_of(e.event).value for e in whole].index("count_started")
    payload = made.turns.payload_for(made.state(whole[:cut]))
    baseline = investigate(made.inputs.context, systems_holding(world).ports)
    assert payload.claims == baseline.claims and payload.claims
    assert payload.composition == rules_only_composition()


def test_an_abstention_asks_no_call_and_goes_to_the_approval_with_the_empty_payload(
    world: SealedWorld,
) -> None:
    """The opening read unreachable: the leave is not returned, the run abstains, and the
    system asks nothing (fork 8): no count, no send, the approval requested with no claims,
    the run completed."""
    made = bench(world, outage="leave")
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    assert made.client.sends == [] and made.counter.asked == []
    kinds = [kind_of(e.event).value for e in made.events()]
    assert "dispatch_intent" not in kinds and "count_started" not in kinds
    assert kinds[-5:] == [
        "finalization_entered",
        "approval_requested",
        "approved",
        "resumed",
        "completed",
    ]
    state = made.state()
    assert made.turns.request_for(state, 1) is None
    assert made.turns.payload_for(state).claims == ()
    assert export_of(state).trace.claims == ()


# --- The capture's fourth reading -----------------------------------------------------------


@pytest.mark.parametrize("outage", [None, "leaves_within"])
def test_the_capture_finds_neither_the_scenario_id_nor_the_world_version_in_any_request(
    world: SealedWorld, outage: str | None
) -> None:
    made = bench(world, outage=outage)
    made.work()
    context = made.inputs.context
    secrets = (str(context.scenario_id), str(context.world_version))
    sent = [canonical_json(body) for body in made.client.bodies]
    assert len(sent) == 3
    whole = made.events()
    rebuilt: list[str] = []
    for index, intent in intents_of(whole):
        request = made.turns.request_for(made.state(whole[:index]), intent.call)
        assert request is not None
        rebuilt.append(canonical_json(request.body))
    assert rebuilt == sent, "rebuilt from the log, the bytes are the ones first sent"
    for text in sent:
        for secret in secrets:
            assert secret not in text
    if outage is not None:
        (user,) = messages_of(made.client.bodies[0])
        window = prefetch_block(content_of(user)[2 + PREFETCH.index("leaves_within")])
        assert cast(JsonObject, window["result"])["unreachable"] == {"source": "frappe"}


# --- The smoke -----------------------------------------------------------------------------------


def test_the_smoke_run_states_a_requirement_the_guard_admits_and_closes_completed(
    world: SealedWorld,
) -> None:
    """The stating script through every node: two loop calls and the forced finalization
    call, whose one entry is admitted; the claims are the baseline's, since the requirement
    scopes an artifact outside the leave's span; a recovery from every prefix restates every
    request byte for byte and admits the same statement."""
    stated = support.a_planted_requirement(world).stated
    stating = support.SCRIPTS["stating"]
    reference = bench(world, script=stating)
    assert reference.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    whole = reference.events()
    kinds = [kind_of(e.event).value for e in whole]
    assert kinds.count("dispatch_intent") == 3 and len(reference.client.sends) == 3
    assert kinds.count("finalization_entered") == 1 and kinds[-1] == "completed"
    third = reference.client.bodies[2]
    assert tool_names(third) == [FACT_TOOL] and tool_choice(third) == {"tool": {"name": FACT_TOOL}}
    state = reference.state()
    assert admitted_statements(state) == (stated,)
    assert reference.turns.request_for(state, 4) is None
    export = export_of(state)
    baseline = investigate(reference.inputs.context, systems_holding(world).ports)
    assert export.trace.claims == baseline.claims and export.trace.claims
    assert export.record.failure is None
    operations = [o.id for o in export.trace.operations]
    assert "call-1/tu_emp" in operations and "call-1/tu_doc" in operations
    for cut in range(2, len(whole)):
        recovering = bench(world, events=whole[:cut], script=stating)
        ending = recovering.work()
        assert ending.kind is WorkerEndingKind.CLOSED and ending.generation == 2, cut
        recovered = recovering.events()
        assert recovered[:cut] == whole[:cut]
        assert digests_per_call(recovered) == digests_per_call(whole), cut
        assert support.settled(recovered) == support.settled(whole), cut
        assert admitted_statements(recovering.state()) == (stated,), cut
        for body in recovering.client.bodies:
            turn = support.assistant_turns(body)
            assert canonical_json(body) == canonical_json(reference.client.bodies[turn]), cut


def test_a_text_only_finalization_answer_ends_the_loop_with_the_baselines_payload(
    world: SealedWorld,
) -> None:
    """The forced call answered by text alone: nothing is admitted, the turns ask nothing
    after it, the payload is the baseline's and the run completes."""
    text_only = replace(support.SCRIPTS["stating"], build=support.text_only_finalization)
    made = bench(world, script=text_only)
    assert made.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    assert len(made.client.sends) == 3
    state = made.state()
    assert admitted_statements(state) == ()
    assert made.turns.request_for(state, 4) is None
    baseline = investigate(made.inputs.context, systems_holding(world).ports)
    assert made.turns.payload_for(state).claims == baseline.claims
    assert export_of(state).trace.claims == baseline.claims


def test_a_read_contradicting_the_enumeration_fails_the_run_at_that_read_on_every_recovery(
    world: SealedWorld,
) -> None:
    """The HR system answers the employee the model asks for with another name than its
    enumeration gave: the transition's conclusion stops the attempt at that read, the read
    after it in the same answer is never made, the worker closes it failed by defect with no
    claim, and a recovery from every prefix closes it the same way."""
    contradicting = support.SCRIPTS["contradicting"]
    reference = bench(world, script=contradicting)
    assert reference.work() == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "failed")
    whole = reference.events()
    kinds = [kind_of(e.event).value for e in whole]
    assert kinds[-2:] == ["operation", "failed"] and len(reference.client.sends) == 1
    export = export_of(reference.state())
    failure = export.record.failure
    assert failure is not None and failure.category is FailureCategory.DEFECT
    assert failure.site == OperationSite(OperationId("call-1/tu_emp"))
    assert failure.reason.startswith("returns_differ: this read and prefetch/2 disagree")
    assert export.trace.claims == ()
    assert "call-1/tu_doc" not in [o.id for o in export.trace.operations]
    for cut in range(2, len(whole)):
        recovering = bench(world, events=whole[:cut], script=contradicting)
        ending = recovering.work()
        assert (ending.kind, ending.detail, ending.generation) == (
            WorkerEndingKind.CLOSED,
            "failed",
            2,
        ), cut
        recovered = recovering.events()
        assert recovered[:cut] == whole[:cut]
        assert support.settled(recovered) == support.settled(whole), cut
        assert export_of(recovering.state()).record.failure == failure, cut


def test_what_the_model_wrote_goes_back_as_it_arrived_and_the_harness_echoes_none_of_it(
    world: SealedWorld,
) -> None:
    """A model that names the scenario id in a tool call sees it again in its own message, as
    Converse requires, and in nothing the harness rendered."""
    made = bench(world, probe_tool="scenario_001")
    made.work()
    secret = str(made.inputs.context.scenario_id)
    second = made.client.bodies[1]
    _, assistant, results = messages_of(second)
    assert secret in canonical_json(assistant), "the assistant message as arrived"
    harness = {"system": second["system"], "results": results, "tools": second["toolConfig"]}
    assert secret not in canonical_json(harness)
    assert secret not in canonical_json(FACT_TOOL_DEFINITION)
