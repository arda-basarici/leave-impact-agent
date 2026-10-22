"""The results view over the public results: every row states a count over its denominator
with its interval named and directed, a cost as a mean and a median with a lower bound
rounded down and said, an unresolved interval and an unavailable comparison by their
recorded reasons, and the labels built from the file; the committed results render with
the base loss and the padded gain each in the row that carries its label."""

from __future__ import annotations

from dataclasses import replace
from functools import cache

from leaveimpact.app.results import (
    MECHANISM_CAPTION,
    SERVED_WORLD_LABEL,
    TRUNCATION_LABEL,
    ComparisonRow,
    ResultsView,
    TwoByTwo,
    changed_code_label,
    embargo_label,
    repeats_label,
    results_view,
)
from leaveimpact.results.committed import committed_results
from leaveimpact.results.public import Headroom
from tests.unit.test_results_codec import OVERALL, comparison, results


@cache
def committed_view() -> ResultsView:
    return results_view(committed_results())


def view() -> ResultsView:
    return results_view(results())


def test_an_arm_row_states_its_count_over_the_scenarios_with_its_wilson_interval() -> None:
    agent, degraded = view().arms
    assert (agent.name, agent.level, agent.count, agent.interval) == (
        "the investigator",
        "padded",
        "24 of 30",
        "0.63 to 0.90",
    )
    assert agent.unavailable is None
    assert [(tier.tier, tier.count) for tier in agent.tiers] == [("structured", "24 of 30")]
    assert degraded.count is None and degraded.interval is None
    assert degraded.unavailable == "no answer-quality checks (degraded condition)"


def test_a_count_without_an_interval_keeps_the_count() -> None:
    value = results()
    arm = value.arms[0]
    overall = arm.cells[0]
    assert overall.checks is not None
    (check,) = overall.checks
    without = replace(overall, checks=(replace(check, wilson=None),))
    value = replace(value, arms=(replace(arm, cells=(without, *arm.cells[1:])), value.arms[1]))
    row = results_view(value).arms[0]
    assert (row.count, row.interval, row.unavailable) == ("24 of 30", None, None)


def test_a_cost_is_a_mean_over_runs_beside_the_recorded_median_and_range() -> None:
    cost = view().arms[0].cost
    assert cost is not None
    assert (cost.total, cost.mean_per_run, cost.runs) == ("$2.2125", "$0.0738", 30)
    assert cost.median_per_run == "$0.0691 (from $0.0485 to $0.1940)"


def test_a_lower_bound_cost_says_at_least_and_rounds_down() -> None:
    value = results()
    arm = value.arms[0]
    overall = arm.cells[0]
    floored = replace(overall, cost=replace(overall.cost, floors=1))
    value = replace(value, arms=(replace(arm, cells=(floored, *arm.cells[1:])), value.arms[1]))
    built = results_view(value)
    cost = built.arms[0].cost
    assert cost is not None
    # 2212544400000 over 30 runs is 73,751,480,000 pico-dollars: $0.07375…, truncated.
    assert (cost.total, cost.mean_per_run) == ("at least $2.2125", "at least $0.0737")
    assert built.spend == replace(built.spend, total="at least $2.2125", floor=True)


def test_a_cell_with_no_runs_or_no_spread_renders_its_cost_unavailable() -> None:
    value = results()
    arm = value.arms[0]
    overall = arm.cells[0]
    empty = replace(overall, cost=replace(overall.cost, runs=0, pico_usd=0))
    value = replace(value, arms=(replace(arm, cells=(empty, *arm.cells[1:])), value.arms[1]))
    row = results_view(value).arms[0]
    assert (row.cost, row.cost_unavailable) == (None, "no runs")
    degraded = view().arms[1]
    assert (degraded.cost, degraded.cost_unavailable) == (None, "no per-run spread recorded")


def test_the_primary_comparison_counts_from_the_two_by_two_and_directs_its_interval() -> None:
    primary = view().primary
    assert primary.kind == "primary"
    assert primary.title == "the investigator against full context, padded"
    assert primary.direction == "the investigator minus full context"
    overall = primary.overall
    assert overall is not None
    assert (overall.first_count, overall.second_count) == ("24 of 30", "14 of 30")
    assert overall.two_by_two == TwoByTwo(14, 10, 0, 6)
    assert (overall.paired, overall.interval, overall.unresolved) == (30, "+0.20 to +0.47", None)
    (tier,) = primary.breakdowns
    assert (tier.stratum, tier.interval) == ("structured", None)
    assert tier.unresolved == "no interval: every resample equal"


