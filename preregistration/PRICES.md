# The price table's sources

`prices.json` beside this file is the committed price table: integer pico-dollars per
token (one dollar per million tokens is 1,000,000), one row per pricing key, region,
billing mode and token class, with the table's policy on a counter the provider omits
(`when_absent`). The harness prices every dispatch from it and sizes every reservation
by it, and the evaluator holds each export's embedded basis to the table at the commit the
export cites, so a row changes only here and a change is a commit. The file is written
through the encoder in `core.pricing`, never by hand.

## Rows

| pricing key | region | mode | class | pico-dollars per token | per million | read from |
|---|---|---|---|---|---|---|
| `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | eu-central-1 | on_demand | input_tokens | 1,100,000 | $1.10 | the Bedrock pricing page, in a browser, 2026-08-26 |
| same | same | same | output_tokens | 5,500,000 | $5.50 | the Bedrock pricing page, in a browser, 2026-08-26 |
| same | same | same | cache_write_input_tokens | 1,375,000 | $1.375 | derived: Anthropic's published five-minute cache-write rate ($1.25) at the same geographic premium |
| same | same | same | cache_read_input_tokens | 110,000 | $0.11 | derived: Anthropic's published cache-read rate ($0.10) at the same geographic premium |

`when_absent` is `unknown` on every row: a cache counter the response omits leaves the
cost incomplete until a probe earns the `zero` entry for this configuration (DESIGN, the
cost passage). The first probe from the instance (2026-10-11) saw both cache counters
present and zero on a Haiku call with no cache point, which is data for that entry and not
yet the entry.

## Where each figure comes from, and what confirms it

- **The input and output rates** were read from the Amazon Bedrock pricing page
  (`https://aws.amazon.com/bedrock/pricing/`) in a browser on 2026-08-26, during the
  Bedrock probe (`probes/FINDINGS.md`, the `bedrock` entry): the EU geographic profile
  prices at the global profile's rate plus ten percent, flat, which for Haiku 4.5 gives
  $1.10 and $5.50 a million. The page renders its tables client-side, so a scripted read
  of it shows no Anthropic rows; the browser read is the source, and the number is the
  one the prompt check's spend was computed at (`probes/FINDINGS.md`, the prompt-check
  entries).
- **The two cache rates** were not read from an AWS page. They are Anthropic's published
  base rates for Haiku 4.5 (`https://platform.claude.com/docs/en/about-claude/pricing`,
  read 2026-10-11: $1.25 a million for a five-minute cache write, $0.10 for a cache read)
  at the same ten-percent premium the input and output rows carry. They are marked derived
  here until a bill line or a browser read of the page confirms them.
- **The premium's direction** is stated by both parties, each from its side. Anthropic's
  page (read 2026-10-11): "Regional and multi-region endpoints include a 10% premium over
  global endpoints." AWS's cross-region inference guide
  (`https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html`,
  read 2026-10-11) puts the global profile at "Approximately 10% savings" against the
  geographic one and says "The price is calculated based on the Region from which you
  call an inference profile." The `eu.` profile is the geographic one; the development
  runs call it from eu-central-1.
- **The bill confirms or corrects every row.** The first live run's cost is read off the
  account's bill after the run (step 14, fork 6) and recorded in `probes/FINDINGS.md`
  beside the table's figure; a row the bill contradicts is corrected here, in a commit,
  before any further run is priced.
- **Counting is free.** The Bedrock user guide's CountTokens page
  (`https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html`, read
  2026-10-11) says "Using the CountTokens API doesn't incur charges." The registered
  input-bound method counts every request before it is sent, and no row prices a count.
  The production counting client counted from the instance on 2026-10-13 (the `step-14`
  entry in `probes/FINDINGS.md`; `captures/investigator-principals/instance-run-02.txt`),
  so the first bill that covers the live runs is where a charge for counting would show
  if the sentence were wrong.

## What waits for the freeze

Rows for the other shortlisted models (Nova and Titan in Frankfurt), their cache classes
where the family bills them, and the implicit cache-read rows are added when the freeze
names those models or declines them; the table's digest moves with every row, and every
export records the digest it was priced under.
