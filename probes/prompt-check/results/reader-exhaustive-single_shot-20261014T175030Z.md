# Round `reader-exhaustive-single_shot`

System `single_shot` (role `reader`) at level `padded_90k` under the normal condition.

Prompt digests: finalization `069b41c4`, opening `b20b6141`, system `29290e9f`.

| scenario | ending | calls / dispatches / sends | stop reasons | finalization at | tokens (account; usage in/out) | first request bytes | cost (USD) | reads by tool beyond the prefetch | targets returned/emitted/admitted/usable of n | emissions by class | refusals by reason | batches (nested) | requires stated: placed/unplaced/ambiguous (overruns) | exclusions | plumbing findings | max-tokens with tool use | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| scenario_009 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20657; 12465/8192 | 48435 | 0.0588 | search 1 | 0/0/0/0 of 0 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 33.3 |
| scenario_010 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 21012; 12820/8192 | 49884 | 0.0592 | search 1 | 0/0/0/0 of 0 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 34.0 |
| scenario_013 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20762; 12570/8192 | 49044 | 0.0589 | search 1 | 0/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 31.8 |
| scenario_018 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20586; 12394/8192 | 48205 | 0.0587 | search 1 | 1/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 31.1 |
| scenario_023 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20603; 12411/8192 | 48241 | 0.0587 | search 1 | 1/0/0/0 of 1 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 31.9 |
| scenario_028 | closed/completed | 1 / 1 / 1 | max_tokens 1 | 10 | 20480; 12288/8192 | 47863 | 0.0586 | search 1 | 1/0/0/0 of 2 | malformed 1 | none | 1 (0) | 0: 0/0/0 (0) | none | all empty | 1 | 31.8 |

Round total: 6 logical calls, 74,948 input and 49,152 output tokens by usage, 0.3528 USD by the account check.
