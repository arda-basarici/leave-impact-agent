"""The correct-whole verdict of every prompt-check run, read back from the captured exports
with the real evaluator and no model call: the one check the probe's reduction did not
carry (the FIXLOG of session 88, closed at the step's close).

The probe's result files reduce the oracle's plan findings and the report findings; the
row match that decides correct whole lives in the evaluation's claim rows, and no summary
showed it, so two runs differing in their plan findings could not be told apart on the
check the preregistration reads first. This script walks the capture directory
(``LEAVE_IMPACT_SPIKE_CAPTURES/prompt-check/<round>/<scenario>.export.json``), evaluates
each export against the development world under the probe's configuration, as the probe
did when it wrote the export, and writes ``results/verdicts.md``: one row per round in the
summary's order, the verdict per scenario and the count correct whole of the runs. Dry
rounds have no captures and are skipped. From the close on, the live probe records the
verdict in its result files too (``live_probe.reduce``); this script is how the fifteen
rounds already in the record got theirs.

    LEAVE_IMPACT_SPIKE_CAPTURES=<dir> uv run python probes/prompt-check/verdicts.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import development_world as dw  # noqa: E402
from summary import ORDER  # noqa: E402

from leaveimpact.core.run_export import RunExport  # noqa: E402
from leaveimpact.core.run_export_json import decode_export_bytes  # noqa: E402
from leaveimpact.core.run_timing import TreeState  # noqa: E402
from leaveimpact.evaluator.grading import Graded, correct_whole  # noqa: E402
from leaveimpact.evaluator.sealed_world import SealedWorld  # noqa: E402
from leaveimpact.evaluator.trace_metrics import evaluate_run  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CAPTURES = "LEAVE_IMPACT_SPIKE_CAPTURES"


def captures_root(env: dict[str, str]) -> Path:
    """The prompt check's capture directory, outside the tree, from the environment."""
    value = env.get(CAPTURES)
    if not value:
        raise SystemExit(f"set {CAPTURES} to the capture directory the probe wrote under")
    return Path(value) / "prompt-check"


def verdict_of(
    world: SealedWorld, export: RunExport, configuration: dw.ProbeConfiguration
) -> bool | None:
    """Whether the run ``export`` records is correct whole against ``world``; ``None`` when
    the evaluator did not grade it."""
    evaluation = evaluate_run(
        world,
        export,
        table=configuration.rules.table,
        redispatch=configuration.rules.redispatch,
        retry=configuration.worker.retry,
        counting_identifiers=dict(configuration.worker.counting_identifiers),
    )
    outcome = evaluation.outcome
    return correct_whole(outcome) if isinstance(outcome, Graded) else None


def cell(verdict: bool | None) -> str:
    if verdict is None:
        return "-"
    return "yes" if verdict else "no"


def main() -> int:
    world = dw.development_world()
    configuration = dw.probe_configuration(tree_state=TreeState.CLEAN)
    root = captures_root(dict(os.environ))
    rows: list[tuple[str, dict[str, bool | None]]] = []
    for name in ORDER:
        directory = root / name
        if not directory.is_dir():
            continue
        verdicts: dict[str, bool | None] = {}
        for path in sorted(directory.glob("*.export.json")):
            scenario = path.name.split(".")[0]
            export = decode_export_bytes(path.read_bytes())
            verdicts[scenario] = verdict_of(world, export, configuration)
        rows.append((name, verdicts))
    scenarios = sorted({scenario for _, verdicts in rows for scenario in verdicts})
    lines = [
        "# The correct-whole verdict of every prompt-check run, from the captured exports",
        "",
        "Read back by `verdicts.py` with the real evaluator over the exports the probe captured;"
        " a run's verdict is the preregistration's first check, whether its report is correct"
        " in every part against the expected answer. `yes`, `no`, or `-` for a run the"
        " evaluator did not grade. The structured scenarios (009, 010) rest on the prefetch"
        " alone, so their verdict says nothing of the prompt; the seventh run (014) is the"
        " chain check's.",
        "",
        "| round | " + " | ".join(scenarios) + " | correct whole of n |",
        "|---|" + "---|" * (len(scenarios) + 1),
    ]
    for name, verdicts in rows:
        cells = [cell(verdicts.get(scenario)) for scenario in scenarios]
        correct = sum(1 for verdict in verdicts.values() if verdict is True)
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {correct} of {len(verdicts)} |")
    text = "\n".join(lines) + "\n"
    (RESULTS / "verdicts.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
