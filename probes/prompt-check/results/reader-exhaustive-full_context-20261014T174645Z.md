# Round `reader-exhaustive-full_context`

System `full_context` (role `reader`) at level `padded_90k` under the normal condition.

Prompt digests: finalization `069b41c4`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 105640; 97448/8192 | 436876 | 0.1522 | documents 1 | 0/0/0/0 of 0 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 41.4 |
| scenario_010 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 99484; 97646/1838 | 437530 | 0.1175 | documents 1 | 0/0/0/0 of 0 | malformed 13, true_in_a_structured_record 2, true_unneeded 7 | missing_anchor 2 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 12.1 |
| scenario_013 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 105586; 97394/8192 | 436682 | 0.1522 | documents 1 | 2/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 39.7 |
| scenario_018 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 105692; 97500/8192 | 437024 | 0.1523 | documents 1 | 2/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 39.5 |
| scenario_023 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 105586; 97394/8192 | 436682 | 0.1522 | documents 1 | 1/0/0/0 of 1 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 40.3 |
| scenario_028 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 105586; 97394/8192 | 436682 | 0.1522 | documents 1 | 2/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 39.8 |

Round total: 6 logical calls, 584,776 input and 42,798 output tokens by usage, 0.8786 USD by the account check.
