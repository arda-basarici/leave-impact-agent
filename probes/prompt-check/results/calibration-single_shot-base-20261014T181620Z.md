# Round `calibration-single_shot-base`

System `single_shot` (role `reader`) at level `base` under the normal condition.

Prompt digests: finalization `069b41c4`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 10648; 9217/1431 | 32931 | 0.0180 | search 1 | 0/0/0/0 of 0 | true_in_a_structured_record 2, true_unneeded 16 | missing_anchor 2 | 1 (0) | 4: 4/0/0 (0) | none | all empty | 0 | 9.0 |
| scenario_010 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 9718; 8882/836 | 31310 | 0.0144 | search 1 | 0/0/0/0 of 0 | true_in_a_structured_record 2, true_unneeded 10 | missing_anchor 2 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 4.6 |
| scenario_013 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 10241; 8986/1255 | 32001 | 0.0168 | search 1 | 1/1/1/1 of 2 | needed 1, true_in_a_structured_record 2, true_unneeded 13 | missing_anchor 2 | 1 (0) | 3: 3/0/0 (0) | none | all empty | 0 | 6.8 |
| scenario_018 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 11589; 9671/1918 | 34859 | 0.0212 | search 1 | 2/2/2/2 of 2 | needed 2, true_in_a_structured_record 2, true_unneeded 19 | missing_anchor 2 | 1 (0) | 9: 8/1/0 (0) | none | all empty | 0 | 9.6 |
| scenario_023 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 10594; 9163/1431 | 32737 | 0.0179 | search 1 | 1/1/1/1 of 1 | needed 1, true_in_a_structured_record 2, true_unneeded 15 | missing_anchor 2 | 1 (0) | 4: 4/0/0 (0) | none | all empty | 0 | 7.5 |
| scenario_028 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 11483; 9565/1918 | 34517 | 0.0211 | search 1 | 2/2/2/2 of 2 | needed 2, true_in_a_structured_record 2, true_unneeded 19 | missing_anchor 2 | 1 (0) | 9: 7/2/0 (0) | none | all empty | 0 | 9.8 |

Round total: 6 logical calls, 55,484 input and 8,789 output tokens by usage, 0.1094 USD by the account check.
