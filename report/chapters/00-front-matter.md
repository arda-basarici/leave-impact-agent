# Where the Single Call Stops

*Evaluating an LLM leave-impact investigator on a constructed organization.*

| System | Base level | Padded level |
|---|---|---|
| Investigator | {{pin:whole.agent.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.agent.padded}} of {{pin:scenarios.per_arm}} |
| Full context, one call | {{pin:whole.full_context.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.full_context.padded}} of {{pin:scenarios.per_arm}} |
| Single shot, one retrieval then one call | {{pin:whole.single_shot.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.single_shot.padded}} of {{pin:scenarios.per_arm}} |
| Rules only, no model | {{pin:whole.rules_only.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.rules_only.padded}} of {{pin:scenarios.per_arm}} |

Four systems answered the same thirty leave scenarios on one generated organization, at
two corpus levels, {{pin:runs.total}} runs in all for {{pin:cost.total_usd}}. The table
counts scenarios answered correct whole: every required claim present and right, nothing
unexpected claimed, and no finding against the plan. At the base level a single call
shown every document is correct on all thirty and the investigator is correct on fewer.
At the padded level the single call stops at its output maximum on
{{pin:stopped.full_context.padded}} calls and falls to {{pin:whole.full_context.padded}},
while the investigator holds its {{pin:whole.agent.padded}}; the paired difference is
{{pin:difference.agent.full_context.padded}} at {{pin:statistics.confidence_percent}}
percent. Two things belong beside that result. The padded level's size was chosen,
before the measurement world existed, so that the single call would fail on a
development world. And one model, Claude Haiku 4.5, played every role in every system
measured, on one world, with one run per scenario. The finding is about these systems
under their registered output budgets. It says nothing about agents in general.

## Contents

| Chapter | Question it answers |
|---|---|
| 1. What it was measured on | How the organization and its answer key are built, checked and sealed |
| 2. What a correct answer contains | The claim vocabulary, who writes the claims, and the checks |
| 3. What the model adds beyond the rules | The rules alone, one retrieval, and the loop, by tier |
| 4. When the loop helps, and when full context does better | Both levels, the mechanism, and what the experiment cannot say |
| 5. What the loop earns | What was fixed before the runs, and cost beside quality |
| 6. What this does not show | The limits, the most consequential first |
| 7. Reproducing the numbers | Where every figure in this report is read from |
