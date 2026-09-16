"""The comment probe: one real brief of a sealed-shape world through writer and checker
several times, with the guards' verdicts, for human inspection. Development probing,
nothing sealed.

Where the section probe constructs fixture scenarios, this one replays a target the
generation job actually refused: the semantic world is assembled from the job's own
recipe (pure, no network), the lexicon is built as the materializer builds it, and the
writer request is the byte-identical request the job sent, so every attempt here is one
more fresh sample of the configuration the job exhausted. Written at step 16, when the
golden world's first dispatch exhausted the cap on one ticket comment with other-claim
refusals on every attempt and the log, by design, carried counts and never a sentence.

What it found (``probes/FINDINGS.md``, ``comment-probe``): zero of six under the register
as dispatched, the failure two-faced, the writer assessing the work as the register asked
("the freeze is coming up", "straightforward") and the checker reading a component named
as the work's context as the author's membership. The register rewritten on the writer's
side (what the author knows or has done, no assessment of the work, the ticket by its
title) took the target to six of six and the three comment briefs to eleven of fourteen;
the checker-side rule, tried in the system prompt and in the predicate line, moved nothing
on Nova Pro and was dropped. After the attempts, two fixed membership cases go through the
checker alone, so the residual reading is on record each time the probe runs: a component
as work context (the checker still records a membership, a false positive that costs a
safe retry) and an explicit belonging (recorded, as it must be).

Run with the SSO profile logged in and the three prose variables set; prints the brief's
required and allowed facts, the writer's message, then per attempt the text, the checker's
raw tool input and the guard result, then totals, then the membership cases. ``PROBE_SEED``,
``PROBE_PLAN`` and ``PROBE_WORLD_START`` name the recipe (defaults: 16, golden,
2026-01-05), ``PROBE_TARGET`` the brief (default ``comment_002``), ``PROBE_COUNT`` the
attempts (default 6).
"""

import json
import os
import sys

from leaveimpact.generator.entrypoint import (
    parse_recipe,
    prose_models_for,
    prose_models_from_env,
)
from leaveimpact.generator.guards import (
    containment_findings,
    namespace_findings,
    required_fact_findings,
)
from leaveimpact.generator.prose.assets import load_prompt_assets
from leaveimpact.generator.prose.render import checker_request, describe_fact, writer_request
from leaveimpact.generator.prose.schema import ExtractionMalformed, parse_extraction
from leaveimpact.world import assemble_semantic_world
from leaveimpact.world.briefs import lexicon_of, target_ref

SEED = os.environ.get("PROBE_SEED", "16")
PLAN = os.environ.get("PROBE_PLAN", "golden")
WORLD_START = os.environ.get("PROBE_WORLD_START", "2026-01-05")
TARGET = os.environ.get("PROBE_TARGET", "comment_002")
COUNT = int(os.environ.get("PROBE_COUNT", "6"))
MEMBERSHIP_CASES = (
    (
        "negative (work context only, expect none)",
        "I've got Python experience with queue migrations, so the retry queue work in "
        "Mobile Release is familiar territory for me.",
    ),
    (
        "positive (explicit belonging, expect one)",
        "I'm on the Mobile Release component, and I've got Python experience with queue "
        "migrations.",
    ),
)


def main() -> int:
    recipe = parse_recipe(["--seed", SEED, "--world-start", WORLD_START, "--plan", PLAN])
    semantic = assemble_semantic_world(
        recipe.seed, recipe.params, recipe.world_start, recipe.plan_name
    )
    lexicon = lexicon_of(
        semantic.org,
        [p.entity for s in semantic.scenarios for p in s.owned.work_items],
        [p.entity for s in semantic.scenarios for p in s.owned.documents],
        [p.entity for s in semantic.scenarios for p in s.owned.events],
    )
    world_forms = lexicon.forms()
    brief = next(b for s in semantic.scenarios for b in s.briefs if b.id == TARGET)
    assets = load_prompt_assets()
    writer, checker = prose_models_for(prose_models_from_env(os.environ))

    print(f"=== {TARGET} of seed {SEED}, plan {PLAN}, start {WORLD_START}")
    for required in brief.required:
        print(f"    required: {describe_fact(required.fact, lexicon)}")
    for allowed in brief.allowed:
        print(f"    allowed:  {describe_fact(allowed, lexicon)}")
    request = writer_request(brief, lexicon, assets)
    print(f"--- writer message:\n{request.message}")

    totals = {"writer_in": 0, "writer_out": 0, "checker_in": 0, "checker_out": 0, "passed": 0}
    for attempt in range(1, COUNT + 1):
        written = writer.write(request)
        totals["writer_in"] += written.usage.input_tokens
        totals["writer_out"] += written.usage.output_tokens
        body = written.text.strip()
        print(f"\n=== attempt {attempt} ({written.usage.latency_ms} ms):\n{body}")
        findings = namespace_findings(body, brief, world_forms) or required_fact_findings(
            body, brief, lexicon
        )
        if findings:
            refused = [(f.reason.value, f.message) for f in findings]
            print("--- REFUSED before the checker:", refused)
            continue
        call = checker.extract(checker_request(body, brief, assets))
        totals["checker_in"] += call.usage.input_tokens
        totals["checker_out"] += call.usage.output_tokens
        print(f"--- checker raw tool input ({call.usage.latency_ms} ms):")
        print(json.dumps(call.input, indent=2))
        try:
            extraction = parse_extraction(call.input, brief.namespace, target_ref(brief.target))
        except ExtractionMalformed as fault:
            print("--- REFUSED: extraction malformed:", fault)
            continue
        findings = containment_findings(brief, extraction)
        if findings:
            print("--- REFUSED by containment:", [(f.reason.value, f.message) for f in findings])
            continue
        totals["passed"] += 1
        print("--- ACCEPTED")
    print("\n=== totals:", totals)

    # The membership cases, checker only, against the same brief: a component named as the
    # work's context should yield no membership of the author, a plain statement of
    # belonging must yield one. Only the model can show what the model infers, so the cases
    # live here and not in the unit suite; on Nova Pro the first still reads as membership
    # after both prompt placements were tried, which is why the register avoids the phrasing
    # rather than the checker being told not to infer.
    author = target_ref(brief.target)
    for label, text in MEMBERSHIP_CASES:
        call = checker.extract(checker_request(text, brief, assets))
        propositions = call.input.get("propositions", [])
        membership = [
            p
            for p in propositions
            if p.get("predicate") in ("member_of_component", "member_of_team")
        ]
        print(f"\n=== membership case, {label}: {text}")
        print("--- memberships recorded:", json.dumps(membership))
        print("--- author:", author)
    return 0


if __name__ == "__main__":
    sys.exit(main())
