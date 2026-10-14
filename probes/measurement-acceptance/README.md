# The measurement world's acceptance reads

The two spot checks PROTOCOL fixes before the measurement world is bound ("How the
measurement world is accepted"; the freeze's fork 16): one scenario per tier traced by the
audit method, and five filler documents read by a model of another family than the
writer's. This folder holds the draw and the filler read; the traces are a hand audit whose
records live in the git-ignored audit directory and are sealed to the truth bucket by
`scripts/audit_index.py`, as the golden world's were.

- `draw.py <world_version>`: the draw, by the development draw's rule (a stream derived from
  the frozen registration's statistics seed, the draw's name and the tier), written to
  `data/audit/acceptance_draw_<v8>.json` with each scenario's tier beside its id. The tiers
  stay private; a public record lists the scenarios as bare ids.
- `filler_read.py <world_version>`: one forced-tool call of Nova Pro per drawn document,
  answering whether the text reads as the requirement it imitates and listing every proper
  name it mentions; the names are compared in code with the world's lexicon (people, given
  names, teams, components, clients, planted titles; skills left out), so the reader never
  sees a world name. Answers, titles and hits go to `data/audit/filler_read_<v8>.json`;
  stdout carries counts and token usage.

Both run under the SSO profile (`AWS_PROFILE=leave-impact`) and refuse to write anywhere
git does not ignore. The comparator's positive controls, run once by hand on the
measurement world's forms: an exact team name, a lower-cased person's name and a person's
name inside a longer phrase each hit, a fictional release name did not.

**Run 2026-10-15 on `2e6705ba…341c`.** The draw: three scenarios, one per tier, and five
filler documents of the pool of 432. The read: five of five read as the requirement they
imitate, five of five list no name of the world against 182 forms compared; the names
listed were the documents' own fictional release or client and the skills their briefs
carry. One answer omitted the `reads_as` field the schema requires, so a reader of the
answers takes the verdict field, not that one. Usage: 3,599 input and 353 output tokens,
under a cent at Nova Pro's rates.
