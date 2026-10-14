# Round `reader-relevant-full_context`

System `full_context` (role `reader`) at level `padded_90k` under the normal condition.

Prompt digests: finalization `d7e9bb84`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 97716; 97476/240 | 437021 | 0.1085 | documents 1 | 0/0/0/0 of 0 | malformed 1, true_in_a_structured_record 1, true_unneeded 1 | missing_anchor 1 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 7.1 |
| scenario_010 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 99148; 97674/1474 | 437675 | 0.1155 | documents 1 | 0/0/0/0 of 0 | malformed 16, true_in_a_structured_record 2, true_unneeded 3 | missing_anchor 2 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 11.3 |
| scenario_013 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 97651; 97422/229 | 436827 | 0.1084 | documents 1 | 2/0/0/0 of 2 | malformed 1, true_in_a_structured_record 1, true_unneeded 1 | missing_anchor 1 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 5.3 |
| scenario_018 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 98412; 97528/884 | 437169 | 0.1121 | documents 1 | 2/1/1/1 of 2 | malformed 11, needed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 8.5 |
| scenario_023 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 97662; 97422/240 | 436827 | 0.1085 | documents 1 | 1/0/0/0 of 1 | malformed 1, true_in_a_structured_record 1, true_unneeded 1 | missing_anchor 1 | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 5.4 |
| scenario_028 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 97852; 97422/430 | 436827 | 0.1095 | documents 1 | 2/0/0/0 of 2 | malformed 6 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 0 | 5.7 |

Round total: 6 logical calls, 584,944 input and 3,497 output tokens by usage, 0.6627 USD by the account check.
