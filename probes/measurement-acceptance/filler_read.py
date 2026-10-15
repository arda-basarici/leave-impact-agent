"""The measurement world's filler read: five drawn filler documents read by another model family.

PROTOCOL ("How the measurement world is accepted") asks that the drawn filler documents be
read by a person or by a model of another family than the writer's, "checking that each
reads as the requirement it imitates and names nothing of the world"; the freeze's fork 16
set the reader to Nova Pro and the count to five, spot checks that establish no defect rate
over the pool. The two halves of that one question are answered by two different parties
on purpose: the model says whether the text reads as the requirement it presents itself as
and lists every proper name it finds, and this script compares the listed names with the
world's own lexicon (the organization's people, teams and components, the planted records'
titles, the vocabulary's clients) in code, so the model never sees the world's names and
its reading cannot be steered by them. Skills are vocabulary terms a filler brief carries by
construction, not world names, and are left out of the comparison.

The model answers through one forced tool, as the generator's checker does, so an answer
is a parsed object and never free text read by eye. Every answer, with the document's title
and the comparison's hits, goes to the git-ignored audit directory beside the draw; stdout
carries counts and the token usage, never a document's text or title. One call per
document at temperature 0, about five cents in all.

Usage: ``python probes/measurement-acceptance/filler_read.py <world_version>`` after the
draw, with ``AWS_PROFILE`` set to a principal that reads both buckets and may invoke the
reader on Bedrock.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import boto3

from leaveimpact.adapters.object_store.layout import document_key
from leaveimpact.adapters.object_store.s3 import S3ObjectReader
from leaveimpact.adapters.prose.bedrock import bedrock_client
from leaveimpact.core.anchors import SKILL_KIND, SurfaceForm
from leaveimpact.core.entities import Document
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world
from leaveimpact.world.briefs import lexicon_of
from leaveimpact.world.decoders import decode_document

REPOSITORY = Path(__file__).resolve().parents[2]
OUT_DIR = REPOSITORY / "data" / "audit"
REGION = "eu-central-1"
TRUTH_BUCKET = "leave-impact-truth-445743457479"
WORLD_BUCKET = "leave-impact-world-445743457479"

READER_MODEL = "eu.amazon.nova-pro-v1:0"
"""The checker's model: another family than the writer's (Haiku 4.5), as the protocol asks."""

SYSTEM = (
    "You are reading one internal document from a software organization's document "
    "store. Answer only by calling the tool you are given, with every field filled."
)
QUESTION = (
    "Read the document below. First: does it read as a genuine requirement text of the "
    "kind it presents itself as (for example a release requirement or a client requirement "
    "note), the way such a document would read inside a real organization? Second: list "
    "every proper name the text mentions, of any kind: persons, teams, components or "
    "products, releases, clients, tickets. List each name once, spelled exactly as the "
    "text spells it; list nothing the text does not contain."
)
TOOL: dict[str, Any] = {
    "toolSpec": {
        "name": "filler_reading",
        "description": "The reading of one document: whether it reads as the requirement "
        "it imitates, and every proper name it mentions.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "reads_as_requirement": {"type": "boolean"},
                    "reads_as": {
                        "type": "string",
                        "description": "the kind of document it reads as, in a few words",
                    },
                    "reason": {"type": "string", "description": "one sentence"},
                    "names": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["reads_as_requirement", "reads_as", "reason", "names"],
            }
        },
    }
}


def require_ignored(path: Path) -> None:
    """The answers carry titles of a sealed world: written where git ignores them, nowhere else."""
    done = subprocess.run(
        ["git", "-C", str(REPOSITORY), "check-ignore", "-q", str(path)],
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{path} is not git-ignored; the answers are private and stay unwritten")


def world_forms(world: SealedWorld) -> tuple[SurfaceForm, ...]:
    """Every name the world can be said to name, skills left out (the filler mint's own list)."""
    lexicon = lexicon_of(
        world.org,
        [p.entity for s in world.scenarios for p in s.owned.work_items],
        [p.entity for s in world.scenarios for p in s.owned.documents],
        [p.entity for s in world.scenarios for p in s.owned.events],
    )
    return tuple(form for form in lexicon.forms() if form.kind != SKILL_KIND)


def hits(names: list[str], forms: tuple[SurfaceForm, ...]) -> list[dict[str, str]]:
    """Each listed name that equals a world form, or contains one of two or more words."""
    found: list[dict[str, str]] = []
    for name in names:
        spelled = " ".join(name.casefold().split())
        for form in forms:
            form_text = " ".join(form.form.casefold().split())
            if spelled == form_text or (len(form_text.split()) >= 2 and form_text in spelled):
                found.append({"name": name, "kind": form.kind, "id": form.id, "form": form.form})
    return found


def document_text(document: Document) -> str:
    sections = "\n\n".join(section.text for section in document.sections)
    return f"Title: {document.title}\n\n{sections}"


def parse_answer(document_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    """The reader's answer with its two fields present and typed: ``names`` a list of
    strings and ``reads_as_requirement`` a boolean. A missing or mistyped field is a refusal
    naming the document, never a default, since an empty list would pass the world-hit
    count at zero with nothing read (the external read of the pre-dispatch commits,
    2026-10-16; the five saved answers re-validated the same day through ``--revalidate``)."""
    names = cast(object, raw.get("names"))
    if not isinstance(names, list) or not all(
        isinstance(name, str) for name in cast(list[object], names)
    ):
        raise RuntimeError(
            f"{document_id}: the answer holds no names list of strings; fields {sorted(raw)}"
        )
    if not isinstance(raw.get("reads_as_requirement"), bool):
        raise RuntimeError(
            f"{document_id}: the answer holds no boolean reads_as_requirement; fields {sorted(raw)}"
        )
    return raw


def revalidate(path: Path) -> int:
    """Every saved reading's answer through ``parse_answer``, no call made; the counts the
    run printed, printed again."""
    record = json.loads(path.read_text(encoding="utf-8"))
    for reading in record["readings"]:
        answer = parse_answer(reading["document_id"], reading["answer"])
        print(
            f"{reading['document_id']}: reads as requirement={answer['reads_as_requirement']}, "
            f"names listed={len(answer['names'])}, world hits={len(reading['world_hits'])}"
        )
    print(f"revalidated {len(record['readings'])} readings of {record['world_version'][:8]}")
    return 0


def read_one(client: Any, document: Document) -> tuple[dict[str, Any], dict[str, int]]:
    response = client.converse(
        modelId=READER_MODEL,
        system=[{"text": SYSTEM}],
        messages=[
            {"role": "user", "content": [{"text": f"{QUESTION}\n\n{document_text(document)}"}]}
        ],
        inferenceConfig={"temperature": 0.0, "maxTokens": 600},
        toolConfig={"tools": [TOOL], "toolChoice": {"any": {}}},
    )
    content = response["output"]["message"]["content"]
    uses = [block["toolUse"]["input"] for block in content if "toolUse" in block]
    if len(uses) != 1:
        raise RuntimeError(f"{document.id}: expected one tool call, the model made {len(uses)}")
    usage = response.get("usage", {})
    return cast(dict[str, Any], uses[0]), {
        "input_tokens": int(usage.get("inputTokens", 0)),
        "output_tokens": int(usage.get("outputTokens", 0)),
    }


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--revalidate":
        return revalidate(Path(sys.argv[2]))
    if len(sys.argv) != 2:
        print("usage: filler_read.py <world_version> | --revalidate <record>", file=sys.stderr)
        return 2
    version = WorldVersion(sys.argv[1])
    draw_path = OUT_DIR / f"acceptance_draw_{version[:8]}.json"
    out_path = OUT_DIR / f"filler_read_{version[:8]}.json"
    require_ignored(out_path)
    draw = json.loads(draw_path.read_text(encoding="utf-8"))
    if draw["world_version"] != version:
        raise RuntimeError(f"{draw_path} is the draw of another world")
    document_ids: list[str] = draw["filler"]["documents"]

    s3 = boto3.Session(region_name=REGION).client("s3")
    world_reader = S3ObjectReader(s3, WORLD_BUCKET)
    world = load_sealed_world(version, S3ObjectReader(s3, TRUTH_BUCKET), world_reader)
    forms = world_forms(world)
    client = bedrock_client(REGION)

    readings: list[dict[str, Any]] = []
    totals = {"input_tokens": 0, "output_tokens": 0}
    for document_id in document_ids:
        stored = world_reader.get(document_key(version, document_id))
        if stored is None:
            raise RuntimeError(f"{document_id} is not in the world bucket under {version[:8]}")
        document = decode_document(stored.content)
        answer, usage = read_one(client, document)
        answer = parse_answer(document_id, answer)
        found = hits(answer["names"], forms)
        readings.append(
            {
                "document_id": document_id,
                "title": document.title,
                "kind": document.kind.value,
                "sections": len(document.sections),
                "answer": answer,
                "world_hits": found,
                "usage": usage,
            }
        )
        for key in totals:
            totals[key] += usage[key]
        print(
            f"{document_id}: reads as requirement={answer['reads_as_requirement']}, "
            f"names listed={len(answer['names'])}, world hits={len(found)}"
        )
    record = {
        "world_version": version,
        "reader_model": READER_MODEL,
        "inference": {"temperature": 0.0, "max_tokens": 600},
        "question": QUESTION,
        "world_forms_compared": len(forms),
        "readings": readings,
        "usage": totals,
    }
    out_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    passing = sum(1 for r in readings if r["answer"].get("reads_as_requirement") is True)
    clean = sum(1 for r in readings if not r["world_hits"])
    print(
        f"{passing} of {len(readings)} read as the requirement they imitate; "
        f"{clean} of {len(readings)} name nothing of the world ({len(forms)} forms compared); "
        f"tokens in {totals['input_tokens']}, out {totals['output_tokens']}"
    )
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