def test_a_comparison_without_a_two_by_two_states_the_fractions() -> None:
    value = results()
    bare = replace(comparison(OVERALL, True), two_by_two=None)
    value = replace(value, primary=replace(value.primary, overall=bare))
    overall = results_view(value).primary.overall
    assert overall is not None
    assert (overall.first_count, overall.second_count, overall.two_by_two) == ("0.80", "0.47", None)


def test_an_unavailable_comparison_states_its_reason_and_no_figure() -> None:
    (secondary,) = view().secondary
    assert secondary.overall is None and secondary.breakdowns == ()
    assert secondary.unavailable == "an arm of the pair was not built"


def test_a_level_contrast_reads_padded_minus_base_for_one_system() -> None:
    (contrast,) = view().level_contrasts
    assert contrast.kind == "level contrast"
    assert contrast.title == "the investigator, padded against base"
    assert (contrast.first_name, contrast.second_name) == (
        "the investigator at padded",
        "the investigator at base",
    )
    assert contrast.direction == "padded minus base"
    assert contrast.overall is not None and contrast.overall.unresolved is not None


def test_a_descriptive_pair_is_its_headline_check_or_its_reason() -> None:
    (pair,) = view().descriptive
    assert pair.kind == "descriptive" and pair.unavailable is None
    assert pair.overall is not None and pair.overall.interval == "+0.20 to +0.47"
    value = results()
    unavailable = replace(value.descriptive[0], checks=(), unavailable="not computed")
    (row,) = results_view(replace(value, descriptive=(unavailable,))).descriptive
    assert (row.overall, row.unavailable) == (None, "not computed")
    headline_missing = replace(value.descriptive[0], checks=())
    (row,) = results_view(replace(value, descriptive=(headline_missing,))).descriptive
    assert row.unavailable == "no correct whole comparison at the overall stratum"


def test_the_mechanism_states_each_stage_over_its_denominator_or_what_it_is_pending_on() -> None:
    mechanism = view().mechanism
    assert (mechanism.name, mechanism.stages, mechanism.pending) == (
        "needed prose facts",
        ("returned", "emitted"),
        None,
    )
    (row,) = mechanism.rows
    assert (row.name, row.level) == ("the investigator", "padded")
    assert [(stage.stage, stage.count) for stage in row.stages] == [
        ("needed prose facts returned: all predicates", "884 of 986")
    ]
    pending = results_view(
        replace(results(), mechanism=None, mechanism_pending="prose_checkpoint_missing")
    ).mechanism
    assert (pending.name, pending.rows, pending.pending) == (
        None,
        (),
        "prose checkpoint missing",
    )


def test_headroom_states_what_the_reference_did_not_pass_or_why_there_is_no_count() -> None:
    (row,) = view().headroom
    assert (row.level, row.text) == (
        "padded",
        "20 of 30 scenarios the rules-only reference did not pass",
    )
    missing = Headroom("normal", "base", None, None, "reference_arm_not_run")
    (row,) = results_view(replace(results(), headroom=(missing,))).headroom
    assert row.text == "unavailable: reference arm not run"


def test_a_cell_not_run_names_its_arm_and_its_reason() -> None:
    (row,) = view().not_run
    assert (row.name, row.condition, row.level) == ("full context", "jira_down", "base")
    assert row.why == "group not run: full_context_under_outage"


def test_the_labels_are_built_from_the_file_and_the_captions_are_the_same_sentences() -> None:
    built = view()
    assert built.labels[0] == SERVED_WORLD_LABEL
    assert built.labels[2] == TRUNCATION_LABEL
    assert built.arms_caption == built.labels[1] == repeats_label(results().disclosures)
    assert built.comparisons_caption == TRUNCATION_LABEL
    assert built.mechanism_caption == MECHANISM_CAPTION
    assert built.labels[3] == (
        "The evaluation was produced by code one file different from the registration's "
        "bind: src/leaveimpact/evaluator/cells.py."
    )
    assert built.labels[4].startswith("The measurement world is embargoed:")
    assert built.disclosures.repeats == built.labels[1]
    assert built.interval_method == (
        "Intervals are at 95%: Wilson for a count; a paired scenario bootstrap of 10,000 "
        "resamples for a difference, read as the first system minus the second."
    )
    disclosures = results().disclosures
    unchanged = replace(disclosures, evaluated_by_changed_code=False, changed=())
    assert changed_code_label(unchanged) == (
        "The evaluation was produced by the code the registration binds."
    )
    assert embargo_label(replace(disclosures, world_disclosure="open")) == (
        "The measurement world's disclosure is recorded as open."
    )
    assert repeats_label(replace(disclosures, repeats_per_scenario=3)).startswith(
        "3 runs per scenario:"
    )


