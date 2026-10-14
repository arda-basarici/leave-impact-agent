"""The caps replay of the freeze step (fork 4): the per-system caps derived by the ruled rule
from the calibration rounds' exports, and every calibration history replayed through the
account check under those caps, model-free, so the freeze registers caps no calibration run
would have been stopped by, with the replay's own findings beside the numbers.

The rule (the step-15 forks file, fork 4, ruled as proposed): per system, the call cap is
twice the largest completed calibration run's call count and at least 8; the token cap is
twice the largest completed run's counted tokens, rounded up to a multiple of 10,000; the
finalization reserve stays 2 calls and 20,000 tokens; full context's token cap is the
context allowance less the output maximum (the step-12 ruling), so the cap path is the one
a too-large level reaches. The counts are read off each run's own account under the caps it
ran with, through the evaluator's check and nothing else, since that is the account the
registered caps will be held against.

The replay substitutes the candidate caps into each export's record and runs the account
check again. A finding of the kind "intent not authorized" or "tokens above cap" under the
candidate caps names a calibration run the caps would have stopped; the control replay
under the as-run caps shows the check's findings that have nothing to do with the caps, and
a second control under caps of half each system's largest count must stop runs, or the
replay is not reading the caps at all (the lesson that a check's first test is the real
producer's output). The three columns are read against each other.

    PYTHONPATH=. uv run python probes/prompt-check/caps_replay.py \\
        --captures <LEAVE_IMPACT_SPIKE_CAPTURES>/prompt-check \\
        --rounds calibration-agent-base,calibration-agent-padded_40k,...

The exports are read from the capture directory, outside the tree; the table lands beside
this file as ``results/caps-replay-<stamp>.md`` with ids, counts and the derived caps alone.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import development_world as dw  # noqa: E402

from leaveimpact.core.run_export_json import decode_export_bytes  # noqa: E402
from leaveimpact.core.run_record import Caps, SystemKind  # noqa: E402
from leaveimpact.evaluator.account_check import AccountFindingKind, check_account  # noqa: E402

RESULTS = HERE / "results"
MINIMUM_CALL_CAP = 8
TOKEN_ROUNDING = 10_000
FINALIZATION_CALL_RESERVE = 2
FINALIZATION_TOKEN_RESERVE = 20_000
CAP_FINDINGS = frozenset(
    {AccountFindingKind.INTENT_NOT_AUTHORIZED, AccountFindingKind.TOKENS_ABOVE_CAP}
)


@dataclass(frozen=True)
class RunReading:
    """One calibration run as its own account holds it."""

    round_name: str
    scenario: str
    world: str
    system: SystemKind
    calls: int
    tokens: int
    as_run_findings: tuple[str, ...]


def read_runs(captures: Path, rounds: list[str]) -> list[tuple[RunReading, bytes]]:
    runs: list[tuple[RunReading, bytes]] = []
    for round_name in rounds:
        for path in sorted((captures / round_name).glob("*.export.json")):
            content = path.read_bytes()
            export = decode_export_bytes(content)
            check = check_account(export)
            if check is None:
                raise SystemExit(f"{path} holds no reservation; the replay reads admitted runs")
            runs.append(
                (
                    RunReading(
                        round_name,
                        path.name.split(".")[0],
                        str(export.context.world_version),
                        export.record.system.kind,
                        check.calls,
                        check.tokens,
                        tuple(f.kind.value for f in check.findings),
                    ),
                    content,
                )
            )
    return runs


def derived_caps(system: SystemKind, readings: list[RunReading], template: Caps) -> Caps:
    """The caps fork 4's rule gives ``system`` from its ``readings``, on ``template``'s
    counting rule and input bound."""
    largest_calls = max(r.calls for r in readings)
    largest_tokens = max(r.tokens for r in readings)
    call_cap = max(2 * largest_calls, MINIMUM_CALL_CAP)
    if system is SystemKind.FULL_CONTEXT:
        token_cap = dw.CONTEXT_ALLOWANCE - dw.OUTPUT_MAXIMUM
    else:
        token_cap = math.ceil(2 * largest_tokens / TOKEN_ROUNDING) * TOKEN_ROUNDING
    return Caps(
        call_cap,
        token_cap,
        FINALIZATION_CALL_RESERVE,
        FINALIZATION_TOKEN_RESERVE,
        template.counting_rule,
        template.input_bound,
    )


def halved_caps(readings: list[RunReading], template: Caps) -> Caps:
    """The control: caps at half the largest count, which must stop that run."""
    return Caps(
        max(max(r.calls for r in readings) // 2, 1),
        max(max(r.tokens for r in readings) // 2, 1),
        0,
        0,
        template.counting_rule,
        template.input_bound,
    )


def replay(content: bytes, caps: Caps) -> tuple[str, ...]:
    export = decode_export_bytes(content)
    substituted = replace(export, record=replace(export.record, caps=caps))
    check = check_account(substituted)
    assert check is not None
    return tuple(f.kind.value for f in check.findings)


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--captures", required=True, help="the prompt-check capture directory")
    parser.add_argument("--rounds", required=True, help="comma-separated round names")
    args = parser.parse_args()
    captures = Path(str(args.captures)).resolve()
    if captures == dw.REPOSITORY or dw.REPOSITORY in captures.parents:
        raise SystemExit("the capture directory must lie outside the repository")
    rounds = [r.strip() for r in str(args.rounds).split(",") if r.strip()]
    runs = read_runs(captures, rounds)

    by_system: dict[SystemKind, list[RunReading]] = {}
    for reading, _ in runs:
        by_system.setdefault(reading.system, []).append(reading)
    templates = {
        reading.system: decode_export_bytes(content).record.caps for reading, content in runs
    }
    candidates = {
        system: derived_caps(system, readings, templates[system])
        for system, readings in by_system.items()
    }
    controls = {
        system: halved_caps(readings, templates[system]) for system, readings in by_system.items()
    }
    worlds = sorted({reading.world for reading, _ in runs})

    lines = [
        "# The caps replay (step 15, fork 4)",
        "",
        f"World(s) the exports name: {', '.join(f'`{w[:8]}…`' for w in worlds)}. "
        f"Rounds: {', '.join(rounds)}.",
        "",
        "## The caps the rule derives",
        "",
        "| system | runs | largest calls | largest counted tokens | call cap | token cap | "
        "reserves (calls, tokens) |",
        "|---|---|---|---|---|---|---|",
    ]
    for system, readings in by_system.items():
        caps = candidates[system]
        lines.append(
            f"| {system.value} | {len(readings)} | {max(r.calls for r in readings)} | "
            f"{max(r.tokens for r in readings):,} | {caps.call_cap} | {caps.token_cap:,} | "
            f"{caps.finalization_call_reserve}, {caps.finalization_token_reserve:,} |"
        )
    lines += [
        "",
        "## Every calibration history under the candidate caps",
        "",
        "| round | scenario | calls | counted tokens | findings as run | findings under the "
        "candidate caps | stopped by the caps | stopped under halved caps (control) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    stopped = 0
    control_stopped = 0
    for reading, content in runs:
        under = replay(content, candidates[reading.system])
        cap_bound = [kind for kind in under if AccountFindingKind(kind) in CAP_FINDINGS]
        stopped += bool(cap_bound)
        control = replay(content, controls[reading.system])
        control_bound = [kind for kind in control if AccountFindingKind(kind) in CAP_FINDINGS]
        control_stopped += bool(control_bound)
        lines.append(
            f"| {reading.round_name} | {reading.scenario} | {reading.calls} | "
            f"{reading.tokens:,} | {dict(Counter(reading.as_run_findings)) or 'none'} | "
            f"{dict(Counter(under)) or 'none'} | {'yes' if cap_bound else 'no'} | "
            f"{'yes' if control_bound else 'no'} |"
        )
    lines += [
        "",
        f"Runs replayed: {len(runs)}; stopped by the candidate caps: {stopped}; stopped under "
        f"the halved control caps: {control_stopped}.",
        "",
    ]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"caps-replay-{stamp}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
