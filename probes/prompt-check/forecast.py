"""The prompt check's forecast, computed model-free before any live call (the step's fork 15
with amendment 6): what the six live-iteration runs will be asked, what their answers
need, and how much input each call carries, from the sealed world and the real turns alone.

Per scenario it renders the first request and the no-read finalization request exactly as
the live run will send them, by driving the real worker over an in-memory log with a client
that answers "nothing further" to every turn (so no read is made and the finalization is
the first request plus one exchange); the byte lengths bound the input tokens by the
input-bound probe's measured ratio (2.5 to 6 bytes a token). It derives the oracle's answer
under the normal condition and the retrieval targets that move it, splits them by the kind
of text that carries them (a comment the prefetch returns inside its ticket, a section the
model has to read through a document tool) and sums the bytes of the documents a run has to
read to see every section target; and it names whether a scenario's targets include a clause
asking for more than one person, the chain check's case.

Written beside this file: ``forecast.json`` (the numbers) and ``forecast.md`` (the table).
Both carry scenario ids and sizes alone: a scenario's tier and class are sealed and this
repository is public, so they are printed to the console and never written.

    PYTHONPATH=. uv run python probes/prompt-check/forecast.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

sys.path.insert(0, str(Path(__file__).resolve().parent))

import development_world as dw  # noqa: E402

from leaveimpact.agent.assets import load_prompt_assets  # noqa: E402
from leaveimpact.agent.turns import InvestigatorTurns  # noqa: E402
from leaveimpact.agent.worker import AutomaticApproval, Worker, WorkerConfiguration  # noqa: E402
from leaveimpact.core.entities import Document  # noqa: E402
from leaveimpact.core.enums import EntityKind  # noqa: E402
from leaveimpact.core.facts import RunCondition  # noqa: E402
from leaveimpact.core.jsonshape import canonical_bytes  # noqa: E402
from leaveimpact.core.run_timing import TreeState  # noqa: E402
from leaveimpact.core.values import Requirement  # noqa: E402
from leaveimpact.evaluator.oracle import Answerable, oracle_for  # noqa: E402
from leaveimpact.evaluator.retrieval_targets import RetrievalTarget, retrieval_targets  # noqa: E402
from leaveimpact.evaluator.sealed_world import SealedWorld  # noqa: E402
from leaveimpact.world.scenario import Scenario  # noqa: E402
from tests.unit import worker_support as support  # noqa: E402
from tests.unit.log_store_memory import MemoryLog  # noqa: E402
from tests.unit.reads_fixture import systems_holding  # noqa: E402

HERE = Path(__file__).resolve().parent
BYTES_PER_TOKEN = (2.5, 6.0)
"""The input-bound probe's measured ratio of a request's bytes to its input tokens."""


@dataclass(frozen=True)
class ScenarioForecast:
    scenario_id: str
    abstains: bool
    first_request_bytes: int
    finalization_request_bytes: int
    targets: int
    targets_required: int
    targets_by_predicate: dict[str, int]
    targets_on_comments: int
    targets_on_sections: int
    documents_with_targets: int
    document_bytes_with_targets: int
    two_person_clause: bool

    def tokens(self, size: int) -> tuple[int, int]:
        low, high = BYTES_PER_TOKEN
        return int(size / high), int(size / low)


def render_requests(
    world: SealedWorld, scenario: Scenario, configuration: dw.ProbeConfiguration
) -> tuple[bytes, bytes]:
    """The first request and the finalization request of a run that reads nothing, as
    canonical bytes: the real worker and turns under the probe's configuration, the client
    answering a text with no tool use to the loop call and to the finalization call."""
    inputs = configuration.frozen_inputs(world.context_of(scenario))
    answer = support.answered(support.text("Nothing further to read."))
    client = support.ContentScriptedClient((answer, answer))
    log = MemoryLog()
    log.seed(support.admission(inputs))
    worker = Worker(
        log,
        WorkerConfiguration.of(inputs),
        configuration.harness,
        "launch-forecast",
        configuration.rules,
        InvestigatorTurns(load_prompt_assets()),
        client,
        support.ScriptedCounter(),
        systems_holding(world).ports,
        AutomaticApproval(),
        InMemorySaver(),
        sleep=lambda seconds: None,
    )
    ending = worker.work(inputs.run_id, inputs.attempt, nonce="nonce-forecast")
    if ending.detail != "completed":
        raise AssertionError(f"the no-read run did not complete: {ending}")
    if len(client.bodies) != 2:
        raise AssertionError(f"a no-read run sends two requests, sent {len(client.bodies)}")
    return canonical_bytes(client.bodies[0]), canonical_bytes(client.bodies[1])


def targets_under_normal(
    world: SealedWorld, scenario: Scenario
) -> tuple[RetrievalTarget, ...] | None:
    oracle = oracle_for(world, scenario, RunCondition.all_reachable())
    return retrieval_targets(world, oracle) if isinstance(oracle, Answerable) else None


def document_bytes(world: SealedWorld, targets: tuple[RetrievalTarget, ...]) -> tuple[int, int]:
    """How many distinct documents carry a section target, and their text in bytes."""
    documents: dict[str, Document] = {}
    for target in targets:
        for carrier in target.carriers:
            if carrier.part.kind is EntityKind.COMMENT:
                continue
            record = world.index.records.get(carrier.record)
            if isinstance(record, Document):
                documents[record.id] = record
    size = sum(
        len(document.title.encode()) + sum(len(s.text.encode()) for s in document.sections)
        for document in documents.values()
    )
    return len(documents), size


def asks_for_several(targets: tuple[RetrievalTarget, ...]) -> bool:
    return any(
        isinstance(target.statement[2], Requirement) and target.statement[2].count >= 2
        for target in targets
    )


def forecast_scenario(
    world: SealedWorld, scenario: Scenario, configuration: dw.ProbeConfiguration
) -> ScenarioForecast:
    first, final = render_requests(world, scenario, configuration)
    targets = targets_under_normal(world, scenario)
    if targets is None:
        return ScenarioForecast(
            scenario.spec.id, True, len(first), len(final), 0, 0, {}, 0, 0, 0, 0, False
        )
    on_comments = sum(
        1 for t in targets if all(c.part.kind is EntityKind.COMMENT for c in t.carriers)
    )
    count, size = document_bytes(world, targets)
    return ScenarioForecast(
        scenario.spec.id,
        False,
        len(first),
        len(final),
        len(targets),
        sum(1 for t in targets if t.moves_a_required_key),
        dict(Counter(t.statement[1].value for t in targets)),
        on_comments,
        len(targets) - on_comments,
        count,
        size,
        asks_for_several(targets),
    )


def markdown(rows: list[ScenarioForecast], configuration: dw.ProbeConfiguration) -> str:
    caps = configuration.worker.caps
    assets = load_prompt_assets()
    lines = [
        "# The prompt check's forecast, computed before any live call",
        "",
        f"World `{dw.WORLD[:8]}…`, condition `{dw.CONDITION}`, level `{dw.LEVEL}`; the model "
        f"`{dw.MODEL}` at temperature 0 and {dw.OUTPUT_MAXIMUM:,} output tokens; caps "
        f"{caps.call_cap} calls and {caps.token_cap:,} tokens with "
        f"{caps.finalization_call_reserve} calls and {caps.finalization_token_reserve:,} tokens "
        "reserved for the finalization; "
        f"the registration at `{configuration.worker.preregistration_commit[:8]}`, the harness "
        f"at `{configuration.harness.commit[:8]}` ({configuration.harness.tree.value}); prompt "
        "digests "
        + ", ".join(f"{name} `{digest[:8]}`" for name, digest in sorted(assets.digests()))
        + f"; the reservation per run {configuration.reservation_pico_usd / 1e12:.2f} USD.",
        "",
        "Tokens are bounded from the request's bytes by the input-bound probe's ratio "
        f"({BYTES_PER_TOKEN[0]} to {BYTES_PER_TOKEN[1]} bytes a token); the live run reports "
        "the provider's count.",
        "",
        "| scenario | abstains | first request (bytes, tokens) | finalization with no read "
        "(bytes) | targets (required) | by predicate | on comments / on sections | documents "
        "holding section targets (count, bytes) | a clause asking for two or more |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        low, high = row.tokens(row.first_request_bytes)
        predicates = ", ".join(f"{k} {v}" for k, v in sorted(row.targets_by_predicate.items()))
        lines.append(
            f"| {row.scenario_id} | {'yes' if row.abstains else 'no'} | "
            f"{row.first_request_bytes:,}, {low:,} to {high:,} | "
            f"{row.finalization_request_bytes:,} | {row.targets} ({row.targets_required}) | "
            f"{predicates or 'none'} | {row.targets_on_comments} / {row.targets_on_sections} | "
            f"{row.documents_with_targets}, {row.document_bytes_with_targets:,} | "
            f"{'yes' if row.two_person_clause else 'no'} |"
        )
    total_first = sum(r.first_request_bytes for r in rows)
    lines += [
        "",
        f"Six first requests together: {total_first:,} bytes "
        f"({int(total_first / BYTES_PER_TOKEN[1]):,} to {int(total_first / BYTES_PER_TOKEN[0]):,} "
        "tokens).",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    world = dw.development_world()
    configuration = dw.probe_configuration(tree_state=TreeState.DIRTY)
    six = dw.live_iteration_scenarios(world)
    rows = [forecast_scenario(world, scenario, configuration) for scenario in six]
    (HERE / "forecast.json").write_text(
        json.dumps([row.__dict__ for row in rows], indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "forecast.md").write_text(markdown(rows, configuration), encoding="utf-8")
    # The console alone sees what is sealed.
    for scenario, row in zip(six, rows, strict=True):
        sealed: dict[str, Any] = {
            "tier": scenario.key.tier.value,
            "class": scenario.key.scenario_class.value,
        }
        print(row.scenario_id, sealed, f"first={row.first_request_bytes:,}B targets={row.targets}")
    print(f"written: {HERE / 'forecast.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
