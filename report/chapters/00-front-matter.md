# Where the Single Call Stops

*An LLM leave-impact investigator against one-call readers under a fixed output budget,
on a constructed organization.*

When an employee goes on leave, someone has to work out what their absence affects and
who can cover it. The investigator is an LLM agent that reads an organization's HR
system, issue tracker, calendar and documents and drafts that coverage plan with its
evidence. This report measures whether its reading loop earns its cost against three
simpler ways of producing the same plan, on an organization built so that the right
answer is known.

| System | Base level | Padded level |
|---|---|---|
| Investigator (the system under study) | {{pin:whole.agent.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.agent.padded}} of {{pin:scenarios.per_arm}} |
| Full context, one call | {{pin:whole.full_context.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.full_context.padded}} of {{pin:scenarios.per_arm}} |
| Single shot, one retrieval then one call | {{pin:whole.single_shot.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.single_shot.padded}} of {{pin:scenarios.per_arm}} |
| Rules only, no model | {{pin:whole.rules_only.base}} of {{pin:scenarios.per_arm}} | {{pin:whole.rules_only.padded}} of {{pin:scenarios.per_arm}} |

Four systems answered the same thirty leave scenarios on one generated organization, at
two corpus levels, {{pin:runs.total}} runs in all for about {{pin:cost.total_usd.rounded}}
in model calls. The table counts scenarios answered correct whole: every required claim
present and right, nothing unexpected claimed, and no finding against the plan.

> At the base level a single call shown every document is correct on all thirty and the
> investigator is correct on fewer. At the padded level the single call stops at its
> output allowance on {{pin:stopped.full_context.padded}} calls, the cap on what it may
> write and not on what it may read, and falls to {{pin:whole.full_context.padded}},
> while the investigator holds its {{pin:whole.agent.padded}}: an observed difference
> of {{pin:difference.agent.full_context.padded.points}} percentage points of scenarios,
> with a paired interval of {{pin:difference.agent.full_context.padded.points_interval}}
> points at {{pin:statistics.confidence_percent}} percent.

Two things belong beside that result. The padded level's size was chosen, before the
measurement world existed, so that the single call would fail on a development world.
And one model, Claude Haiku 4.5, played every role in every system measured, on one
world, with one run per scenario. The finding is about these systems under their
registered output budgets. It says nothing about agents in general.

## Contents

{{contents}}
