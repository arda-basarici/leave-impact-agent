# Round `calibration-agent-base`

System `agent` (role `investigator`) at level `base` under the normal condition.

Prompt digests: finalization `d495fefb`, opening `a414b411`, system `24b74144`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 4 / 4 / 4 | tool_use 4 | 27 | 42243; 40758/1485 | 33389 | 0.0530 | document 2, search 4 | 0/0/0/0 of 0 | false 2, true_in_a_structured_record 3, true_unneeded 6 | missing_anchor 3 | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 14.2 |
| scenario_010 | closed/completed | 7 / 7 / 7 | tool_use 7 | 43 | 78318; 75993/2325 | 34043 | 0.0964 | search 10 | 0/0/0/0 of 0 | true_in_a_structured_record 4, true_unneeded 20 | missing_anchor 4 | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 19.4 |
| scenario_013 | closed/completed | 4 / 4 / 4 | tool_use 4 | 25 | 40486; 39462/1024 | 33195 | 0.0490 | document 1, search 2, work_item 1 | 1/1/1/1 of 2 | needed 2, true_in_a_structured_record 3, true_unneeded 4 | missing_anchor 3 | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 9.1 |
| scenario_018 | closed/completed | 4 / 4 / 4 | tool_use 4 | 32 | 45450; 43497/1953 | 33537 | 0.0586 | document 5, search 6 | 2/2/2/2 of 2 | needed 3, true_in_a_structured_record 2, true_unneeded 12 | missing_anchor 2 | 2 (0) | 8: 4/0/0 (0) | none | all empty | 0 | 13.5 |
| scenario_023 | closed/completed | 5 / 5 / 5 | tool_use 5 | 35 | 54051; 52760/1291 | 33195 | 0.0651 | document 2, search 4, work_item 4 | 1/1/1/1 of 1 | needed 2, true_in_a_structured_record 2, true_unneeded 4 | missing_anchor 2 | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 11.9 |
| scenario_028 | closed/completed | 4 / 4 / 4 | tool_use 4 | 32 | 45428; 43375/2053 | 33195 | 0.0590 | document 6, search 5 | 2/2/2/2 of 2 | needed 4, true_in_a_structured_record 2, true_unneeded 13 | missing_anchor 2 | 2 (0) | 8: 4/0/0 (0) | none | all empty | 0 | 14.3 |

Round total: 28 logical calls, 295,845 input and 10,131 output tokens by usage, 0.3811 USD by the account check.
