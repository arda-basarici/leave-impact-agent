"""The provider's token-counting call against what inference reported for the same request.

The ledger authorizes a model call on a bound of its input tokens. One candidate is to ask
the provider: ``CountTokens`` takes the Converse request's messages, system prompt and tool
configuration and answers with a number, before any inference. Whether that is usable here
is three questions nobody had checked: whether the call is served for the models the
harness uses, under their ``eu.`` inference profiles or only under the base model ids;
whether its count is at or above the input inference then reports; and whether that holds
on a request the size of the full-context system's.

The acceptance spike already holds requests as sent and the usage each reported. Every
distinct captured body that reported usage is replayed through the counting call, under the
family's profile id and its base model id, and the count is printed beside the reported
total input (input, cache read and cache write summed). No inference is repeated for those.
The spike's requests end near 37,000 bytes, so one large request is built from a text file
(``--large-text``, a JSON list of documents with ``sections``), counted, and with
``--send-large`` sent once to the Haiku profile with an output limit of 16 tokens. That one
send is the probe's only inference and its only known cost.

    LEAVE_IMPACT_SPIKE_CAPTURES=<dir> AWS_PROFILE=<profile> \\
        python probes/input-bound/count_tokens.py [--large-text <file> [--send-large]]

Each call's request identity, answer or error goes to a JSON-lines file under the capture
directory, outside the repository; this prints numbers and error codes only, never a
request or a response body. Retries are off: one call is one request. The probe runs under
whatever principal the profile names, so it says nothing of a deployed role's grant, and it
cannot show whether the counting call is billed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

CAPTURES_VARIABLE = "LEAVE_IMPACT_SPIKE_CAPTURES"
REPOSITORY = Path(__file__).resolve().parents[2]
REGION = "eu-central-1"
INPUT_COUNTERS = ("inputTokens", "cacheReadInputTokens", "cacheWriteInputTokens")
CONVERSE_INPUT_KEYS = ("messages", "system", "toolConfig", "additionalModelRequestFields")

IDENTIFIERS = {
    "haiku": (
        "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "anthropic.claude-haiku-4-5-20251001-v1:0",
    ),
    "nova": ("eu.amazon.nova-pro-v1:0", "amazon.nova-pro-v1:0"),
}
"""Per family, the inference profile the harness addresses and the base model behind it."""

LARGE_CHARACTERS = 520_000
LARGE_BODY_CEILING = 800_000
LARGE_OUTPUT_LIMIT = 16
COUNT_CALLS_CEILING = 150


def family_of(model: str) -> str:
    """The model family a profile id names.

    >>> family_of("eu.amazon.nova-pro-v1:0")
    'nova'
    """
    return "haiku" if "anthropic" in model else "nova"


def converse_input(body: dict[str, Any]) -> dict[str, Any]:
    """The part of a Converse request body the counting call takes.

    >>> converse_input({"messages": [], "inferenceConfig": {"maxTokens": 1}})
    {'messages': []}
    """
    return {key: body[key] for key in CONVERSE_INPUT_KEYS if key in body}


def total_input(usage: dict[str, Any]) -> int:
    """The input-side counters a usage object carries, summed.

    >>> total_input({"inputTokens": 10, "cacheReadInputTokens": 5, "outputTokens": 3})
    15
    """
    return sum(usage[name] for name in INPUT_COUNTERS if name in usage)


def captured_bodies(root: Path) -> dict[tuple[str, str], tuple[Path, int, set[int]]]:
    """Each distinct body a family was sent and reported usage for: by family and body digest,
    one request file, the body's bytes, and every total input the sends of it reported."""
    record = [
        json.loads(line)
        for line in (root / "sends.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    outcomes = {line["send"]: line for line in record if line["event"] == "outcome"}
    held: dict[tuple[str, str], tuple[Path, int, set[int]]] = {}
    reported: dict[tuple[str, str], set[int]] = defaultdict(set)
    for line in record:
        if line["event"] != "send" or line.get("offline"):
            continue
        usage = (outcomes.get(line["send"]) or {}).get("usage")
        if not isinstance(usage, dict) or "inputTokens" not in usage:
            continue
        key = (family_of(line["requested_model"]), line["body_sha256"])
        reported[key].add(total_input(usage))
        file = root / line["execution"] / f"{line['send']}.request.json"
        held.setdefault(key, (file, line["body_bytes"], reported[key]))
    return held


def large_request(text_file: Path) -> dict[str, Any]:
    """One Converse request holding about ``LARGE_CHARACTERS`` of the file's section text."""
    documents = json.loads(text_file.read_text(encoding="utf-8"))
    parts: list[str] = []
    used = 0
    for document in documents:
        for section in document["sections"]:
            if used >= LARGE_CHARACTERS:
                break
            parts.append(str(section))
            used += len(str(section))
    return {
        "system": [{"text": "Answer with the single word: ok"}],
        "messages": [{"role": "user", "content": [{"text": "\n\n".join(parts)}]}],
        "inferenceConfig": {"maxTokens": LARGE_OUTPUT_LIMIT, "temperature": 0},
    }


class Probe:
    """The probe's client and its record: state with a lifecycle, the calls made so far."""

    def __init__(self, root: Path) -> None:
        self.execution = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
        directory = root / "count-tokens"
        directory.mkdir(parents=True, exist_ok=True)
        self.record = directory / f"{self.execution}.jsonl"
        configuration = Config(
            retries={"mode": "standard", "total_max_attempts": 1},
            read_timeout=120,
            connect_timeout=10,
        )
        self.client = boto3.Session(region_name=REGION).client(
            "bedrock-runtime", config=configuration
        )
        self.count_calls = 0

    def _write(self, line: dict[str, Any]) -> None:
        with self.record.open("a", encoding="utf-8") as record:
            record.write(json.dumps(line, ensure_ascii=False) + "\n")

    def count(self, identifier: str, body: dict[str, Any], label: str) -> int | str:
        """The counting call's answer for ``body`` under ``identifier``, or its error code."""
        if self.count_calls >= COUNT_CALLS_CEILING:
            raise SystemExit(f"{COUNT_CALLS_CEILING} counting calls in one execution; stopping")
        self.count_calls += 1
        line: dict[str, Any] = {
            "event": "count",
            "label": label,
            "identifier": identifier,
            "at": datetime.now(UTC).isoformat(),
        }
        try:
            answer = self.client.count_tokens(
                modelId=identifier, input={"converse": converse_input(body)}
            )
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", type(error).__name__))
            line |= {"error": code, "message": str(error.response.get("Error", {}).get("Message"))}
            line["request_id"] = error.response.get("ResponseMetadata", {}).get("RequestId")
            self._write(line)
            return code
        line |= {
            "inputTokens": answer["inputTokens"],
            "request_id": answer.get("ResponseMetadata", {}).get("RequestId"),
        }
        self._write(line)
        return int(answer["inputTokens"])

    def send(self, identifier: str, body: dict[str, Any], label: str) -> dict[str, Any] | str:
        """One inference send of ``body``; its raw usage, or the error code."""
        line: dict[str, Any] = {
            "event": "send",
            "label": label,
            "identifier": identifier,
            "at": datetime.now(UTC).isoformat(),
        }
        try:
            answer = self.client.converse(modelId=identifier, **body)
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", type(error).__name__))
            line |= {"error": code, "message": str(error.response.get("Error", {}).get("Message"))}
            self._write(line)
            return code
        line |= {
            "usage": answer.get("usage"),
            "request_id": answer.get("ResponseMetadata", {}).get("RequestId"),
        }
        self._write(line)
        return dict(answer.get("usage") or {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--large-text", type=Path)
    parser.add_argument("--send-large", action="store_true")
    arguments = parser.parse_args()
    named = os.environ.get(CAPTURES_VARIABLE, "").strip()
    if not named:
        raise SystemExit(f"{CAPTURES_VARIABLE} names the private capture directory; it is unset")
    root = Path(named).resolve()
    if root == REPOSITORY or REPOSITORY in root.parents:
        raise SystemExit(f"captures are held outside the repository; {root} resolves inside it")

    probe = Probe(root)
    print(f"execution {probe.execution}, region {REGION}\n")
    print("family  bytes  reported input   count by profile   count by base id   body")
    served: dict[str, bool] = {}
    bodies = captured_bodies(root)
    for (family, digest), (file, size, reported) in sorted(
        bodies.items(), key=lambda item: (item[0][0], item[1][1], item[0][1])
    ):
        body = json.loads(file.read_bytes())
        answers: list[int | str] = []
        for identifier in IDENTIFIERS[family]:
            # An identifier the service refused once is not asked again: the refusal is the
            # finding, and forty repeats of it would add nothing.
            if served.get(identifier) is False:
                answers.append("not asked")
                continue
            answer = probe.count(identifier, body, f"{family} {digest[:12]}")
            served.setdefault(identifier, isinstance(answer, int))
            answers.append(answer)
        low, high = min(reported), max(reported)
        shown = str(low) if low == high else f"{low}..{high}"
        print(
            f"{family:<6} {size:>6}  {shown:>14}   {answers[0]!s:>16}   {answers[1]!s:>16}   "
            f"{digest[:12]}"
        )

    if arguments.large_text is not None:
        body = large_request(arguments.large_text)
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if len(encoded) > LARGE_BODY_CEILING:
            raise SystemExit(f"the large request is {len(encoded)} bytes, over the ceiling")
        digest = hashlib.sha256(encoded).hexdigest()
        print(f"\nthe large request: about {len(encoded)} bytes as JSON, digest {digest[:12]}")
        for identifiers in IDENTIFIERS.values():
            for identifier in identifiers:
                answer = probe.count(identifier, body, f"large {digest[:12]}")
                print(f"  count  {identifier:<46} {answer}")
        if arguments.send_large:
            usage = probe.send(IDENTIFIERS["haiku"][0], body, f"large {digest[:12]}")
            if isinstance(usage, str):
                print(f"  send   {IDENTIFIERS['haiku'][0]:<46} error {usage}")
            else:
                print(
                    f"  send   {IDENTIFIERS['haiku'][0]:<46} total input {total_input(usage)}, "
                    f"raw usage {json.dumps(usage, sort_keys=True)}"
                )
    print(f"\n{probe.count_calls} counting calls; the record is {probe.record.name}")


if __name__ == "__main__":
    main()
