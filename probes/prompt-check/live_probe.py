"""The prompt check's live run (the step's fork 15 with amendment 6): the real worker over the
real store and the real turns, the live clients, the first development world through the
planted readers and the corpus cache, the automatic approval, each export evaluated in
process by the real evaluator; publishing nothing.

One round is one prompt configuration over a list of scenarios, by default the six
live-iteration scenarios and the seventh the forecast added for the chain check. The
composition mirrors the work command's (``agent/__main__.py``) with the three substitutions
the forecast names: ``adapters.plantings.sealed_readers`` over the local truth root for the
vendor adapters, the laptop's ``leaveimpact_step9`` cache for the instance's, and a log
schema of its own on that database (``prompt_check``), created if absent and kept, so every
run's log survives for a later read. The frozen inputs are the draft registration's through
``agent_provenance`` (``development_world.probe_configuration``), as a production admission
records them; the ledger's threshold is set once per schema, far above what a round can
spend, since the caps are the registration's and the ledger is not what bounds a run here.

Per scenario the probe admits, works, publishes to an in-memory store, saves the export's
bytes outside the tree (``LEAVE_IMPACT_SPIKE_CAPTURES/prompt-check/<round>/``, refused when
unset or inside the repository: an export carries the model's text), evaluates, and reduces
the export and the evaluation to the shapes the report reads: the calls and dispatches, the
tokens and cost the account check sums, the ending, every fact-stage row, every emission's
class and refusal, every requirement placement with whether its span ran one word past a
sealed title, the nesting of the fact tool's input, whether a max-tokens stop arrived with a
tool use, and the plumbing checks that must be empty. The round's summary lands beside this
file as ``results/<round>-<stamp>.json`` and ``.md`` with ids, counts and states alone; the
spans and quotes stay in the capture directory's JSON.

``--dry`` runs the same path under the scripted "nothing further" client and the scripted
counter: no call, no spend, the plumbing proven end to end. A comparison round is this
script run again under ``--round <name>`` after the prompt asset's sentence has been removed
in ``agent/prompts/``; the digests the round ran under are recorded in its summary, so the
export's provenance and the report agree by construction.

    PYTHONPATH=. AWS_PROFILE=leave-impact LEAVE_IMPACT_SPIKE_CAPTURES=<dir> \\
        POSTGRES_PASSWORD=<the laptop's> uv run python probes/prompt-check/live_probe.py \\
        --round shipped [--scenarios scenario_009,scenario_013] [--dry]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent))

import development_world as dw  # noqa: E402

from leaveimpact.adapters.inference import (  # noqa: E402
    ConverseClient,
    CountingClient,
    inference_client,
)
from leaveimpact.adapters.object_store.local import LocalObjectReader  # noqa: E402
from leaveimpact.adapters.plantings import sealed_readers  # noqa: E402
from leaveimpact.adapters.wiring import run_export_publisher_over  # noqa: E402
from leaveimpact.agent.assets import load_prompt_assets  # noqa: E402
from leaveimpact.agent.commands import (  # noqa: E402
    PublishRequest,
    WorkerComposition,
    WorkRequest,
    publish,
    work,
)
from leaveimpact.agent.corpus import corpus_reader_for  # noqa: E402
from leaveimpact.agent.execution import ReadPorts  # noqa: E402
from leaveimpact.agent.inventory import PublicationRecord  # noqa: E402
from leaveimpact.agent.log_events import FrozenInputs, Producer  # noqa: E402
from leaveimpact.agent.log_store import AdmissionReceipt, AdmissionRequest, LogStore  # noqa: E402
from leaveimpact.agent.turns import InvestigatorTurns  # noqa: E402
from leaveimpact.agent.worker import AutomaticApproval  # noqa: E402
from leaveimpact.core.ids import ScenarioId  # noqa: E402
from leaveimpact.core.model_calls import (  # noqa: E402
    CompleteResponse,
    RefusedBeforeSend,
    RefusedInput,
)
from leaveimpact.core.predicates import PredicateName  # noqa: E402
from leaveimpact.core.run_export import RunExport  # noqa: E402
from leaveimpact.core.run_export_json import decode_export_bytes  # noqa: E402
from leaveimpact.core.run_timing import TreeState  # noqa: E402
from leaveimpact.core.stated import PlacementState  # noqa: E402
from leaveimpact.evaluator.grading import Graded, correct_whole  # noqa: E402
from leaveimpact.evaluator.sealed_world import SealedWorld  # noqa: E402
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run  # noqa: E402
from leaveimpact.world.scenario import Scenario  # noqa: E402
from tests.unit import worker_support as support  # noqa: E402
from tests.unit.in_memory_object_store import InMemoryObjectStore  # noqa: E402
from tests.unit.stating_fixture import title_of  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SCHEMA = "prompt_check"
DATABASE = "leaveimpact_step9"
LEDGER = "ledger-prompt-check"
THRESHOLD_PICO_USD = 20 * 10**12
"""Twenty dollars for the schema's whole life: a bound on the ledger, never on a round."""
LIMIT_PICO_USD = 270 * 10**12
"""The registered admission threshold limit (the draft's budget section)."""
ADMITTER = Producer("probe:prompt-check")
CHAIN_CHECK_SCENARIO = "scenario_014"
"""The forecast's seventh run: the one scenario of the two holding a clause asking for two
with the lower id."""
NESTED_DETAIL = "an entry is an object, got list"


