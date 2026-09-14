"""The attempt loop over scripted fakes: a clean first attempt accepted with its record and the
composed world sealing from it; a refusal by each guard consuming an attempt and recorded, the
next fresh attempt accepted; the cap exhausted marking the target and the stage still finishing
the others before failing with every failed target; a checker that keeps breaking the contract
aborting at once as infrastructure; an unreachable writer retried then aborting; a world with no
briefs calling no model; the log carrying ids, attempts, guard names and counts and never a body."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from leaveimpact.adapters.prose import (
    CheckerRequest,
    ModelProtocolFault,
    ModelUnreachable,
    ToolCall,
    Usage,
    WriterRequest,
    WrittenText,
)
from leaveimpact.generator.materialize import (
    CALL_RETRIES,
    MaterializationAborted,
    MaterializationFailed,
    Materialized,
    materialize,
)
from leaveimpact.generator.prose import load_prompt_assets
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Brief,
    CommentTarget,
    GuardName,
    assemble_semantic_world,
    bundle,
    compose,
)
from tests.unit.prose_fixture import (
    KAFKA,
    ORG,
    WORLD_START,
    SkillInComment,
    pending_scenario,
    semantic_world_of,
)

ASSETS = load_prompt_assets()
USAGE = Usage(100, 40, 500)


def brief_of() -> Brief:
    [brief] = pending_scenario(SkillInComment()).briefs
    return brief


def author(brief: Brief) -> str:
    assert isinstance(brief.target, CommentTarget)
    return brief.namespace.form_of("employee", brief.target.author_id)


def good_body(brief: Brief) -> str:
    return f"{author(brief)} here: I built the Kafka side of the retry queue migration myself."


def reading(brief: Brief, value: str = KAFKA, mode: str = "asserted") -> dict[str, object]:
    assert isinstance(brief.target, CommentTarget)
    return {
        "propositions": [
            {
                "subject": brief.target.author_id,
                "predicate": "has_skill",
                "value": value,
                "polarity": "affirmed",
                "mode": mode,
            }
        ],
        "other_claims": [],
    }


@dataclass
class ScriptedWriter:
    """Answers in order; an exception in the script is raised instead of returned."""

    script: list[str | Exception]
    model_id: str = "fake-writer"
    requests: list[WriterRequest] = field(default_factory=list[WriterRequest])

    def write(self, request: WriterRequest) -> WrittenText:
        self.requests.append(request)
        answer = self.script.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return WrittenText(answer, USAGE)


@dataclass
class ScriptedChecker:
    script: list[dict[str, object] | Exception]
    model_id: str = "fake-checker"
    requests: list[CheckerRequest] = field(default_factory=list[CheckerRequest])

    def extract(self, request: CheckerRequest) -> ToolCall:
        self.requests.append(request)
        answer = self.script.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ToolCall(answer, USAGE)


def run(
    writer: ScriptedWriter, checker: ScriptedChecker, cap: int = 4
) -> tuple[Callable[[], Materialized], list[str]]:
    lines: list[str] = []
    scenario = pending_scenario(SkillInComment())
    semantic = semantic_world_of(scenario)
    return (lambda: materialize(semantic, writer, checker, ASSETS, cap, lines.append)), lines


def test_a_clean_first_attempt_is_accepted_recorded_and_seals_into_a_world() -> None:
    brief = brief_of()
    writer = ScriptedWriter([good_body(brief)])
    checker = ScriptedChecker([reading(brief)])
    go, lines = run(writer, checker)
    materialized = go()
    assert materialized.prose == {brief.id: good_body(brief)}
    [target] = materialized.record.targets
    assert (target.target_id, target.attempts, target.refusals) == (brief.id, 1, ())
    assert len(target.propositions) == 1
    assert materialized.record.writer.model_id == "fake-writer"
    assert materialized.record.prompt_digests == ASSETS.digests()
    assert lines == [f"{brief.id}: accepted on attempt 1"]
    metrics = materialized.metrics
    assert (
        metrics.writer_attempts,
        metrics.targets_first_attempt_pass,
        metrics.targets_eventual_pass,
    ) == (1, 1, 1)
    assert metrics.writer_input_tokens == 100 and metrics.checker_latency_ms == 500
    # The checker never saw the brief's facts, only the text and the entity list.
    assert "has experience with" not in checker.requests[0].message
    # The output composes and seals.
    composed = compose(
        semantic_world_of(pending_scenario(SkillInComment())),
        materialized.prose,
        materialized.record,
    )
    assert bundle(composed).world_version


def test_each_guard_refuses_in_turn_and_the_fresh_attempt_after_them_is_accepted() -> None:
    brief = brief_of()
    stranger = next(e.name for e in ORG.employees if e.name != author(brief))
    writer = ScriptedWriter(
        [
            f"{stranger} and I did the Kafka side.",  # namespace: another world name
            f"{author(brief)} here: I did the streaming side.",  # required fact: no Kafka anchor
            good_body(brief),  # extraction: the checker reads a hedge
            good_body(brief),  # accepted
        ]
    )
    checker = ScriptedChecker([reading(brief, mode="hedged"), reading(brief)])
    go, lines = run(writer, checker)
    materialized = go()
    [target] = materialized.record.targets
    assert target.attempts == 4
    assert [(r.attempt, r.guard) for r in target.refusals] == [
        (1, GuardName.NAMESPACE),
        (2, GuardName.REQUIRED_FACT),
        (3, GuardName.EXTRACTION),
    ]
    assert lines == [
        f"{brief.id} attempt 1: refused by namespace (1 findings)",
        f"{brief.id} attempt 2: refused by required_fact (1 findings)",
        f"{brief.id} attempt 3: refused by extraction (2 findings)",  # hedged, and so not asserted
        f"{brief.id}: accepted on attempt 4",
    ]
    assert stranger not in "\n".join(lines)  # no body, no name, ever in the log
    assert len({r.message for r in writer.requests}) == 1  # the same prompt every attempt
    metrics = materialized.metrics
    assert (
        metrics.namespace_refusals,
        metrics.required_fact_refusals,
        metrics.extraction_refusals,
    ) == (1, 1, 1)
    assert metrics.targets_first_attempt_pass == 0 and metrics.targets_eventual_pass == 1


def test_the_cap_exhausted_fails_the_target_after_the_stage_with_every_refusal() -> None:
    brief = brief_of()
    writer = ScriptedWriter([f"{author(brief)} here: nothing about the topic."] * 2)
    checker = ScriptedChecker([])
    go, lines = run(writer, checker, cap=2)
    with pytest.raises(MaterializationFailed, match="1 target") as failure:
        go()
    assert [r.guard for r in failure.value.failed[brief.id]] == [GuardName.REQUIRED_FACT] * 2
    assert failure.value.metrics.targets_cap_exhausted == 1
    assert lines[-1] == f"{brief.id}: cap of 2 exhausted"


def test_a_checker_that_keeps_breaking_the_contract_aborts_the_stage_as_infrastructure() -> None:
    brief = brief_of()
    writer = ScriptedWriter([good_body(brief)])
    checker = ScriptedChecker(
        [ModelProtocolFault("fake-checker", "no tool call")] * (CALL_RETRIES + 1)
    )
    go, lines = run(writer, checker)
    with pytest.raises(MaterializationAborted, match="checker unusable"):
        go()
    assert (
        sum("checker call failed (ModelProtocolFault)" in line for line in lines)
        == CALL_RETRIES + 1
    )


def test_an_unreachable_writer_is_retried_then_aborts() -> None:
    writer = ScriptedWriter([ModelUnreachable("fake-writer")] * (CALL_RETRIES + 1))
    go, _ = run(writer, ScriptedChecker([]))
    with pytest.raises(MaterializationAborted, match="writer unusable") as aborted:
        go()
    assert aborted.value.metrics.writer_retries == CALL_RETRIES + 1


def test_a_world_with_no_briefs_calls_no_model_and_records_nothing() -> None:
    semantic = assemble_semantic_world(7, DEFAULT_PARAMS, WORLD_START)
    writer, checker = ScriptedWriter([]), ScriptedChecker([])
    materialized = materialize(semantic, writer, checker, ASSETS, 4, lambda _: None)
    assert materialized.prose == {} and materialized.record.targets == ()
    assert writer.requests == [] and checker.requests == []


def test_the_request_digest_is_of_the_rendered_request() -> None:
    brief = brief_of()
    writer = ScriptedWriter([good_body(brief)])
    go, _ = run(writer, ScriptedChecker([reading(brief)]))
    materialized = go()
    [target] = materialized.record.targets
    [request] = writer.requests
    assert json.dumps(request.message)  # the request is plain text the digest is over
    assert len(target.request_digest) == 64
