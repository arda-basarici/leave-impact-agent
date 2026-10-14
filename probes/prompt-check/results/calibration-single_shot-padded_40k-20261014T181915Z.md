# Round `calibration-single_shot-padded_40k`

System `single_shot` (role `reader`) at level `padded_40k` under the normal condition.

Prompt digests: finalization `069b41c4`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20431; 12239/8192 | 47382 | 0.0585 | search 1 | 0/0/0/0 of 0 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 34.3 |
| scenario_010 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20808; 12616/8192 | 48889 | 0.0589 | search 1 | 0/0/0/0 of 0 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 31.9 |
| scenario_013 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20558; 12366/8192 | 48049 | 0.0587 | search 1 | 0/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 32.0 |
| scenario_018 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20505; 12313/8192 | 47645 | 0.0586 | search 1 | 1/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 30.7 |
| scenario_023 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20377; 12185/8192 | 47188 | 0.0585 | search 1 | 1/0/0/0 of 1 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 33.3 |
| scenario_028 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 12661; 12207/454 | 47303 | 0.0159 | search 1 | 1/1/1/0 of 2 | needed 1, true_in_a_structured_record 2, true_unneeded 3 | missing_anchor 2 | 1 (0) | 1: 0/1/0 (1) | none | all empty | 0 | 3.9 |

Round total: 6 logical calls, 73,926 input and 41,414 output tokens by usage, 0.3091 USD by the account check.