# --- The composition -------------------------------------------------------------------------


def dsn_from_env(env: dict[str, str]) -> str:
    password = env.get("POSTGRES_PASSWORD", "")
    if not password:
        raise SystemExit("POSTGRES_PASSWORD names the laptop's database password")
    return f"postgresql://leaveimpact:{password}@127.0.0.1:5432/{DATABASE}"


def captures_root(env: dict[str, str]) -> Path:
    value = env.get("LEAVE_IMPACT_SPIKE_CAPTURES", "")
    if not value:
        raise SystemExit("LEAVE_IMPACT_SPIKE_CAPTURES names a directory outside the repository")
    root = Path(value).resolve()
    if root == dw.REPOSITORY or dw.REPOSITORY in root.parents:
        raise SystemExit("the capture directory must lie outside the repository")
    return root / "prompt-check"


def ensure_schema(dsn: str) -> None:
    with psycopg.connect(dsn, connect_timeout=5, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(SCHEMA)))


def store_in_schema(dsn: str) -> LogStore:
    def connect(target: str) -> psycopg.Connection[Any]:
        return psycopg.connect(
            target, connect_timeout=5, autocommit=True, options=f"-c search_path={SCHEMA}"
        )

    return LogStore(dsn=dsn, connect=connect)


def saver_in_schema(dsn: str) -> tuple[PostgresSaver, psycopg.Connection[DictRow]]:
    connection = psycopg.Connection[DictRow].connect(
        make_conninfo(
            dsn, options=f"-c search_path={SCHEMA}", application_name="prompt-check-saver"
        ),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    saver = PostgresSaver(connection)
    saver.setup()
    return saver, connection


@dataclass
class Clients:
    """The model-facing fillings of one run: live, or scripted under ``--dry``."""

    client: Any
    counter: Any


def live_clients() -> Clients:
    runtime = inference_client(dw.REGION)
    return Clients(ConverseClient(runtime), CountingClient(runtime))


def dry_clients() -> Clients:
    answer = support.answered(support.text("Nothing further to read."))
    return Clients(support.ContentScriptedClient((answer, answer)), support.ScriptedCounter())


# --- One run ---------------------------------------------------------------------------------


@dataclass
class RunResult:
    scenario_id: str
    run_id: str
    ending: str
    status: str | None
    failure: str | None
    wall_seconds: float
    logical_calls: int
    dispatches: int
    sends: int
    stop_reasons: dict[str, int]
    finalization_entered: int | None
    max_tokens_with_tool_use: int
    account_tokens: int | None
    account_pico_usd: int | None
    usage_input_tokens: int
    usage_output_tokens: int
    operations_by_tool: dict[str, int]
    model_reads: int
    claims: int
    targets: list[dict[str, Any]]
    emissions_by_class: dict[str, int]
    refusals_by_reason: dict[str, int]
    batches: int
    nested_batches: int
    requirements_stated: int
    placements: dict[str, int]
    overruns: int
    exclusions: dict[str, int]
    plumbing: dict[str, int]
    contradictions: int
    graded: dict[str, Any] | None
    report_findings: list[str]
    notes: list[str] = field(default_factory=list[str])


def admit(
    store: LogStore,
    configuration: dw.ProbeConfiguration,
    world: SealedWorld,
    scenario: Scenario,
    run_id: str,
) -> FrozenInputs:
    inputs = configuration.frozen_inputs(world.context_of(scenario))
    inputs = replace(inputs, run_id=run_id, attempt=1)
    receipt = store.admit(
        AdmissionRequest(f"req-{uuid4().hex[:12]}", inputs, ADMITTER, LEDGER, configuration.rules)
    )
    if not isinstance(receipt, AdmissionReceipt):
        raise AssertionError(f"the admission was refused: {receipt}")
    return inputs


def run_one(
    *,
    world: SealedWorld,
    scenario: Scenario,
    configuration: dw.ProbeConfiguration,
    dsn: str,
    clients: Clients,
    round_name: str,
    captures: Path,
) -> RunResult:
    run_id = f"pc-{round_name}-{scenario.spec.id}-{uuid4().hex[:6]}"
    store = store_in_schema(dsn)
    started = time.monotonic()
    try:
        inputs = admit(store, configuration, world, scenario, run_id)
        readers = sealed_readers(LocalObjectReader(dw.STORE_ROOT / "truth"), dw.WORLD)
        corpus = corpus_reader_for(inputs, dsn=dsn)
        saver, saver_connection = saver_in_schema(dsn)
        try:
            composition = WorkerComposition(
                configuration.worker,
                configuration.harness,
                configuration.rules,
                InvestigatorTurns(load_prompt_assets()),
                clients.client,
                clients.counter,
                ReadPorts(readers.people, readers.work, readers.calendar, corpus),
                AutomaticApproval(),
                saver,
            )
            ending = work(
                WorkRequest(run_id, 1, f"nonce-{uuid4().hex[:8]}", f"launch-{round_name}"),
                store,
                composition,
            )
        finally:
            saver_connection.close()
            corpus.close()
        memory = InMemoryObjectStore()
        record = publish(
            PublishRequest(run_id, 1, configuration.harness.commit),
            store,
            run_export_publisher_over(memory),
            rules=configuration.rules,
        )
        if not isinstance(record, PublicationRecord) or record.object_identity is None:
            raise AssertionError(f"the publication did not produce an export: {record}")
        held = memory.get(record.object_identity)
        assert held is not None
    finally:
        store.close()
    wall = time.monotonic() - started
    captures.mkdir(parents=True, exist_ok=True)
    (captures / f"{scenario.spec.id}.export.json").write_bytes(held.content)
    export = decode_export_bytes(held.content)
    evaluation = evaluate_run(
        world,
        export,
        table=configuration.rules.table,
        redispatch=configuration.rules.redispatch,
        retry=inputs.retry,
        counting_identifiers=dict(inputs.counting_identifiers),
    )
    result = reduce(world, scenario, run_id, ending.kind.value, export, evaluation, wall)
    (captures / f"{scenario.spec.id}.detail.json").write_text(
        json.dumps(detail(world, export, evaluation), indent=2, default=str), encoding="utf-8"
    )
    return result


# --- The reduction ---------------------------------------------------------------------------


def reduce(
    world: SealedWorld,
    scenario: Scenario,
    run_id: str,
    ending: str,
    export: RunExport,
    evaluation: Evaluation,
    wall: float,
) -> RunResult:
    trace = export.trace
    metrics = evaluation.metrics
    dispatches = [d for call in trace.model_calls for d in call.dispatches]
    complete = [d.observation for d in dispatches if isinstance(d.observation, CompleteResponse)]
    # A send is a dispatch that left the machine, a service error's included; only a refusal
    # before sending made none (the close's review: the first count was of complete responses).
    sends = sum(1 for d in dispatches if not isinstance(d.observation, RefusedBeforeSend))
    stop_reasons = Counter(o.stop_reason for o in complete)
    usage_in = usage_out = 0
    for d in dispatches:
        if d.usage is not None:
            raw = d.usage.raw
            usage_in += int(cast(int, raw.get("inputTokens", 0)))
            usage_out += int(cast(int, raw.get("outputTokens", 0)))
    max_tokens_tool = 0
    for call in trace.model_calls:
        if call.answer is None:
            continue
        for d in call.dispatches:
            o = d.observation
            if (
                isinstance(o, CompleteResponse)
                and o.stop_reason == "max_tokens"
                and call.answer.tool_calls
            ):
                max_tokens_tool += 1
    batches = nested = 0
    for call in trace.model_calls:
        if call.answer is None:
            continue
        for batch in call.answer.fact_batches:
            batches += 1
            entries = getattr(batch, "entries", ())
            if any(isinstance(e, RefusedInput) and NESTED_DETAIL in e.detail for e in entries):
                nested += 1
    facts = metrics.facts
    targets: list[dict[str, Any]] = []
    emissions: Counter[str] = Counter()
    refusals: Counter[str] = Counter()
    if facts is not None:
        for row in facts.targets:
            targets.append(
                {
                    "predicate": row.predicate.value,
                    "returned": row.returned,
                    "emitted": row.emitted,
                    "admitted": row.admitted,
                    "usable": row.usable,
                }
            )
        for emission in facts.emissions:
            emissions[emission.emission_class.value] += 1
            if emission.refusal is not None:
                refusals[emission.refusal.value] += 1
    composition = trace.composition
    placements = Counter(p.placement.state.value for p in composition.placements)
    overruns = sum(
        1 for p in composition.placements if overran(world, p.fact.target_span, p.placement.state)
    )
    requirements = sum(
        1
        for call in trace.model_calls
        if call.answer is not None
        for batch in call.answer.fact_batches
        for e in getattr(batch, "entries", ())
        if not isinstance(e, RefusedInput) and e.fact.predicate is PredicateName.REQUIRES
    )
    plumbing = {
        "prefetch": len(metrics.prefetch.findings) if metrics.prefetch.evaluated else -1,
        "recheck": len(metrics.recheck.findings),
        "ending": len(metrics.ending.findings),
        "cost": len(metrics.cost.findings),
        "counts": len(metrics.counts.findings),
        "account": len(metrics.account.findings) if metrics.account else -1,
        "calls": len(metrics.calls.findings) if metrics.calls else -1,
        "attribution": len(metrics.attribution.findings) if metrics.attribution else -1,
    }
    outcome = evaluation.outcome
    graded: dict[str, Any] | None = None
    report_findings: list[str] = []
    if isinstance(outcome, Graded):
        graded = {
            # The preregistration's first check, decided in the evaluation's claim rows and not
            # in these findings; absent from the fifteen rounds' files (`verdicts.py` read theirs).
            "correct_whole": correct_whole(outcome),
            "oracle_findings": len(outcome.oracle_findings or ()),
            "report_findings": len(outcome.report_findings or ()),
            "integrity": len(outcome.integrity),
            "harness_findings": list(outcome.harness_findings),
            "citations": len(outcome.grounding.citations) if outcome.grounding else None,
            "citations_resolving": (
                sum(1 for c in outcome.grounding.citations if c.resolves)
                if outcome.grounding
                else None
            ),
        }
        report_findings = [
            type(f).__name__ + ":" + str(getattr(f, "check", getattr(f, "kind", "")))
            for f in (outcome.report_findings or ())
        ]
    failure = export.record.failure
    return RunResult(
        scenario_id=scenario.spec.id,
        run_id=run_id,
        ending=ending,
        status=export.record.status.value,
        failure=None if failure is None else f"{failure.category.value}",
        wall_seconds=round(wall, 1),
        logical_calls=len(trace.model_calls),
        dispatches=len(dispatches),
        sends=sends,
        stop_reasons=dict(stop_reasons),
        finalization_entered=trace.finalization_entered,
        max_tokens_with_tool_use=max_tokens_tool,
        account_tokens=metrics.account.tokens if metrics.account else None,
        account_pico_usd=metrics.account.pico_usd if metrics.account else None,
        usage_input_tokens=usage_in,
        usage_output_tokens=usage_out,
        operations_by_tool=dict(Counter(op.tool for op in trace.operations)),
        model_reads=sum(
            1 for op in trace.operations if type(op.origin).__name__ != "PrefetchOrigin"
        ),
        claims=len(trace.claims),
        targets=targets,
        emissions_by_class=dict(emissions),
        refusals_by_reason=dict(refusals),
        batches=batches,
        nested_batches=nested,
        requirements_stated=requirements,
        placements=dict(placements),
        overruns=overruns,
        exclusions=dict(Counter(e.reason.value for e in composition.exclusions)),
        plumbing=plumbing,
        contradictions=len(evaluation.contradictions),
        graded=graded,
        report_findings=report_findings,
    )


def overran(world: SealedWorld, span: str | None, state: PlacementState) -> bool:
    """Whether an unplaced requirement's span is a sealed title plus one trailing word: the
    span probe's measured limitation."""
    if span is None or state is PlacementState.PLACED or " " not in span.strip():
        return False
    shorter = span.strip().rsplit(" ", 1)[0]
    return shorter in sealed_titles(world)


_TITLES: dict[str, frozenset[str]] = {}


def sealed_titles(world: SealedWorld) -> frozenset[str]:
    if world.version not in _TITLES:
        titles: set[str] = set()
        for ref in world.index.records:
            try:
                titles.add(title_of(world, ref))
            except Exception:  # noqa: BLE001 - a record with no title is no artifact a span names
                continue
        _TITLES[world.version] = frozenset(titles)
    return _TITLES[world.version]


def detail(world: SealedWorld, export: RunExport, evaluation: Evaluation) -> dict[str, Any]:
    """What stays outside the tree: every placement with its span and the sealed title it
    was measured against, every emission with its statement, every refusal's detail."""
    trace = export.trace
    rows: list[dict[str, Any]] = []
    for p in trace.composition.placements:
        rows.append(
            {
                "span": p.fact.target_span,
                "state": p.placement.state.value,
                "artifact": str(p.placement.artifact),
                "among": [str(a) for a in p.placement.among],
                "quote": p.fact.quote,
            }
        )
    refused: list[dict[str, Any]] = []
    for call in trace.model_calls:
        if call.answer is None:
            continue
        for batch in call.answer.fact_batches:
            for e in getattr(batch, "entries", ()):
                if isinstance(e, RefusedInput):
                    refused.append(
                        {
                            "call": call.id,
                            "reason": e.reason.value,
                            "detail": e.detail,
                            "raw": e.raw[:400],
                        }
                    )
                elif getattr(e, "reason", None) is not None:
                    refused.append(
                        {
                            "call": call.id,
                            "reason": e.reason.value,
                            "detail": e.detail,
                            "fact": str(e.fact),
                        }
                    )
    facts = evaluation.metrics.facts
    emissions = [
        {
            "class": e.emission_class.value,
            "fact": str(e.fact),
            "admitted": e.admitted,
            "refusal": None if e.refusal is None else e.refusal.value,
        }
        for e in (facts.emissions if facts else ())
    ]
    return {
        "placements": rows,
        "refused": refused,
        "emissions": emissions,
        "report_findings": [
            str(f) for f in (getattr(evaluation.outcome, "report_findings", None) or ())
        ],
        "oracle_findings": [
            str(f) for f in (getattr(evaluation.outcome, "oracle_findings", None) or ())
        ],
    }


# --- The round -------------------------------------------------------------------------------


def markdown(round_name: str, digests: dict[str, str], results: list[RunResult], dry: bool) -> str:
    lines = [
        f"# Round `{round_name}`{' (dry: scripted client, no call)' if dry else ''}",
        "",
        "Prompt digests: " + ", ".join(f"{k} `{v[:8]}`" for k, v in sorted(digests.items())) + ".",
        "",
        "| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | "
        "tokens (account; usage in/out) | cost (USD) | model reads by tool | targets "
        "returned/emitted/admitted/usable of n | emissions by class | refusals by reason | "
        "batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | "
        "plumbing findings | max-tokens with tool use | wall s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        n = len(r.targets)
        stages = (
            f"{sum(t['returned'] for t in r.targets)}/{sum(t['emitted'] for t in r.targets)}/"
            f"{sum(t['admitted'] for t in r.targets)}/{sum(t['usable'] for t in r.targets)} of {n}"
        )
        reads = (
            ", ".join(
                f"{k} {v}"
                for k, v in sorted(r.operations_by_tool.items())
                if k
                not in (
                    "leave",
                    "employees",
                    "leaves_within",
                    "components",
                    "work_items",
                    "events_within",
                )
            )
            or "none"
        )
        pl = r.placements
        plumbing = ", ".join(f"{k} {v}" for k, v in r.plumbing.items() if v != 0) or "all empty"
        cost = "n/a" if r.account_pico_usd is None else f"{r.account_pico_usd / 1e12:.4f}"
        def joined(counts: dict[str, int], empty: str = "none") -> str:
            return ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or empty

        cells = [
            r.scenario_id,
            f"{r.ending}/{r.status}" + (f"/{r.failure}" if r.failure else ""),
            f"{r.logical_calls} / {r.dispatches} / {r.sends}",
            joined(r.stop_reasons),
            str(r.finalization_entered),
            f"{r.account_tokens}; {r.usage_input_tokens}/{r.usage_output_tokens}",
            cost,
            reads,
            stages,
            joined(r.emissions_by_class),
            joined(r.refusals_by_reason),
            f"{r.batches} ({r.nested_batches})",
            f"{r.requirements_stated}: {pl.get('placed', 0)}/{pl.get('unplaced', 0)}/"
            f"{pl.get('ambiguous', 0)} ({r.overruns})",
            joined(r.exclusions),
            plumbing,
            str(r.max_tokens_with_tool_use),
            str(r.wall_seconds),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    total_cost = sum(r.account_pico_usd or 0 for r in results) / 1e12
    lines += [
        "",
        f"Round total: {sum(r.logical_calls for r in results)} logical calls, "
        f"{sum(r.usage_input_tokens for r in results):,} input and "
        f"{sum(r.usage_output_tokens for r in results):,} output tokens by usage, "
        f"{total_cost:.4f} USD by the account check.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--round", required=True, help="the prompt configuration's name")
    parser.add_argument(
        "--scenarios", default=None, help="comma-separated ids; default the six and the seventh"
    )
    parser.add_argument("--dry", action="store_true", help="scripted client, no call")
    args = parser.parse_args()
    env = dict(os.environ)
    dsn = dsn_from_env(env)
    captures = captures_root(env) / args.round
    world = dw.development_world()
    configuration = dw.probe_configuration(tree_state=TreeState.DIRTY)
    by_id = {s.spec.id: s for s in world.scenarios}
    if args.scenarios:
        ids = [ScenarioId(s.strip()) for s in str(args.scenarios).split(",") if s.strip()]
    else:
        ids = [s.spec.id for s in dw.live_iteration_scenarios(world)] + [
            ScenarioId(CHAIN_CHECK_SCENARIO)
        ]
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"not scenarios of the world: {missing}")
    ensure_schema(dsn)
    setup = store_in_schema(dsn)
    try:
        setup.ensure_schema()
        setup.set_threshold(
            LEDGER,
            THRESHOLD_PICO_USD,
            authority="probe:prompt-check",
            registration_commit=configuration.worker.preregistration_commit,
            limit_pico_usd=LIMIT_PICO_USD,
        )
    finally:
        setup.close()
    clients = dry_clients() if args.dry else live_clients()
    digests = dict(load_prompt_assets().digests())
    results: list[RunResult] = []
    for scenario_id in ids:
        result = run_one(
            world=world,
            scenario=by_id[scenario_id],
            configuration=configuration,
            dsn=dsn,
            clients=clients,
            round_name=args.round,
            captures=captures,
        )
        results.append(result)
        print(
            f"{result.scenario_id}: {result.ending}/{result.status} calls={result.logical_calls} "
            f"sends={result.sends} tokens={result.usage_input_tokens}/{result.usage_output_tokens} "
            f"targets={sum(t['admitted'] for t in result.targets)}/{len(result.targets)} "
            f"batches={result.batches}({result.nested_batches}) wall={result.wall_seconds}s",
            flush=True,
        )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RESULTS.mkdir(exist_ok=True)
    summary = {
        "round": args.round,
        "dry": args.dry,
        "stamp": stamp,
        "world": dw.WORLD,
        "harness": {
            "commit": configuration.harness.commit,
            "tree": configuration.harness.tree.value,
        },
        "registration_commit": configuration.worker.preregistration_commit,
        "prompt_digests": digests,
        "model": dw.MODEL,
        "output_maximum": dw.OUTPUT_MAXIMUM,
        "results": [asdict(r) for r in results],
    }
    (RESULTS / f"{args.round}-{stamp}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (RESULTS / f"{args.round}-{stamp}.md").write_text(
        markdown(args.round, digests, results, args.dry), encoding="utf-8"
    )
    print(f"written: {RESULTS / f'{args.round}-{stamp}.md'}; exports under {captures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
