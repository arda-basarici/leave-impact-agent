"""The cross-round table of the prompt check, generated from the stage rows every round's
result file holds, so the FINDINGS entry's counts are read and never retyped.

A round's result file (``results/<round>-<stamp>.json``) carries, per scenario, one row per
needed target with the four stages the evaluator's fact stages reached (returned, emitted,
admitted, usable); a target is a section's unless it is a has_skill target of a scenario
whose needed skill fact a comment carries (``scenario_013`` and ``scenario_018``, the
forecast's split). Writes ``results/summary.md``.

    uv run python probes/prompt-check/summary.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
ORDER = ("shipped", "search-by-names", "search-plan", "search-once", "closed-list")
COMMENT_TARGETS = {("scenario_013", "has_skill"), ("scenario_018", "has_skill")}
STAGES = ("returned", "emitted", "admitted", "usable")


def latest_files() -> dict[str, Path]:
    """The newest result file of each round that is not a dry one."""
    found: dict[str, Path] = {}
    for path in sorted(RESULTS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data["dry"]:
            found[data["round"]] = path
    return found


def stage_counts(results: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    """The section targets' and all targets' stage sums with their counts, per round."""
    section = [0, 0, 0, 0, 0]
    every = [0, 0, 0, 0, 0]
    for result in results:
        scenario = str(result["scenario_id"])
        targets = cast("list[dict[str, Any]]", result["targets"])
        for target in targets:
            is_section = (scenario, str(target["predicate"])) not in COMMENT_TARGETS
            for sums in (section, every) if is_section else (every,):
                for i, stage in enumerate(STAGES):
                    sums[i] += int(bool(target[stage]))
                sums[4] += 1
    return section, every


def main() -> int:
    files = latest_files()
    lines = [
        "# The prompt check's rounds, from the result files",
        "",
        "| round | system digest | calls (the seven) | section targets returned / emitted / "
        "admitted / usable of n | all targets, the same | runs at the cap | cost (USD) |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in ORDER:
        if name not in files:
            continue
        data = json.loads(files[name].read_text(encoding="utf-8"))
        results = cast("list[dict[str, Any]]", data["results"])
        section, every = stage_counts(results)
        calls = ", ".join(str(r["logical_calls"]) for r in results)
        at_cap = sum(1 for r in results if r["logical_calls"] >= 19)
        cost = sum(r["account_pico_usd"] or 0 for r in results) / 1e12
        lines.append(
            f"| {name} | `{data['prompt_digests']['system'][:8]}` | {calls} | "
            f"{section[0]} / {section[1]} / {section[2]} / {section[3]} of {section[4]} | "
            f"{every[0]} / {every[1]} / {every[2]} / {every[3]} of {every[4]} | {at_cap} | "
            f"{cost:.2f} |"
        )
    text = "\n".join(lines) + "\n"
    (RESULTS / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
