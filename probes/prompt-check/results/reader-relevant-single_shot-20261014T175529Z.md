# Round `reader-relevant-single_shot`

System `single_shot` (role `reader`) at level `padded_90k` under the normal condition.

Prompt digests: finalization `d7e9bb84`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 12733; 12493/240 | 48580 | 0.0151 | search 1 | 0/0/0/0 of 0 | malformed 1, true_in_a_structured_record 1, true_unneeded 1 | missing_anchor 1 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 4.7 |
| scenario_010 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 13198; 12848/350 | 50029 | 0.0161 | search 1 | 0/0/0/0 of 0 | true_in_a_structured_record 2, true_unneeded 3 | missing_anchor 2 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 3.0 |
| scenario_013 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 12755; 12598/157 | 49189 | 0.0147 | search 1 | 0/0/0/0 of 2 | true_in_a_structured_record 1, true_unneeded 1 | missing_anchor 1 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 2.7 |
| scenario_018 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20614; 12422/8192 | 48350 | 0.0587 | search 1 | 1/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 31.2 |
| scenario_023 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 12679; 12439/240 | 48386 | 0.0150 | search 1 | 1/1/1/1 of 1 | needed 1, true_in_a_structured_record 1, true_unneeded 1 | missing_anchor 1 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 2.8 |
| scenario_028 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 12769; 12316/453 | 48008 | 0.0160 | search 1 | 1/1/1/1 of 2 | needed 1, true_in_a_structured_record 2, true_unneeded 3 | missing_anchor 2 | 1 (0) | 1: 1/0/0 (0) | none | all empty | 0 | 5.1 |

Round total: 6 logical calls, 75,116 input and 9,632 output tokens by usage, 0.1356 USD by the account check.
