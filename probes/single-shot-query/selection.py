"""The single-shot baseline's query selection: every candidate protocol scored, model-free, on
development worlds by what the real full-text search returns, under the procedure the step's
forks file fixed before any candidate was tried (M2 step 12, fork 5 as amended).

What runs. For each development world named on the line (loaded in the laptop's cache at its
padded level and sealed under the local object store's two roots), each of its scenarios
under the normal condition: the oracle's answer gives the retrieval targets, of which the
scored ones are those that move a required key and have at least one document-section
carrier (a target carried by ticket comments alone is not corpus-recoverable); the frozen
prefetch runs over the planted readers and the padded corpus adapter, exactly as a run's
would, and each candidate is rendered over what it returned with the production rendering
(``core.query_protocol.render_query``); the rendered text is searched once at the limit of
20, and a target counts as recovered at a limit when any of its section carriers' documents
is among the first that many results.

How the winner is chosen, fixed before any score was seen. The candidate with the most
required targets recovered at the limit of 20, pooled over every scenario of every world;
ties go to fewer template inputs, then the shorter mean rendered length over the scored
scenarios, then the earlier position in the candidate list. The limit is then the smallest
of 5, 10 and 20 whose pooled count for that candidate is within one target of its count at
20. The padded level is the one scored, since the padded list is the base list with filler
inserted and the shared ranks are unchanged, so a target returned within the limit at padded
is returned within it at base.

What is written. ``results/selection-<stamp>.md`` and its ``.json`` beside this file: the
worlds and scenario counts, the table of every candidate at every limit, the selection, and
the chosen protocol in the registration's own encoding; and nothing of any world's content
(ids and counts only, as the probes' convention asks of a public tree). The selected value
is written into the draft registration by hand from the json, labelled development; the
freeze re-selects by this same procedure on the worlds it then names.

Run from the repository root with the cache's database named and the local store present:

    DATABASE_URL=... uv run python probes/single-shot-query/selection.py <world-version>...
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
sys.path.insert(0, str(REPOSITORY))

from leaveimpact.adapters.corpus.adapter import CorpusAdapter, CorpusConfig  # noqa: E402
from leaveimpact.adapters.object_store.local import LocalObjectReader  # noqa: E402
from leaveimpact.adapters.plantings import planted_readers  # noqa: E402
from leaveimpact.agent.execution import Executor, ReadPorts, run_prefetch  # noqa: E402
from leaveimpact.core.enums import EntityKind  # noqa: E402
from leaveimpact.core.facts import RunCondition  # noqa: E402
from leaveimpact.core.ids import WorldVersion  # noqa: E402
from leaveimpact.core.query_protocol import (  # noqa: E402
    LiteralQuery,
    QueryInput,
    QueryProtocol,
    TemplateQuery,
    encode_query_protocol,
    render_query,
)
from leaveimpact.core.read_projection import project_reads  # noqa: E402
from leaveimpact.evaluator.oracle import Answerable, oracle_for  # noqa: E402
from leaveimpact.evaluator.retrieval_targets import RetrievalTarget, retrieval_targets  # noqa: E402
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world  # noqa: E402

STORE_ROOT = REPOSITORY / "data" / "object-store"
LEVEL = "padded"
LIMITS = (5, 10, 20)
SCORING_LIMIT = 20
WITHIN = 1
"""A smaller limit is chosen when its pooled count is within this many targets of the count
at the scoring limit."""

L1 = "handover or coverage or on-call or escalation"
L2 = "requires or required or responsible or owner"
L3 = "policy or runbook or account"
CANDIDATES: tuple[tuple[str, QueryProtocol], ...] = (
    ("L1", LiteralQuery(L1)),
    ("L2", LiteralQuery(L2)),
    ("L3", LiteralQuery(L3)),
    ("T1", TemplateQuery((QueryInput.COMPONENT_NAMES,), L1)),
    ("T2", TemplateQuery((QueryInput.LEAVER_NAME,), L1)),
    ("T3", TemplateQuery((QueryInput.WORK_ITEM_TITLES,), L1)),
    ("T4", TemplateQuery((QueryInput.COMPONENT_NAMES, QueryInput.WORK_ITEM_TITLES), L1)),
    ("T5", TemplateQuery((QueryInput.COMPONENT_NAMES, L2), L1)),
)
"""The candidates as the forks file wrote them before any was scored; T2 lost the team name,
which the prefetch returns no record of (the amendment of fork 5)."""


@dataclass(frozen=True)
class ScenarioScore:
    scenario_id: str
    scored_targets: int
    rendered_length: int
    recovered: dict[int, int]
    """Targets recovered at each limit."""


@dataclass(frozen=True)
class CandidateScore:
    name: str
    inputs: int
    scenarios: tuple[ScenarioScore, ...]

    def recovered(self, limit: int) -> int:
        return sum(s.recovered[limit] for s in self.scenarios)

    @property
    def mean_length(self) -> float:
        return mean(s.rendered_length for s in self.scenarios) if self.scenarios else 0.0


def scored_targets(world: SealedWorld, scenario: object) -> tuple[RetrievalTarget, ...]:
    """The targets a candidate is scored on: required, and carried by a document section
    somewhere; empty when the oracle has no answer for the scenario under the normal
    condition."""
    oracle = oracle_for(world, scenario, RunCondition.all_reachable())  # type: ignore[arg-type]
    if not isinstance(oracle, Answerable):
        return ()
    return tuple(
        target
        for target in retrieval_targets(world, oracle)
        if target.moves_a_required_key
        and any(carrier.part.kind is EntityKind.CLAUSE for carrier in target.carriers)
    )


def section_documents(target: RetrievalTarget) -> frozenset[str]:
    return frozenset(
        carrier.record.id for carrier in target.carriers if carrier.part.kind is EntityKind.CLAUSE
    )


def score_world(world: SealedWorld, dsn: str) -> dict[str, list[ScenarioScore]]:
    readers = planted_readers(world)
    adapter = CorpusAdapter(dsn=dsn, config=CorpusConfig(world.version), level=LEVEL)
    adapter.serving_check()
    by_candidate: dict[str, list[ScenarioScore]] = {name: [] for name, _ in CANDIDATES}
    try:
        for scenario in world.scenarios:
            targets = scored_targets(world, scenario)
            if not targets:
                continue
            context = world.context_of(scenario)
            executor = Executor(ReadPorts(readers.people, readers.work, readers.calendar, adapter))
            result = run_prefetch(executor, context)
            if result.leave is None:
                continue
            returned = project_reads(tuple(executor.operations), context.today).returned
            for name, protocol in CANDIDATES:
                query = render_query(protocol, returned, result.leave)
                hits = [seen.value.id for seen in adapter.search(query, limit=SCORING_LIMIT)]
                recovered = {
                    limit: sum(
                        1 for target in targets if section_documents(target) & set(hits[:limit])
                    )
                    for limit in LIMITS
                }
                by_candidate[name].append(
                    ScenarioScore(str(scenario.spec.id), len(targets), len(query), recovered)
                )
    finally:
        adapter.close()
    return by_candidate


def select(scores: tuple[CandidateScore, ...]) -> tuple[CandidateScore, int]:
    """The winner and its limit by the fixed rule."""
    ranked = sorted(
        enumerate(scores),
        key=lambda item: (
            -item[1].recovered(SCORING_LIMIT),
            item[1].inputs,
            item[1].mean_length,
            item[0],
        ),
    )
    winner = ranked[0][1]
    at_scoring = winner.recovered(SCORING_LIMIT)
    limit = next(limit for limit in LIMITS if winner.recovered(limit) >= at_scoring - WITHIN)
    return winner, limit


def main(argv: list[str]) -> int:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn or not argv:
        print("usage: DATABASE_URL=... selection.py <world-version>...", file=sys.stderr)
        return 2
    worlds = [
        load_sealed_world(
            WorldVersion(version),
            LocalObjectReader(STORE_ROOT / "truth"),
            LocalObjectReader(STORE_ROOT / "world"),
        )
        for version in argv
    ]
    pooled: dict[str, list[ScenarioScore]] = {name: [] for name, _ in CANDIDATES}
    per_world: list[dict[str, object]] = []
    for world in worlds:
        scored = score_world(world, dsn)
        for name, rows in scored.items():
            pooled[name].extend(rows)
        first = next(iter(scored.values()))
        per_world.append(
            {
                "world": str(world.version)[:8],
                "scenarios_scored": len(first),
                "scored_targets": sum(s.scored_targets for s in first),
            }
        )
    scores = tuple(
        CandidateScore(
            name,
            sum(isinstance(part, QueryInput) for part in getattr(protocol, "parts", ())),
            tuple(pooled[name]),
        )
        for name, protocol in CANDIDATES
    )
    winner, limit = select(scores)
    protocol = dict(CANDIDATES)[winner.name]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    total_targets = sum(s.scored_targets for s in scores[0].scenarios)
    lines = [
        f"# Single-shot query selection, {stamp}",
        "",
        "Model-free; the procedure and the candidates fixed in the step-12 forks file before "
        "any score was seen. Scored at the padded level on the worlds below, over every "
        "scenario with an answer under the normal condition, on the required targets carried "
        "by a document section.",
        "",
        "| world | scenarios scored | scored targets |",
        "|---|---|---|",
        *(
            f"| `{w['world']}…` | {w['scenarios_scored']} | {w['scored_targets']} |"
            for w in per_world
        ),
        "",
        f"Pooled scored targets: {total_targets}.",
        "",
        "| candidate | inputs | recovered @5 | @10 | @20 | mean rendered length |",
        "|---|---|---|---|---|---|",
        *(
            f"| {s.name} | {s.inputs} | {s.recovered(5)} | {s.recovered(10)} | {s.recovered(20)} | "
            f"{s.mean_length:.1f} |"
            for s in scores
        ),
        "",
        f"**Selected: {winner.name} at limit {limit}** (the most recovered at 20, ties by fewer "
        f"inputs, shorter mean length, list position; the limit the smallest within {WITHIN} "
        f"of the count at 20).",
        "",
        "```json",
        json.dumps(encode_query_protocol(protocol), indent=2),
        "```",
        "",
    ]
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    (results / f"selection-{stamp}.md").write_text("\n".join(lines), encoding="utf-8")
    (results / f"selection-{stamp}.json").write_text(
        json.dumps(
            {
                "stamp": stamp,
                "level": LEVEL,
                "worlds": per_world,
                "candidates": [
                    {
                        "name": s.name,
                        "inputs": s.inputs,
                        "recovered": {str(limit): s.recovered(limit) for limit in LIMITS},
                        "mean_rendered_length": round(s.mean_length, 1),
                        "scenarios": [
                            {
                                "scenario_id": row.scenario_id,
                                "scored_targets": row.scored_targets,
                                "rendered_length": row.rendered_length,
                                "recovered": {str(k): v for k, v in row.recovered.items()},
                            }
                            for row in s.scenarios
                        ],
                    }
                    for s in scores
                ],
                "selected": {
                    "candidate": winner.name,
                    "search_limit": limit,
                    "query_protocol": encode_query_protocol(protocol),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
