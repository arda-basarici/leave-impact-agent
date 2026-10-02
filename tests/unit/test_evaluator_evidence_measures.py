"""The evidence-side measures, each as a numerator and a denominator of one run with its own
scope. Grounding and citations are over a replayed report, graded runs and limited runs apart;
source discipline is over every run; retrieval is where the oracle had an answer. A truthful
report over a full read is reproduced whole and cites nothing, which is measured as nothing
cited and never as perfect citation; the citing report resolves, was retrieved and is used
throughout."""

from collections import Counter
from dataclasses import replace

import pytest

from leaveimpact.core import EntityKind, Source
from leaveimpact.core.refs import EvidenceRef
from leaveimpact.evaluator.evidence_measures import (
    GROUNDING_AND_CITATION_MEASURES,
    RETRIEVAL_MEASURES,
    SOURCE_MEASURES,
    citing_a_witness_share,
    citing_share,
    grounded_end_to_end_share,
    hit_ranks,
    local_failure_share,
    repeated_citations,
    resolving_share,
    retrieved_against_concluded,
    retrieved_share,
    standing_share,
    strictly_grounded_share,
    used_share,
)
from leaveimpact.evaluator.grading import Excluded, Graded, Limited
from leaveimpact.evaluator.measures import Counts, Measure
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from tests.unit.evaluation_fixture import NORMAL, evaluated, truthful
from tests.unit.export_fixture import provider_failed_export
from tests.unit.reads_fixture import Recorder, full_read, systems_holding
from tests.unit.report_fixture import citing, renumbered
from tests.unit.throwaway_world import loaded_world

REPRODUCED, CONTRADICTED, UNSUPPORTED = (
    Standing.REPRODUCED,
    Standing.CONTRADICTED,
    Standing.UNSUPPORTED,
)
SOURCE = {measure.name: measure for measure in SOURCE_MEASURES}
RETRIEVAL = {measure.name: measure for measure in RETRIEVAL_MEASURES}


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def counts(measure: Measure, evaluation: Evaluation) -> Counts:
    found = measure.of(evaluation)
    assert found is not None, measure.name
    return found


def total(measure: Measure, evaluations: list[Evaluation]) -> Counts:
    each = [counts(measure, evaluation) for evaluation in evaluations]
    return sum(n for n, _ in each), sum(d for _, d in each)


def test_a_truthful_report_over_a_full_read_is_reproduced_whole_and_cites_nothing(
    world: SealedWorld,
) -> None:
    runs = [evaluated(world, scenario) for scenario in world.scenarios]
    assert total(standing_share(REPRODUCED, Graded), runs) == (1_001, 1_001)
    assert total(standing_share(CONTRADICTED, Graded), runs) == (0, 1_001)
    assert total(standing_share(UNSUPPORTED, Graded), runs) == (0, 1_001)
    assert total(local_failure_share(Graded), runs) == (0, 1_001)
    assert total(grounded_end_to_end_share(Graded), runs) == (1_001, 1_001)
    # The strict reading leaves out what stood without the corpus closed.
    assert total(strictly_grounded_share(Graded), runs) == (547, 1_001)
    # Nothing cited is nothing cited: no citation to judge, and never a perfect score.
    assert total(citing_share(Graded), runs) == (0, 1_001)
    for quality in (resolving_share, retrieved_share, used_share):
        assert total(quality(Graded), runs) == (0, 0)
    assert total(citing_a_witness_share(Graded), runs) == (0, 1_001)
    # A graded run is in no measure over limited runs: the two are never pooled.
    limited_only = [m for m in GROUNDING_AND_CITATION_MEASURES if m.name.endswith("limited runs")]
    assert len(limited_only) == len(GROUNDING_AND_CITATION_MEASURES) // 2 == 11
    assert all(measure.of(runs[0]) is None for measure in limited_only)


