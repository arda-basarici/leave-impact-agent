"""Where the one-call rounds' ``false`` emissions sit, by the document their carrier belongs
to: a section of a filler document, a section of a scenario-owned document, or a comment.

The evaluator's ``false`` class is a statement the sealed world holds no fact for, in prose
or in a record. A filler section is sealed with no fact under it by construction (its brief
requires none and allows none), while its text does assert requirements about declared
fictional entities, so a reader that states what a shown filler section says is counted
``false`` for an accurate read. This probe tells that population from the rest by the
carrier alone: the sealed world's index gives each section's document, and the sealed
filler pool says which documents are filler. It does not verify that the filler text asserts
the statement, since filler briefs permit by subject and enumerate no statements; the one
example printed is read by eye. The split is the first reading the baselines step's close
recorded for the freeze's reporting design; the class itself is ruled there.

Reads each round's capture details outside the tree
(``LEAVE_IMPACT_SPIKE_CAPTURES/prompt-check/one-call-<system>/<scenario>.detail.json``, the
live probe's output, which holds every emission's class and the stated fact's repr) and the
first development world; writes ``results/false_by_carrier.md``. The counts cited by the
FINDINGS entry ``one-call`` are this script's.

    PYTHONPATH=. LEAVE_IMPACT_SPIKE_CAPTURES=<dir> \
        uv run python probes/prompt-check/false_by_carrier.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import development_world as dw  # noqa: E402

from leaveimpact.core.entities import DocumentSection  # noqa: E402
from leaveimpact.core.enums import EntityKind  # noqa: E402
from leaveimpact.core.refs import EntityRef  # noqa: E402
from leaveimpact.evaluator.sealed_world import SealedWorld  # noqa: E402

RESULT = HERE / "results" / "false_by_carrier.md"
ROUNDS = ("one-call-single-shot", "one-call-full-context")
# The capture detail records the stated fact as its repr; the carrier and the predicate are
# read back from it, since the detail holds no structured copy.
CARRIER = re.compile(r"carrier=EntityRef\(kind=<EntityKind\.(\w+): '(\w+)'>, id='([^']+)'\)")
PREDICATE = re.compile(r"predicate=<PredicateName\.\w+: '(\w+)'>")
QUOTE = re.compile(r"quote='([^']*)'")


def captures_root(env: dict[str, str]) -> Path:
    value = env.get("LEAVE_IMPACT_SPIKE_CAPTURES", "")
    if not value:
        raise SystemExit("LEAVE_IMPACT_SPIKE_CAPTURES names a directory outside the repository")
    root = Path(value).resolve()
    if root == dw.REPOSITORY or dw.REPOSITORY in root.parents:
        raise SystemExit("the capture directory must lie outside the repository")
    return root / "prompt-check"


def placement(world: SealedWorld, carrier: EntityRef) -> str:
    """``filler``, ``owned`` or ``comment`` for a carrier the world sealed; the kind's name
    for one it did not."""
    part = world.index.parts.get(carrier)
    if part is None:
        return f"unsealed-{carrier.kind.value}"
    if isinstance(part.content, DocumentSection):
        return "filler" if part.parent in world.filler else "owned"
    return "comment"


def false_emissions(detail: Path) -> list[str]:
    data = json.loads(detail.read_text(encoding="utf-8"))
    return [str(e["fact"]) for e in data["emissions"] if e["class"] == "false"]


def carrier_of(fact: str) -> EntityRef:
    match = CARRIER.search(fact)
    if match is None:
        raise ValueError(f"no carrier in the recorded fact: {fact[:120]}")
    return EntityRef(EntityKind(match.group(2)), match.group(3))


def main() -> int:
    captures = captures_root(dict(os.environ))
    world = dw.development_world()
    lines = [
        "# The one-call rounds' `false` emissions by carrier",
        "",
        f"World `{dw.WORLD[:12]}…`, the two live rounds' capture details, read by "
        "`false_by_carrier.py`. A cell is `predicate/placement: count`, placement by the "
        "carrier's document in the sealed filler pool (`filler`), among the scenario-owned "
        "documents (`owned`), or a comment.",
        "",
    ]
    example: tuple[str, str, str] | None = None
    for round_name in ROUNDS:
        details = sorted((captures / round_name).glob("*.detail.json"))
        if not details:
            raise SystemExit(f"no capture details under {captures / round_name}")
        lines += [f"## {round_name}", "", "| scenario | false emissions |", "|---|---|"]
        total: Counter[str] = Counter()
        for detail in details:
            cells: Counter[str] = Counter()
            for fact in false_emissions(detail):
                carrier = carrier_of(fact)
                where = placement(world, carrier)
                predicate = PREDICATE.search(fact)
                cells[f"{predicate.group(1) if predicate else '?'}/{where}"] += 1
                if example is None and where == "filler":
                    quote = QUOTE.search(fact)
                    section = world.index.parts[carrier].content
                    assert isinstance(section, DocumentSection)
                    example = (carrier.id, quote.group(1) if quote else "?", section.text)
            total.update(cells)
            scenario = detail.name.split(".")[0]
            lines.append(f"| {scenario} | {_cells(cells)} |")
        lines += [f"| **total** | **{_cells(total)}** |", ""]
    if example is not None:
        clause, quote, text = example
        lines += [
            "## One filler example, read by eye",
            "",
            f"`{clause}`, quoted: {quote}",
            "",
            f"The sealed section: {text}",
            "",
        ]
    RESULT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


def _cells(cells: Counter[str]) -> str:
    return ", ".join(f"{key}: {count}" for key, count in sorted(cells.items())) or "none"


if __name__ == "__main__":
    raise SystemExit(main())
