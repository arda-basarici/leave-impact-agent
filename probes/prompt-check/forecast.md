# The prompt check's forecast, computed before any live call

World `b7ec4563…`, condition `normal`, level `base`; the model `eu.anthropic.claude-haiku-4-5-20251001-v1:0` at temperature 0 and 8,192 output tokens; caps 20 calls and 400,000 tokens with 2 calls and 20,000 tokens reserved for the finalization; the registration at `a0ff7f81`, the harness at `85eb190e` (dirty); prompt digests finalization `e3336aa5`, opening `a414b411`, system `5a5d9530`; the reservation per run 1.45 USD.

Tokens are bounded from the request's bytes by the input-bound probe's ratio (2.5 to 6.0 bytes a token); the live run reports the provider's count.

| scenario | abstains | first request (bytes, tokens) | finalization with no read (bytes) | targets (required) | by predicate | on comments / on sections | documents holding section targets (count, bytes) | a clause asking for two or more |
|---|---|---|---|---|---|---|---|---|
| scenario_009 | no | 33,023, 5,503 to 13,209 | 29,437 | 0 (0) | none | 0 / 0 | 0, 0 | no |
| scenario_010 | no | 33,669, 5,611 to 13,467 | 30,083 | 0 (0) | none | 0 / 0 | 0, 0 | no |
| scenario_013 | no | 33,217, 5,536 to 13,286 | 29,631 | 3 (2) | has_skill 1, names_responsible 1, requires 1 | 1 / 2 | 2, 187 | no |
| scenario_018 | no | 33,564, 5,594 to 13,425 | 29,978 | 2 (2) | has_skill 1, requires 1 | 1 / 1 | 1, 159 | no |
| scenario_023 | no | 33,023, 5,503 to 13,209 | 29,437 | 1 (1) | requires 1 | 0 / 1 | 1, 189 | no |
| scenario_028 | no | 33,217, 5,536 to 13,286 | 29,631 | 1 (1) | owns_work_item 1 | 0 / 1 | 1, 168 | no |

Six first requests together: 199,713 bytes (33,285 to 79,885 tokens).
