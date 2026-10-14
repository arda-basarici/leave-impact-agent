# Round `calibration-full_context-padded_70k`

System `full_context` (role `reader`) at level `padded_70k` under the normal condition.

Prompt digests: finalization `069b41c4`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 82435; 74243/8192 | 330818 | 0.1267 | documents 1 | 0/0/0/0 of 0 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 41.2 |
| scenario_010 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 82633; 74441/8192 | 331472 | 0.1269 | documents 1 | 0/0/0/0 of 0 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 34.9 |
| scenario_013 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 75798; 74189/1609 | 330624 | 0.0905 | documents 1 | 2/1/1/1 of 2 | malformed 5, needed 1, true_in_a_structured_record 2, true_unneeded 13 | missing_anchor 2 | 1 (0) | 5: 5/0/0 (0) | none | all empty | 0 | 10.7 |
| scenario_018 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 82487; 74295/8192 | 330966 | 0.1268 | documents 1 | 2/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 39.0 |
| scenario_023 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 82381; 74189/8192 | 330624 | 0.1267 | documents 1 | 1/0/0/0 of 1 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 35.3 |
| scenario_028 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 82381; 74189/8192 | 330624 | 0.1267 | documents 1 | 2/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 39.4 |

Round total: 6 logical calls, 445,546 input and 42,569 output tokens by usage, 0.7242 USD by the account check.
