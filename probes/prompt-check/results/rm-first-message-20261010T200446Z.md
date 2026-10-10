# Round `rm-first-message`

Prompt digests: finalization `e3336aa5`, opening `a414b411`, system `e89c0c01`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | cost (USD) | model reads by tool | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 13 / 13 / 13 | tool_use 13 | 76 | 149967; 147852/2115 | 0.1743 | document 1, search 17, work_item 1 | 0/0/0/0 of 0 | true_unneeded 4 | none | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 28.2 |
| scenario_010 | closed/completed | 4 / 4 / 4 | tool_use 4 | 29 | 43077; 41907/1170 | 0.0525 | event 1, search 4, work_item 3 | 0/0/0/0 of 0 | malformed 3, true_unneeded 4 | none | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 9.7 |
| scenario_013 | closed/completed | 5 / 5 / 5 | tool_use 5 | 32 | 53039; 51791/1248 | 0.0638 | document 2, search 5 | 2/2/2/1 of 2 | needed 4, true_unneeded 3 | none | 2 (0) | 2: 0/0/1 (0) | none | all empty | 0 | 12.0 |
| scenario_018 | closed/completed | 6 / 6 / 6 | tool_use 6 | 42 | 69527; 67819/1708 | 0.0840 | document 3, event 1, search 5, work_item 4 | 2/2/2/2 of 2 | malformed 3, needed 3, true_unneeded 6 | none | 2 (0) | 4: 2/0/0 (0) | none | all empty | 0 | 14.6 |
| scenario_023 | closed/completed | 4 / 4 / 4 | tool_use 4 | 30 | 44006; 42445/1561 | 0.0553 | document 2, search 4, work_item 3 | 1/1/1/1 of 1 | malformed 3, needed 2, true_unneeded 7 | none | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 12.7 |
| scenario_028 | closed/completed | 13 / 13 / 13 | tool_use 13 | 80 | 166782; 163814/2968 | 0.1965 | document 3, search 17, work_item 3 | 1/1/1/1 of 1 | needed 2, true_unneeded 13 | none | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 28.9 |
| scenario_014 | closed/completed | 5 / 5 / 5 | tool_use 5 | 35 | 55670; 53818/1852 | 0.0694 | document 3, search 3, work_item 4 | 1/1/1/1 of 1 | malformed 4, needed 2, true_unneeded 7 | none | 2 (0) | 6: 3/0/0 (0) | none | all empty | 0 | 14.4 |

Round total: 50 logical calls, 569,446 input and 12,622 output tokens by usage, 0.6958 USD by the account check.
