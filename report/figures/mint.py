"""Mint the report's figures from the committed results.

Four data figures and one diagram. Each data figure has a pure function returning plain
tuples from the committed public results (``headline_data``, ``tier_data``,
``mechanism_data``, ``cost_quality_data``) and a drawing function beside it; the
instrument diagram is drawn from no data. Systems keep one fixed colour and marker each
across every figure, so a reader who learns the investigator's blue once keeps it; the
corpus level is filled against hollow, so colour is never the only carrier. Counts are
labelled directly where the chart is read, intervals are drawn thin, and every axis
starts at zero.

Run from the repository root::

    uv run --group report python -m report.figures.mint [--out DIR]
"""

# pyright: basic
# The plotting library ships partial stubs; the data functions above the drawing
# shell are what the tests assert, and the package sits outside the strict include.

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from leaveimpact.results.committed import committed_results  # noqa: E402
from leaveimpact.results.public import Cell, PublicResults  # noqa: E402

__all__ = [
    "SYSTEMS",
    "cost_quality_data",
    "headline_data",
    "mechanism_data",
    "mint_all",
    "tier_data",
]

OUT = Path(__file__).resolve().parent

SYSTEMS: tuple[tuple[str, str, str, str], ...] = (
    ("agent", "Investigator", "#2a78d6", "o"),
    ("full_context", "Full context", "#eb6834", "s"),
    ("single_shot", "Single shot", "#1baf7a", "^"),
    ("rules_only", "Rules only", "#eda100", "D"),
)
"""Each system's registered name, its label, its colour (the chart palette's first four
categorical slots, in fixed order) and its marker."""

LEVELS = ("base", "padded")
TIERS = ("structured", "fragmented", "adversarial")
INK = "#2b2b2b"
MUTED = "#7a7a7a"
GRID = "#e4e4e4"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _overall(results: PublicResults, system: str, level: str) -> Cell:
    (arm,) = [a for a in results.arms if a.system == system and a.level == level]
    (cell,) = [c for c in arm.cells if c.stratum.kind == "overall"]
    return cell


def _tier(results: PublicResults, system: str, level: str, tier: str) -> Cell:
    (arm,) = [a for a in results.arms if a.system == system and a.level == level]
    (cell,) = [c for c in arm.cells if c.stratum.kind == "tier" and c.stratum.name == tier]
    return cell


def _whole(cell: Cell) -> tuple[int, float, float]:
    """The correct-whole count, end to end, and its Wilson interval as fractions."""
    (check,) = [
        c for c in cell.checks or () if c.check == "correct_whole" and c.reading == "end_to_end"
    ]
    if check.wilson is None:
        raise ValueError(f"no Wilson interval at {cell.stratum}")
    return int(check.passed), check.wilson.low, check.wilson.high


def headline_data(results: PublicResults) -> tuple[tuple[str, str, int, int, float, float], ...]:
    """Per system and level: the correct-whole count, the scenarios, and the Wilson
    interval's ends as fractions."""
    rows: list[tuple[str, str, int, int, float, float]] = []
    for system, _, _, _ in SYSTEMS:
        for level in LEVELS:
            cell = _overall(results, system, level)
            passed, low, high = _whole(cell)
            rows.append((system, level, passed, cell.accounting.scenarios, low, high))
    return tuple(rows)


def tier_data(results: PublicResults) -> tuple[tuple[str, str, str, int, int], ...]:
    """Per system, level and tier: the correct-whole count and the tier's scenarios."""
    rows: list[tuple[str, str, str, int, int]] = []
    for system, _, _, _ in SYSTEMS:
        for level in LEVELS:
            for tier in TIERS:
                cell = _tier(results, system, level, tier)
                passed, _, _ = _whole(cell)
                rows.append((system, level, tier, passed, cell.accounting.scenarios))
    return tuple(rows)


def mechanism_data(
    results: PublicResults,
) -> tuple[tuple[str, ...], tuple[tuple[str, tuple[int, ...], int], ...]]:
    """The stage names, then per arm at the padded level (investigator and full context)
    the needed facts reaching each stage and the denominator."""
    if results.mechanism is None:
        raise ValueError("the results hold no mechanism measure")
    arms: list[tuple[str, tuple[int, ...], int]] = []
    for system in ("agent", "full_context"):
        (arm,) = [a for a in results.mechanism.arms if a.system == system and a.level == "padded"]
        stages = [s for s in arm.stages if s.stratum.kind == "overall"]
        arms.append((system, tuple(s.numerator for s in stages), stages[0].denominator))
    return tuple(results.mechanism.stages), tuple(arms)


def cost_quality_data(results: PublicResults) -> tuple[tuple[str, str, float, int], ...]:
    """Per system and level: the per-run cost in dollars (the cell's total over its runs)
    and the correct-whole count."""
    rows: list[tuple[str, str, float, int]] = []
    for system, _, _, _ in SYSTEMS:
        for level in LEVELS:
            cell = _overall(results, system, level)
            per_run = cell.cost.pico_usd / cell.cost.runs / 1e12
            passed, _, _ = _whole(cell)
            rows.append((system, level, per_run, passed))
    return tuple(rows)