def test_a_report_citing_its_own_witnesses_resolves_was_retrieved_and_is_used(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    plain = evaluated(world, scenario)
    assert isinstance(plain.outcome, Graded) and plain.outcome.grounding is not None
    report = truthful(world, scenario, NORMAL)
    cited = citing(report, plain.outcome.grounding.claims)
    run = evaluated(world, scenario, claims=cited)
    made = sum(len(claim.evidence_refs) for claim in cited)
    assert made > 0
    for quality in (resolving_share, retrieved_share, used_share):
        assert counts(quality(Graded), run) == (made, made)
    citers = sum(bool(claim.evidence_refs) for claim in cited)
    assert counts(citing_share(Graded), run) == (citers, len(cited))
    assert counts(citing_a_witness_share(Graded), run) == (citers, len(cited))
    assert repeated_citations(run) == 0

    # One record cited twice by a claim, by another field: one citation for the ratios,
    # one repeat for the audit.
    first = next(claim for claim in cited if claim.evidence_refs)
    again = replace(first.evidence_refs[0], field="title")
    twice = replace(first, evidence_refs=(*first.evidence_refs, again))
    doubled = evaluated(
        world, scenario, claims=tuple(twice if claim is first else claim for claim in cited)
    )
    assert counts(resolving_share(Graded), doubled) == (made, made)
    assert repeated_citations(doubled) == 1
    assert isinstance(again, EvidenceRef)


def test_a_report_with_nothing_read_is_unsupported_throughout(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    blind = evaluated(world, scenario, operations=())
    claims = len(truthful(world, scenario, NORMAL))
    assert counts(standing_share(UNSUPPORTED, Graded), blind) == (claims, claims)
    assert counts(standing_share(REPRODUCED, Graded), blind) == (0, claims)
    assert counts(local_failure_share(Graded), blind) == (claims, claims)
    assert counts(grounded_end_to_end_share(Graded), blind) == (0, claims)


def test_grounding_is_measured_on_a_limited_run_apart_and_not_where_it_was_not_evaluated(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    report = truthful(world, scenario, NORMAL)
    limited = evaluated(world, scenario, down=(Source.FRAPPE,), claims=report)
    assert isinstance(limited.outcome, Limited)
    assert standing_share(REPRODUCED, Graded).of(limited) is None
    # With the HR system down nothing of the report could be reproduced.
    assert counts(standing_share(REPRODUCED, Limited), limited) == (0, len(report))
    assert counts(grounded_end_to_end_share(Limited), limited) == (0, len(report))

    invalid = evaluated(world, scenario, claims=(*report, renumbered(report[0], 9_999)))
    excluded = evaluate_run(world, provider_failed_export(world, scenario))
    assert isinstance(excluded.outcome, Excluded)
    for unreplayed in (invalid, excluded):
        # Not evaluated, which is not "nothing grounded".
        assert all(m.of(unreplayed) is None for m in GROUNDING_AND_CITATION_MEASURES)
        assert repeated_citations(unreplayed) is None


def test_source_discipline_is_measured_on_every_run_with_its_parts_where_they_exist(
    world: SealedWorld,
) -> None:
    scenario = next(s for s in world.scenarios if Source.JIRA in s.key.required_sources)
    required = len(scenario.key.required_sources)
    full = evaluated(world, scenario)
    assert counts(SOURCE["required sources asked"], full) == (required, required)
    assert counts(SOURCE["required sources answered"], full) == (required, required)
    # A rules-only run made no tool request: nothing refused of nothing, not a zero rate.
    assert counts(SOURCE["tool requests refused"], full) == (0, 0)
    contribution = full.metrics.contribution
    assert contribution is not None
    completed = len(contribution.contributing) + len(contribution.extra)
    assert counts(SOURCE["completed reads repeated"], full) == (0, completed)
    assert counts(SOURCE["completed reads extra"], full) == (len(contribution.extra), completed)

    tracker_down = evaluated(world, scenario, down=(Source.JIRA,))
    assert counts(SOURCE["required sources asked"], tracker_down) == (required, required)
    assert counts(SOURCE["required sources answered"], tracker_down) == (required - 1, required)

    # A failed attempt: no report was replayed, so no read is called extra; the rest stands.
    failed = evaluate_run(world, provider_failed_export(world, scenario))
    assert counts(SOURCE["required sources asked"], failed) == (0, required)
    assert SOURCE["completed reads extra"].of(failed) is None
    assert counts(SOURCE["completed reads repeated"], failed) == (0, 0)


def test_retrieval_is_measured_where_the_oracle_had_an_answer(world: SealedWorld) -> None:
    runs = [evaluated(world, scenario) for scenario in world.scenarios]
    assert total(RETRIEVAL["targets retrieved"], runs) == (35, 35)
    assert total(RETRIEVAL["targets a required row rests on retrieved"], runs) == (31, 31)
    # The fixture reads documents by id: no search was made, so no hit rate exists.
    assert total(RETRIEVAL["searches with a hit"], runs) == (0, 0)
    assert total(RETRIEVAL["searchable targets returned per search"], runs) == (0, 0)
    concluded: Counter[tuple[bool, bool]] = Counter()
    for run in runs:
        concluded.update(retrieved_against_concluded(run) or {})
    assert concluded == {(True, True): 31}
    # A scenario with no target is in scope with nothing to count.
    empty = [run for run in runs if counts(RETRIEVAL["targets retrieved"], run) == (0, 0)]
    assert len(empty) == 10

    scenario = world.scenarios[0]
    limited = evaluated(
        world, scenario, down=(Source.FRAPPE,), claims=truthful(world, scenario, NORMAL)
    )
    assert all(measure.of(limited) is None for measure in RETRIEVAL_MEASURES)
    assert retrieved_against_concluded(limited) is None and hit_ranks(limited) is None


def test_a_searchs_hits_are_counted_per_search_with_their_ranks(world: SealedWorld) -> None:
    scenario = next(
        s
        for s in world.scenarios
        if (found := evaluated(world, s).metrics.retrieval)
        and any(each.searchable for each in found.targets)
    )
    retrieval = evaluated(world, scenario).metrics.retrieval
    assert retrieval is not None
    stated = next(each.target for each in retrieval.targets if each.searchable)
    assert stated.carriers[0].part.kind is EntityKind.CLAUSE
    text = world.index.parts[stated.carriers[0].part].content.text
    reads = Recorder(systems_holding(world))
    full_read(reads, world, scenario)
    reads.read("search", {"query": text[:60].strip(), "limit": 5})
    reads.read("search", {"query": "no document says this anywhere", "limit": 5})
    run = evaluated(world, scenario, operations=reads.operations)
    assert counts(RETRIEVAL["searches with a hit"], run) == (1, 2)
    searchable = sum(each.searchable for each in retrieval.targets)
    ranks = hit_ranks(run)
    assert ranks is not None and len(ranks) >= 1 and min(ranks) >= 1
    assert counts(RETRIEVAL["searchable targets returned per search"], run) == (
        len(ranks),
        searchable * 2,
    )
