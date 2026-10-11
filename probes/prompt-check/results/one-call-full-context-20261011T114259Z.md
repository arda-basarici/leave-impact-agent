# Round `one-call-full-context`

System `full_context` (role `reader`) at level `padded` under the normal condition.

Prompt digests: finalization `069b41c4`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 20680; 12676/8004 | 48932 | 0.0580 | documents 1 | 0/0/0/0 of 0 | false 49, true_unneeded 30 | missing_anchor 36 | 1 (0) | 65: 26/4/0 (0) | scope_without_one_section 12 | all empty | 0 | 35.2 |
| scenario_010 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 20880; 12876/8004 | 49578 | 0.0582 | documents 1 | 0/0/0/0 of 0 | false 48, true_unneeded 31 | missing_anchor 35 | 1 (0) | 65: 26/4/0 (0) | scope_without_one_section 12 | all empty | 0 | 33.4 |
| scenario_013 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 20734; 12730/8004 | 49126 | 0.0580 | documents 1 | 2/2/2/2 of 2 | false 48, needed 2, true_unneeded 29 | missing_anchor 35 | 1 (0) | 65: 26/4/0 (0) | scope_without_one_section 12 | all empty | 0 | 33.9 |
| scenario_018 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 20842; 12838/8004 | 49473 | 0.0581 | documents 1 | 2/2/2/2 of 2 | false 48, needed 2, true_unneeded 29 | missing_anchor 35 | 1 (0) | 65: 27/3/0 (0) | scope_without_one_section 12 | all empty | 0 | 33.6 |
| scenario_023 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 20680; 12676/8004 | 48932 | 0.0580 | documents 1 | 1/1/1/1 of 1 | false 48, needed 1, true_unneeded 30 | missing_anchor 35 | 1 (0) | 65: 26/4/0 (0) | scope_without_one_section 12 | all empty | 0 | 33.6 |
| scenario_028 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 20734; 12730/8004 | 49126 | 0.0580 | documents 1 | 1/1/1/1 of 1 | false 48, needed 1, true_unneeded 30 | missing_anchor 35 | 1 (0) | 65: 26/4/0 (0) | scope_without_one_section 12 | all empty | 0 | 33.6 |
| scenario_014 | closed/completed | 1 / 1 / 1 | tool_use 1 | 10 | 20680; 12676/8004 | 48932 | 0.0580 | documents 1 | 1/1/1/1 of 1 | false 48, needed 1, true_unneeded 30 | missing_anchor 35 | 1 (0) | 65: 26/4/0 (0) | scope_without_one_section 12 | all empty | 0 | 33.6 |

Round total: 7 logical calls, 89,202 input and 56,028 output tokens by usage, 0.4063 USD by the account check.