def _level_legend(ax: Axes, colour: str = MUTED) -> None:
    handles = [
        Line2D([], [], marker="o", color=colour, linestyle="", markersize=7, label="base level"),
        Line2D(
            [],
            [],
            marker="o",
            color=colour,
            markerfacecolor="white",
            linestyle="",
            markersize=7,
            label="padded level",
        ),
    ]
    ax.legend(handles=handles, frameon=False, loc="lower left", fontsize=8)


def draw_headline(results: PublicResults, out: Path) -> None:
    rows = headline_data(results)
    fig, ax = plt.subplots(figsize=(7.2, 3.3), dpi=200)
    offsets = {"base": -0.17, "padded": 0.17}
    for index, (system, _, colour, marker) in enumerate(SYSTEMS):
        for level in LEVELS:
            (row,) = [r for r in rows if r[0] == system and r[1] == level]
            _, _, passed, scenarios, low, high = row
            x = index + offsets[level]
            ax.plot([x, x], [low * scenarios, high * scenarios], color=colour, linewidth=1.4)
            ax.plot(
                x,
                passed,
                marker=marker,
                color=colour,
                markersize=8,
                markerfacecolor=colour if level == "base" else "white",
                markeredgewidth=1.6,
            )
            ax.annotate(
                str(passed),
                (x, passed),
                xytext=(8, 0),
                textcoords="offset points",
                va="center",
                fontsize=8.5,
                color=INK,
            )
    ax.set_xticks(range(len(SYSTEMS)), [s[1] for s in SYSTEMS])
    ax.set_ylim(0, 31)
    ax.set_yticks([0, 10, 20, 30])
    ax.set_ylabel("scenarios correct whole, of 30")
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    _level_legend(ax)
    fig.tight_layout()
    fig.savefig(out / "headline.png")
    plt.close(fig)


def draw_tiers(results: PublicResults, out: Path) -> None:
    rows = tier_data(results)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), dpi=200, sharey=True)
    width = 0.19
    for ax, level in zip(axes, LEVELS, strict=True):
        for index, (system, label, colour, _) in enumerate(SYSTEMS):
            xs = [t + (index - 1.5) * width for t in range(len(TIERS))]
            counts = [
                next(r[3] for r in rows if r[0] == system and r[1] == level and r[2] == tier)
                for tier in TIERS
            ]
            ax.bar(xs, counts, width=width * 0.88, color=colour, label=label)
            for x, count in zip(xs, counts, strict=True):
                ax.annotate(
                    str(count),
                    (x, count),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha="center",
                    fontsize=7.5,
                    color=INK,
                )
        ax.set_title(f"{level} level", fontsize=9.5, color=INK, loc="left")
        ax.set_xticks(range(len(TIERS)), [f"{t}\n(10 scenarios)" for t in TIERS])
        ax.set_ylim(0, 11.5)
        ax.set_yticks([0, 5, 10])
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("scenarios correct whole")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="lower center", ncol=4)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out / "tiers.png")
    plt.close(fig)


def draw_mechanism(results: PublicResults, out: Path) -> None:
    stages, arms = mechanism_data(results)
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=200)
    width = 0.34
    for index, (system, counts, denominator) in enumerate(arms):
        (_, label, colour, _) = next(s for s in SYSTEMS if s[0] == system)
        xs = [i + (index - 0.5) * width for i in range(len(stages))]
        ax.bar(xs, counts, width=width * 0.9, color=colour, label=f"{label}, padded level")
        for x, count in zip(xs, counts, strict=True):
            ax.annotate(
                str(count),
                (x, count),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color=INK,
            )
        ax.axhline(denominator, color=MUTED, linewidth=0.6, linestyle=(0, (3, 3)))
    ax.set_xticks(range(len(stages)), list(stages))
    ax.set_ylim(0, 34)
    ax.set_yticks([0, 10, 20, 31])
    ax.set_ylabel("needed prose facts, of 31")
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(out / "mechanism.png")
    plt.close(fig)


def draw_cost_quality(results: PublicResults, out: Path) -> None:
    rows = cost_quality_data(results)
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=200)
    # Two pairs of marks sit on top of each other (the investigator's levels, rules
    # only's), so their labels are placed above and below by hand.
    offsets = {
        ("agent", "base"): (22, -22),
        ("agent", "padded"): (22, 16),
        ("rules_only", "base"): (8, 6),
        ("rules_only", "padded"): (8, -11),
    }
    for system, label, colour, marker in SYSTEMS:
        for level in LEVELS:
            (row,) = [r for r in rows if r[0] == system and r[1] == level]
            _, _, per_run, passed = row
            ax.plot(
                per_run,
                passed,
                marker=marker,
                color=colour,
                markersize=8,
                linestyle="",
                markerfacecolor=colour if level == "base" else "white",
                markeredgewidth=1.6,
            )
            leader = {"arrowstyle": "-", "color": MUTED, "linewidth": 0.6}
            ax.annotate(
                f"{label}, {level}",
                (per_run, passed),
                xytext=offsets.get((system, level), (6, 7)),
                textcoords="offset points",
                fontsize=7.5,
                color=INK,
                arrowprops=leader if system == "agent" else None,
            )
    ax.set_xlim(-0.004, 0.1)
    ax.set_ylim(0, 32)
    ax.set_yticks([0, 10, 20, 30])
    ax.set_xlabel("mean model cost per run (USD)")
    ax.set_ylabel("scenarios correct whole, of 30")
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    _level_legend(ax)
    fig.tight_layout()
    fig.savefig(out / "cost-quality.png")
    plt.close(fig)