def test_the_spend_sums_every_arms_overall_cell() -> None:
    assert view().spend == replace(view().spend, total="$2.2125", runs=60, floor=False)


def test_the_provenance_names_the_artifact_the_world_and_the_registration() -> None:
    items = dict(view().provenance.items)
    assert items["Evaluation artifact"] == "f" * 64
    assert items["Measurement world"] == "2" * 64
    assert items["Registration"] == "a" * 64
    assert items["Coverage"] == (
        "240 attempts intended, 240 admitted, 240 exported, 0 failed by defect, 0 by infrastructure"
    )


# --- The committed file, the real producer ----------------------------------------------


def _row(rows: tuple[ComparisonRow, ...], title: str) -> ComparisonRow:
    (row,) = [row for row in rows if row.title == title]
    return row


def test_the_committed_results_render_every_arm_in_the_files_order() -> None:
    built = committed_view()
    assert [(row.system, row.level, row.count) for row in built.arms] == [
        ("agent", "base", "24 of 30"),
        ("agent", "padded", "24 of 30"),
        ("full_context", "base", "30 of 30"),
        ("full_context", "padded", "14 of 30"),
        ("rules_only", "base", "10 of 30"),
        ("rules_only", "padded", "10 of 30"),
        ("single_shot", "base", "22 of 30"),
        ("single_shot", "padded", "10 of 30"),
    ]
    assert all(row.unavailable is None and row.cost is not None for row in built.arms)
    assert [tier.count for tier in built.arms[1].tiers] == ["10 of 10", "4 of 10", "10 of 10"]
    assert built.spend == replace(built.spend, total="$9.9594", runs=240, floor=False)


def test_the_committed_results_show_the_base_loss_and_the_padded_gain_in_their_rows() -> None:
    built = committed_view()
    base = _row(built.descriptive, "the investigator against full context, base")
    assert base.overall is not None
    assert (base.overall.first_count, base.overall.second_count, base.overall.interval) == (
        "24 of 30",
        "30 of 30",
        "-0.30 to -0.10",
    )
    padded = built.primary
    assert padded.title == "the investigator against full context, padded"
    assert padded.overall is not None
    assert (padded.overall.first_count, padded.overall.second_count, padded.overall.interval) == (
        "24 of 30",
        "14 of 30",
        "+0.20 to +0.47",
    )
    assert padded.overall.two_by_two == TwoByTwo(14, 10, 0, 6)
    assert [row.title for row in built.secondary] == [
        "the investigator against single shot, base",
        "the investigator against single shot, padded",
    ]
    assert [(row.title, row.direction) for row in built.level_contrasts] == [
        ("the investigator, padded against base", "padded minus base"),
        ("single shot, padded against base", "padded minus base"),
        ("full context, padded against base", "padded minus base"),
    ]
    assert len(built.descriptive) == 12
    for row in (*built.secondary, *built.level_contrasts, *built.descriptive):
        assert row.unavailable is None and row.overall is not None
        assert (row.overall.interval is None) == (row.overall.unresolved is not None)


def test_the_committed_results_mechanism_headroom_and_not_run_rows() -> None:
    built = committed_view()
    assert built.mechanism.stages == ("returned", "emitted", "admitted", "usable")
    stages = {
        (row.system, row.level): [s.count for s in row.stages] for row in built.mechanism.rows
    }
    assert stages[("agent", "padded")] == ["31 of 31", "26 of 31", "26 of 31", "25 of 31"]
    assert stages[("full_context", "padded")] == ["31 of 31", "6 of 31", "6 of 31", "6 of 31"]
    assert [(row.level, row.text) for row in built.headroom] == [
        ("base", "20 of 30 scenarios the rules-only reference did not pass"),
        ("padded", "20 of 30 scenarios the rules-only reference did not pass"),
    ]
    assert [(row.name, row.condition) for row in built.not_run] == [
        ("full context", "jira_down"),
        ("full context", "calendar_down"),
        ("full context", "frappe_down"),
        ("full context", "corpus_down"),
    ]
    assert built.labels[3] == (
        "The evaluation was produced by code 2 files different from the registration's bind: "
        "src/leaveimpact/evaluator/cells.py, src/leaveimpact/evaluator/entrypoint.py."
    )
