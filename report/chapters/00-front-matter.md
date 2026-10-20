# Where the Single Call Stops

*Evaluating an LLM leave-impact investigator on a constructed organization.*

| System | Base level | Padded level |
|---|---|---|
| Investigator | {{pin:whole.agent.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.agent.padded}} of {{pin:scenarios.per_arm}} |
| Full context, one call | {{pin:whole.full_context.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.full_context.padded}} of {{pin:scenarios.per_arm}} |
| Single shot, one retrieval then one call | {{pin:whole.single_shot.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.single_shot.padded}} of {{pin:scenarios.per_arm}} |
| Rules only, no model | {{pin:whole.rules_only.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.rules_only.padded}} of {{pin:scenarios.per_arm}} |

Four systems answered the same thirty leave scenarios on one generated organization, at
two sizes of document corpus, {{pin:runs.total}} runs in all for {{pin:cost.total_usd}}.
Scenarios correct whole, every claim right and every claim grounded, are counted above.
At the base level a single call shown every document is correct on all thirty and the
investigator is behind it. At the padded level the single call stops at its output
maximum on {{pin:stopped.full_context.padded}} calls and falls to
{{pin:whole.full_context.padded}}, while the investigator holds its
{{pin:whole.agent.padded}}; the paired difference is {{pin:difference.agent.full_context.padded}}
at {{pin:statistics.confidence_percent}} percent. That is a finding about these systems
under their registered output budgets on one world, with one run per scenario, and not a
general advantage of agents.
