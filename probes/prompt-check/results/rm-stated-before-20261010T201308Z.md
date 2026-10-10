# Round `rm-stated-before`

Prompt digests: finalization `773937b3`, opening `a414b411`, system `b95a5ccb`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | cost (USD) | model reads by tool | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 6 / 6 / 6 | tool_use 6 | 36 | 61235; 60257/978 | 0.0717 | search 6, work_item 1 | 0/0/0/0 of 0 | true_unneeded 3 | none | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 13.3 |
| scenario_010 | closed/completed | 6 / 6 / 6 | tool_use 6 | 39 | 66219; 65033/1186 | 0.0781 | event 1, search 6, work_item 3 | 0/0/0/0 of 0 | malformed 2, true_unneeded 2 | none | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 13.0 |
| scenario_013 | closed/completed | 4 / 4 / 4 | tool_use 4 | 27 | 41394; 40408/986 | 0.0499 | document 1, search 5 | 1/1/1/1 of 2 | needed 2, true_unneeded 3 | none | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 10.2 |
| scenario_018 | closed/completed | 4 / 4 / 4 | tool_use 4 | 29 | 43413; 42148/1265 | 0.0533 | document 3, search 5 | 2/2/2/2 of 2 | needed 3, true_unneeded 6 | none | 2 (0) | 4: 2/0/0 (0) | none | all empty | 0 | 9.8 |
| scenario_023 | closed/completed | 6 / 6 / 6 | tool_use 6 | 43 | 71002; 68452/2550 | 0.0893 | document 5, search 6, work_item 3 | 1/1/1/1 of 1 | malformed 3, needed 2, true_unneeded 14 | none | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 19.4 |
| scenario_028 | closed/completed | 5 / 5 / 5 | tool_use 5 | 33 | 53146; 51990/1156 | 0.0635 | document 2, search 6 | 1/1/1/1 of 1 | needed 2, true_unneeded 5 | none | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 11.9 |
| scenario_014 | closed/completed | 4 / 4 / 4 | tool_use 4 | 27 | 42553; 41074/1479 | 0.0533 | document 3, search 3 | 1/1/1/1 of 1 | malformed 2, needed 2, true_unneeded 7 | none | 2 (0) | 6: 3/0/0 (0) | none | all empty | 0 | 11.1 |

Round total: 35 logical calls, 369,362 input and 9,600 output tokens by usage, 0.4591 USD by the account check.