def _box(
    ax: Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    edge: str = INK,
    fill: str = "white",
    dashed: bool = False,
    size: float = 8,
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        edgecolor=edge,
        facecolor=fill,
        linewidth=1.0,
        linestyle=(0, (3, 2)) if dashed else "solid",
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=INK)


def _arrow(ax: Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "color": INK,
            "linewidth": 0.9,
            "shrinkA": 0,
            "shrinkB": 0,
        },
    )


def draw_instrument(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.35, 5.0)
    ax.axis("off")
    # Two worlds enter one pipeline.
    _box(ax, 0.2, 3.9, 2.0, 0.8, "Golden world\nseed published, open", fill="#f3f7fd")
    _box(
        ax,
        0.2,
        2.5,
        2.0,
        0.8,
        "Measurement world\nseed secret, embargoed",
        fill="#fdf5f1",
        dashed=True,
    )
    _box(ax, 2.9, 3.2, 1.5, 0.8, "Generator\nplants records,\nauthors the key", size=7.5)
    _box(ax, 4.9, 3.2, 1.4, 0.8, "Prose gate\nextractable facts\nonly", size=7.5)
    _box(ax, 6.8, 3.2, 1.5, 0.8, "Live systems\nHR, tracker,\ncalendar, corpus", size=7.5)
    for y in (4.3, 2.9):
        _arrow(ax, (2.2, y), (2.9, 3.6))
    _arrow(ax, (4.4, 3.6), (4.9, 3.6))
    _arrow(ax, (6.3, 3.6), (6.8, 3.6))
    # The validator reads the live systems back; a world is served on its verdict.
    _box(ax, 6.8, 1.7, 1.5, 0.8, "Validator\nown read-only role,\nreads them back", size=7.5)
    _arrow(ax, (7.55, 3.2), (7.55, 2.5))
    # The generator seals three artifacts for three readers.
    _box(ax, 2.9, 0.2, 1.4, 0.7, "World spec\nbenchmark only", size=7.5)
    _box(ax, 4.5, 0.2, 1.4, 0.7, "Scenario specs\nsystems may read", size=7.5)
    _box(ax, 6.1, 0.2, 1.6, 0.7, "Truth manifest\nevaluator only", edge="#b3261e", size=7.5)
    for x in (3.6, 5.2, 6.9):
        _arrow(ax, (3.65, 3.2), (x, 0.9))
    ax.text(
        5.3,
        -0.2,
        "sealed artifacts: create-only writes with recorded versions",
        ha="center",
        fontsize=7.5,
        color=MUTED,
    )
    # The systems under test read the live systems and the scenario specs, never the key;
    # the evaluator reads their exports against the key.
    _box(ax, 8.6, 1.7, 1.3, 0.8, "Systems\nunder test", size=7.5)
    _box(ax, 8.6, 0.2, 1.3, 0.7, "Evaluator", size=7.5)
    _arrow(ax, (9.25, 2.5), (8.3, 3.4))
    _arrow(ax, (8.6, 1.7), (5.2, 0.9))
    _arrow(ax, (7.7, 0.55), (8.6, 0.55))
    _arrow(ax, (9.25, 1.7), (9.25, 0.9))
    ax.text(
        8.45,
        1.02,
        "no capability over the truth manifest",
        ha="right",
        fontsize=6.5,
        color="#b3261e",
    )
    ax.text(
        0.2,
        1.9,
        "Validation precedes measurement:\na world is served only on a verdict\nunder the "
        "current validator version.",
        fontsize=7.5,
        color=INK,
        va="top",
    )
    fig.tight_layout()
    fig.savefig(out / "instrument.png")
    plt.close(fig)


def mint_all(out: Path) -> tuple[str, ...]:
    """Render every figure into ``out``; the names written, in order."""
    results = committed_results()
    out.mkdir(parents=True, exist_ok=True)
    draw_headline(results, out)
    draw_tiers(results, out)
    draw_mechanism(results, out)
    draw_cost_quality(results, out)
    draw_instrument(out)
    return ("headline.png", "tiers.png", "mechanism.png", "cost-quality.png", "instrument.png")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mint the report's figures.")
    parser.add_argument("--out", type=Path, default=OUT)
    arguments = parser.parse_args(argv)
    for name in mint_all(arguments.out):
        print(f"minted {arguments.out / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
