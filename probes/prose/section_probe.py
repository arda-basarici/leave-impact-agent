"""The section probe: several briefs of one section class through writer and checker, once
each, with the guards' verdicts, for human inspection. Development probing, nothing sealed.

Run with the SSO profile logged in and the three prose variables set; prints the brief's
required facts, the text, the checker's raw tool input and the guard result per
construction, then totals. ``PROBE_CLASS`` picks the class (the responsibility class at
15.2, the composite at 15.4, whose section carries two facts of different subject shape),
``PROBE_COUNT`` the number of constructions.
"""

import json
import os
import sys
from random import Random

sys.path.insert(0, "tests/unit")

from prose_fixture import ORG, TZ, WORLD_START  # noqa: E402

from leaveimpact.core.ids import scenario_id  # noqa: E402
from leaveimpact.generator.entrypoint import prose_models_for, prose_models_from_env  # noqa: E402
from leaveimpact.generator.guards import (  # noqa: E402
    containment_findings,
    namespace_findings,
    required_fact_findings,
)
from leaveimpact.generator.prose.assets import load_prompt_assets  # noqa: E402
from leaveimpact.generator.prose.render import (  # noqa: E402
    checker_request,
    describe_fact,
    writer_request,
)
from leaveimpact.generator.prose.schema import ExtractionMalformed, parse_extraction  # noqa: E402
from leaveimpact.world import (  # noqa: E402
    FragmentedComposite,
    FreeTextResponsibility,
    Minting,
    StaleSourceConflict,
    allocate_slices,
    construct,
)
from leaveimpact.world.briefs import lexicon_of, target_ref  # noqa: E402

CLASSES = {
    FreeTextResponsibility.name.value: FreeTextResponsibility(),
    FragmentedComposite.name.value: FragmentedComposite(),
    StaleSourceConflict.name.value: StaleSourceConflict(),
}
PROBE_CLASS = CLASSES[os.environ.get("PROBE_CLASS", FragmentedComposite.name.value)]
COUNT = int(os.environ.get("PROBE_COUNT", "6"))
SLICES = allocate_slices(Random(0), 30, WORLD_START)


def main() -> int:
    assets = load_prompt_assets()
    writer, checker = prose_models_for(prose_models_from_env(os.environ))
    totals = {"writer_in": 0, "writer_out": 0, "checker_in": 0, "checker_out": 0, "passed": 0}
    for number in range(1, COUNT + 1):
        scenario = construct(
            PROBE_CLASS,
            (),
            ORG,
            scenario_id=scenario_id(number),
            window=SLICES[number % len(SLICES)],
            world_start=WORLD_START,
            reference_timezone=TZ,
            ids=Minting(),
            rng=Random(number),
        )
        [brief] = scenario.briefs
        # The ticket titles join the lexicon: the runbook register names the release by title.
        lexicon = lexicon_of(
            ORG,
            work_items=[p.entity for p in scenario.owned.work_items],
            documents=[p.entity for p in scenario.owned.documents],
        )
        world_forms = lexicon.forms()
        carrier = next(
            p for p in scenario.owned.documents if p.entity.id == brief.target.document_id
        )
        print(f"\n=== construction {number}: {carrier.entity.title!r}")
        for planted in scenario.owned.documents:
            for section in planted.entity.sections:
                print(f"    clause ({planted.entity.title}): {section.text}")
        for required in brief.required:
            print(f"    required: {describe_fact(required.fact, lexicon)}")
        request = writer_request(brief, lexicon, assets)
        written = writer.write(request)
        totals["writer_in"] += written.usage.input_tokens
        totals["writer_out"] += written.usage.output_tokens
        body = written.text.strip()
        print(f"--- text ({written.usage.latency_ms} ms):\n{body}")
        findings = namespace_findings(body, brief, world_forms) or required_fact_findings(
            body, brief, lexicon
        )
        if findings:
            print("--- REFUSED before the checker:", [(f.reason.value, f.message) for f in findings])
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
