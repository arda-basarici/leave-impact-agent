"""The replay set's publish list: one `publish` operator command per finished run of the
plan, generated from the driver's ledger so no run id is ever typed (the step's fork 4).

The demo surface shows a replay only once an operator has published it, by the app's own
command on the host (`python -m leaveimpact.app publish --run R --attempt A --as P --by W`,
one `docker compose run` of the deployed image in a Session Manager session). The public
name is the scenario id with its underscore as a hyphen (`scenario_001` is `scenario-001`),
the publisher is `operator`, and the three introduced examples carry their title at the
publish, since a repeat with other content changes nothing; the titles come from a small
JSON file, public id to title, written after the local grading picks them.

The list refuses rather than guess: a key of the plan with no finished record, a finished
record that stopped the driver (an operator decides those by hand), an admission marker
that is not `run-<id>/<attempt>`, an admission whose scenario is not the key's, two rows
for one public name, a title naming no row. The preamble lines are the host's: the deploy
script's own way of exporting the database password and the deployed tag.

    uv run python probes/replay-set/publish_list.py [--plan-dir probes/replay-set] \
        [--titles titles.json]
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADMITTED = re.compile(r"^(run-\d+)/(\d+)$")
PUBLIC_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")  # the app's slug rule (app/public.py)
PUBLISHER = "operator"
PREAMBLE = (
    "cd /srv/app",
    "export APP_TAG=$(cat DEPLOYED)",
    "POSTGRES_PASSWORD=$(aws ssm get-parameter --region eu-central-1 --with-decryption "
    "--name /leave-agent/postgres-password --query Parameter.Value --output text); "
    "export POSTGRES_PASSWORD",
)


class Refused(Exception):
    """The list cannot be written from this ledger; the message says why."""


def finished_by_key(records: list[dict]) -> dict[str, dict]:
    """Each key's standing finished record: a `released` line clears it, as the driver's fold
    does, so a key sent again reads from its later run."""
    standing: dict[str, dict] = {}
    for record in records:
        if record["kind"] == "released":
            standing.pop(record["key"], None)
        elif record["kind"] == "finished":
            standing[record["key"]] = record
    return standing


def public_id_of(scenario_id: str) -> str:
    public_id = scenario_id.replace("_", "-")
    if not PUBLIC_ID.match(public_id):
        raise Refused(f"{scenario_id} gives no public name under the app's slug rule")
    return public_id


def rows_of(order: list[str], records: list[dict], titles: dict[str, str]) -> list[dict]:
    """One row per key of ``order``: the run, the attempt, the public name and the title if
    any, or a refusal naming the first key that cannot be published."""
    standing = finished_by_key(records)
    rows: list[dict] = []
    seen: dict[str, str] = {}
    for key in order:
        finished = standing.get(key)
        if finished is None:
            raise Refused(f"{key} has no finished record; the plan is not complete")
        if finished["stop_reasons"]:
            raise Refused(
                f"{key} run {finished['run_id']} stopped the driver "
                f"({'; '.join(finished['stop_reasons'])}); an operator decides it by hand, "
                "outside this list"
            )
        markers = finished["markers"]
        admitted = ADMITTED.match(str(markers.get("launch.admitted") or ""))
        if admitted is None:
            raise Refused(
                f"{key} run {finished['run_id']} has no admission marker of the form "
                "run-<id>/<attempt>"
            )
        scenario = key.rsplit("/", 1)[1]
        if markers.get("launch.scenario") != scenario:
            raise Refused(
                f"{key} run {finished['run_id']} admitted {markers.get('launch.scenario')!r}, "
                "not the key's scenario"
            )
        public_id = public_id_of(scenario)
        if public_id in seen:
            raise Refused(f"{public_id} would name both {seen[public_id]} and {key}")
        seen[public_id] = key
        rows.append(
            {
                "key": key,
                "run_id": admitted.group(1),
                "attempt": int(admitted.group(2)),
                "public_id": public_id,
                "title": titles.get(public_id),
            }
        )
    unknown = sorted(set(titles) - set(seen))
    if unknown:
        raise Refused(f"titles name no row: {', '.join(unknown)}")
    return rows


def command_of(row: dict) -> str:
    line = (
        "docker compose run --rm app python -m leaveimpact.app publish "
        f"--run {row['run_id']} --attempt {row['attempt']} --as {row['public_id']} --by {PUBLISHER}"
    )
    if row["title"] is not None:
        line += f" --title {shlex.quote(row['title'])}"
    return line


def publish_list(order: list[str], records: list[dict], titles: dict[str, str]) -> list[str]:
    rows = rows_of(order, records, titles)
    return [*PREAMBLE, *(command_of(row) for row in rows)]


def read_json_lines(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="the replay set's publish list, from the driver's ledger"
    )
    parser.add_argument(
        "--plan-dir", type=Path, default=HERE, help="the plan directory; this file's own"
    )
    parser.add_argument(
        "--titles", type=Path, default=None, help="a JSON object, public id to title"
    )
    args = parser.parse_args(argv)
    plan = json.loads((args.plan_dir / "plan.json").read_text(encoding="utf-8"))
    records = read_json_lines(args.plan_dir / "ledger.jsonl")
    titles = json.loads(args.titles.read_text(encoding="utf-8")) if args.titles else {}
    try:
        for line in publish_list(plan["order"], records, titles):
            print(line)
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
