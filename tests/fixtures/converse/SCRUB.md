# Scrubbed Converse responses

Real responses of the pinned Bedrock client, scrubbed by `probes/parse_protocol/scrub.py`
so the tree may hold them; the raw captures stay outside the repository by the acceptance
spike's rule, since a response quotes the world's names and ids.

What the scrub keeps is exactly what the parse protocol (`agent/answer_parse.py`) reads:
the content blocks in order and by kind; a `toolUse` block's id, name, and the object-ness
and keys of its input, every value a placeholder; a text block's first non-blank character
(a payload keeps its JSON structure with placeholder values, prose becomes `[text n]`); the
stop reason; the usage and metrics. Nothing else of the response survives.

| fixture | origin | shape |
|---|---|---|
| `live-path-call-1.json` | the acceptance spike's live path, 2026-10-04, execution `925dc1`, call 1 (Haiku 4.5 on the `eu.` profile) | stop `tool_use`; a text block beside two `toolUse` blocks (`employee`, `team`), each input an object with one key |
| `live-path-call-2.json` | the same execution, call 2 | stop `end_turn`; one text block |
| `parse-probe-20261006T205828Z.json` | the live parse probe, 2026-10-06 (Haiku 4.5 on the `eu.` profile, one send) | stop `tool_use`; one `state_facts` call whose `facts` holds one entry nested one list deeper than the schema says; no text block |

The responses were parsed through `parse_answer` for the first time by the worker group's
capture replay (`tests/unit/test_agent_answer_parse_captures.py`). The live parse probe
(`probes/parse_protocol/live_probe.py`) added the `state_facts` shape; no response holds a
`{` text block, which the probe asked for and did not get.
