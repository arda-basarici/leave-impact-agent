"""Scrub a captured Converse response into a fixture the tree may hold: what the parse reads
is kept, the scenario's content is not.

Captures hold model requests and responses and live outside the repository (the acceptance
spike's rule), since a response quotes the world's names and ids. The parse protocol
(``agent/answer_parse.py``) reads a response's shape and not its prose: the content blocks
in order and by kind, a ``toolUse`` block's id, name and the object-ness and keys of its
input, a text block's first non-blank character, the stop reason, the usage. The scrub keeps
exactly that. A prose text block becomes ``[text n]``; a text block opening with ``{`` keeps
its JSON structure with every string value replaced by a placeholder and every number by
zero, so the fact parser's reading of its shape survives; a ``toolUse`` input keeps its keys
with the values replaced the same way. The provider's tool-use ids are opaque and kept; the
tool names are the harness's and kept; ``metrics`` and ``usage`` are numbers and kept.

    python probes/parse_protocol/scrub.py <captured response> <fixture path>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def placeholder(value: Any) -> Any:
    """``value`` with its content removed and its JSON shape kept."""
    if isinstance(value, str):
        return "x"
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return 0
    if isinstance(value, list):
        return [placeholder(item) for item in value]  # type: ignore[union-attr]
    if isinstance(value, dict):
        return {str(key): placeholder(item) for key, item in value.items()}  # type: ignore[union-attr]
    raise TypeError(f"a JSON value, got {type(value).__name__}")


def scrub_text(text: str, ordinal: int) -> str:
    """A fact payload keeps its structure with placeholders; any other text is a label."""
    if text.lstrip().startswith("{"):
        try:
            return json.dumps(placeholder(json.loads(text)), sort_keys=True)
        except ValueError:
            return "{" + f'"malformed": "[text {ordinal}]"'
    return f"[text {ordinal}]"


def scrub(response: dict[str, Any]) -> dict[str, Any]:
    """The response with its content scrubbed; see the module."""
    content: list[dict[str, Any]] = []
    for ordinal, block in enumerate(response["output"]["message"]["content"], start=1):
        if "text" in block:
            content.append({"text": scrub_text(block["text"], ordinal)})
        elif "toolUse" in block:
            use = block["toolUse"]
            content.append(
                {
                    "toolUse": {
                        "toolUseId": use["toolUseId"],
                        "name": use["name"],
                        "input": placeholder(use.get("input")),
                    }
                }
            )
        else:
            raise ValueError(f"a content block the scrub does not know: {sorted(block)}")
    return {
        "output": {"message": {"role": response["output"]["message"]["role"], "content": content}},
        "stopReason": response["stopReason"],
        "usage": response.get("usage"),
        "metrics": response.get("metrics"),
    }


def main(argv: list[str]) -> int:
    source, target = Path(argv[1]), Path(argv[2])
    scrubbed = scrub(json.loads(source.read_text(encoding="utf-8")))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(scrubbed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{source.name} -> {target}: {len(scrubbed['output']['message']['content'])} blocks")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
