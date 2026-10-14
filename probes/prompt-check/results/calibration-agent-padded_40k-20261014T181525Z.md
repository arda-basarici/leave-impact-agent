# Round `calibration-agent-padded_40k`

System `agent` (role `investigator`) at level `padded_40k` under the normal condition.

Prompt digests: finalization `d495fefb`, opening `a414b411`, system `24b74144`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 4 / 4 / 4 | tool_use 4 | 27 | 42243; 40758/1485 | 33389 | 0.0530 | document 2, search 4 | 0/0/0/0 of 0 | false 2, true_in_a_structured_record 3, true_unneeded 6 | missing_anchor 3 | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 14.8 |
| scenario_010 | closed/completed | 7 / 7 / 7 | max_tokens 1, tool_use 6 | 43 | 97446; 88040/9406 | 34043 | 0.1486 | search 10 | 0/0/0/0 of 0 | malformed 3 | none | 2 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 45.3 |
| scenario_013 | closed/completed | 4 / 4 / 4 | tool_use 4 | 25 | 40486; 39462/1024 | 33195 | 0.0490 | document 1, search 2, work_item 1 | 1/1/1/1 of 2 | needed 2, true_in_a_structured_record 3, true_unneeded 4 | missing_anchor 3 | 2 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 9.5 |
| scenario_018 | closed/completed | 4 / 4 / 4 | tool_use 4 | 32 | 45450; 43497/1953 | 33537 | 0.0586 | document 5, search 6 | 2/2/2/2 of 2 | needed 3, true_in_a_structured_record 2, true_unneeded 12 | missing_anchor 2 | 2 (0) | 8: 4/0/0 (0) | none | all empty | 0 | 13.6 |
| scenario_023 | closed/completed | 5 / 5 / 5 | tool_use 5 | 35 | 54051; 52760/1291 | 33195 | 0.0651 | document 2, search 4, work_item 4 | 1/1/1/1 of 1 | needed 2, true_in_a_structured_record 2, true_unneeded 4 | missing_anchor 2 | 2 (0) | 2: 1/0/0 (0) | none | all empty | 0 | 11.8 |
| scenario_028 | closed/completed | 4 / 4 / 4 | tool_use 4 | 29 | 45503; 42903/2600 | 33195 | 0.0615 | search 8 | 2/2/2/2 of 2 | needed 4, true_in_a_structured_record 2, true_unneeded 15 | missing_anchor 2 | 2 (0) | 10: 5/0/0 (0) | none | all empty | 0 | 27.3 |

Round total: 28 logical calls, 307,420 input and 17,759 output tokens by usage, 0.4358 USD by the account check.
