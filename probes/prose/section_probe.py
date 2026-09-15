"""The 15.2 workstation probe: several responsibility briefs through writer and checker, once
each, with the guards' verdicts, for human inspection. Development probing, nothing sealed.

Run with the SSO profile logged in and the three prose variables set; prints the text,
the checker's raw tool input and the guard result per construction, then totals.
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
from leaveimpact.generator.prose.render import checker_request, writer_request  # noqa: E402
from leaveimpact.generator.prose.schema import ExtractionMalformed, parse_extraction  # noqa: E402
from leaveimpact.world import FreeTextResponsibility, Minting, allocate_slices, construct  # noqa: E402
from leaveimpact.world.briefs import lexicon_of, target_ref  # noqa: E402

COUNT = int(os.environ.get("PROBE_COUNT", "6"))
SLICES = allocate_slices(Random(0), 30, WORLD_START)


def main() -> int:
    assets = load_prompt_assets()
    writer, checker = prose_models_for(prose_models_from_env(os.environ))
    totals = {"writer_in": 0, "writer_out": 0, "checker_in": 0, "checker_out": 0, "passed": 0}
    for number in range(1, COUNT + 1):
        scenario = construct(
            FreeTextResponsibility(),
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
        lexicon = lexicon_of(ORG, documents=[p.entity for p in scenario.owned.documents])
        world_forms = lexicon.forms()
        note, procedure = scenario.owned.documents
        contact = brief.namespace.form_of("employee", scenario.owned.leaves[0].entity.employee_id)
        print(f"\n=== construction {number}: {note.entity.title!r} / contact {contact}")
        print(f"    procedure clause: {procedure.entity.sections[0].text}")
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
