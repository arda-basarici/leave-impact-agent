"""Runtime truth: where the two views of a world differ, and what an outage does to the answer.

A measurement, not a pass-or-fail probe: it has no criterion, it produced the numbers three
rulings of the investigator milestone's third build step were made on (the stream's
`m2-build/2026-10-01-step-3-rulings.md`, rulings 2, 3 and 4). It was first run on
2026-10-01 from four scratch scripts, one question at a time, while the rulings were being
argued; this file is the same computation in one pass per world, committed with its
capture so the numbers are regenerable from recorded inputs: the seeds, the golden plan,
the default organization, the generator version the run prints.

A world has two views. The *dated* view is the truth fact base, each fact visible from the
day its record was planted. The *runtime* view is what a run obtains: the systems hold
every projected record at once and the harness dates what it reads to the run's day
(`world/runtime_view.py`). World assembly proves every sealed key under both, under the
normal condition. Four questions, each over every scenario at its own run day:

1. *Divergence.* The viability rule over the whole organization under both views, per run
   condition: how many candidate-impact pairs get a different verdict or different
   reasons, split by whether the candidate is in the sealed must-assess set; how many
   expected outcomes differ. Under the normal condition the must-assess count is assembly's
   proof and must be zero. Each must-assess difference under an outage is traced.
2. *Outage shape.* Under each single-source outage, over the runtime view: whether each
   sealed impact still grounds when asked by its exact key, how each must-assess verdict
   and each outcome moves, how many unknowns and conflicts the rules derive, and whether
   "the downed source is in the key's required sources" predicts "something moved".
3. *Derived impacts.* `derive_impacts` under each condition against the sealed impacts:
   does an outage only remove impacts, or can it ground or leave open one no key lists.
4. *Whose unknowns.* The distinct unknown claims (subject and fact) the rules derive for
   the impacts that still ground, split by whether they seed a must-assess candidate's
   assessment.

The worlds are assembled in memory from seeds and hold nothing private; nothing is read
from a bucket and nothing is written but the report on standard output.

Run: `uv run python probes/runtime-truth/probe.py > probes/captures/runtime-truth/forty-seeds.txt`
(seeds 1 to 40 by default; pass seeds as arguments for another set).
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date

from leaveimpact.core.closure import Unresolved
from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.grounding import Grounded, derive_impacts, ground_impact
from leaveimpact.core.plans import expected_action
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import employee_ref
from leaveimpact.core.viability import assess_impact
from leaveimpact.world.assembly import assemble_semantic_world
from leaveimpact.world.construction import derive_expectations, required_count_for
from leaveimpact.world.org import DEFAULT_PARAMS
from leaveimpact.world.runtime_view import runtime_facts, runtime_records
from leaveimpact.world.version import GENERATOR_VERSION

WORLD_START = date(2026, 1, 1)
PLAN = "golden"
NORMAL = RunCondition.all_reachable()
OUTAGES = {f"{source.value}_down": NORMAL.without(source) for source in Source}
CONDITIONS = {"normal": NORMAL} | OUTAGES


def judgment(assessment) -> tuple:
    return (assessment.verdict, assessment.reasons)


def text(verdict, reasons) -> str:
    return f"{verdict.value}{[reason.value for reason in reasons]}"


def main(seeds: list[int]) -> None:
    # 1. Divergence.
    pairs: Counter = Counter()
    differ: Counter = Counter()
    outcomes: Counter = Counter()
    outcomes_differ: Counter = Counter()
    scenarios_hit: Counter = Counter()
    normal_worlds: set[int] = set()
    normal_kinds: Counter = Counter()
    normal_classes: Counter = Counter()
    traces: list[str] = []
    # 2. Outage shape.
    grounding: Counter = Counter()
    verdict_moves: Counter = Counter()
    outcome_moves: Counter = Counter()
    unknowns: Counter = Counter()
    conflicts: Counter = Counter()
    required_and_moved: Counter = Counter()
    # 3. Derived impacts.
    derived_cells: Counter = Counter()
    # 4. Whose unknowns.
    claims: Counter = Counter()
    scenario_count = impact_count = must_count = universe_count = 0

    for seed in seeds:
        world = assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, PLAN)
        universe = [employee.id for employee in world.org.employees]
        owned = [scenario.owned for scenario in world.scenarios]
        authored = [fact for scenario in world.scenarios for fact in scenario.authored_facts]
        briefs = [brief for scenario in world.scenarios for brief in scenario.briefs]
        for scenario in world.scenarios:
            scenario_count += 1
            spec, key = scenario.spec, scenario.key
            leave = scenario.investigated_leave
            today, timezone = spec.today, spec.reference_timezone
            sealed = {expected.key for expected in key.impacts}
            runtime = runtime_facts(
                runtime_records(world.org, owned, spec, briefs), today, authored
            )
            unknowns["normal"] += len(key.expected_unknowns)
            conflicts["normal"] += len(key.expected_conflicts)
            for expected in key.impacts:
                impact_count += 1
                must_count += len(expected.must_assess)
                universe_count += len(universe)

            for name, condition in CONDITIONS.items():
                dated_view = world.facts.at(today, condition)
                view = runtime.at(today, condition)
                hit = moved = False
                still_grounded = []
                for expected in key.impacts:
                    must = {a.employee_id for a in expected.must_assess}
                    args = (expected.key, universe, key.constraints, leave.span, timezone)
                    dated = assess_impact(dated_view, *args)
                    live = assess_impact(view, *args)

                    # 1. Divergence between the views.
                    for old, new in zip(dated, live, strict=True):
                        group = "must_assess" if old.employee_id in must else "extra"
                        pairs[(name, group)] += 1
                        if judgment(old) == judgment(new):
                            continue
                        differ[(name, group)] += 1
                        hit = True
                        if name == "normal":
                            normal_worlds.add(seed)
                            flips = old.verdict is not new.verdict
                            normal_kinds["verdict flips" if flips else "reasons only"] += 1
                            normal_classes[key.scenario_class.value] += 1
                        elif group == "must_assess":
                            skills = [
                                f"{fact.value} from {fact.source.value}:"
                                f"{fact.evidence.target.id} observable {fact.observable_from}"
                                for fact in world.facts.facts
                                if fact.subject == employee_ref(old.employee_id)
                                and fact.predicate is PredicateName.HAS_SKILL
                            ]
                            traces.append(
                                f"seed {seed} {key.scenario_id} [{key.scenario_class.value}] "
                                f"{name}, run day {today}, {old.employee_id} on "
                                f"{expected.key.artifact.id}: dated {text(*judgment(old))} "
                                f"(open: {[(u.predicate.value, u.reason.value) for u in old.unresolved]})"
                                f" vs runtime {text(*judgment(new))}; the candidate's skill "
                                f"facts in the dated base: {skills}"
                            )
                    rest = (expected.key, key.constraints, leave.span, timezone)
                    dated_outcome = expected_action(
                        (a.verdict for a in dated), required_count_for(dated_view, *rest)
                    )
                    live_outcome = expected_action(
                        (a.verdict for a in live), required_count_for(view, *rest)
                    )
                    outcomes[name] += 1
                    if dated_outcome is not live_outcome:
                        outcomes_differ[name] += 1
                        hit = True

                    # 2. Outage shape, over the runtime view.
                    grounded = ground_impact(
                        view, expected.key, leave.employee_id, leave.span, timezone
                    )
                    if isinstance(grounded, Grounded):
                        still_grounded.append(expected)
                    if name == "normal":
                        continue
                    state = (
                        "grounded"
                        if isinstance(grounded, Grounded)
                        else "unresolved"
                        if isinstance(grounded, Unresolved)
                        else "ungrounded"
                    )
                    grounding[(name, state)] += 1
                    moved = moved or state != "grounded"
                    by_employee = {a.employee_id: a for a in live}
                    for sealed_verdict in expected.must_assess:
                        actual = by_employee[sealed_verdict.employee_id]
                        same = judgment(actual) == (sealed_verdict.verdict, sealed_verdict.reasons)
                        label = (
                            "same"
                            if same
                            else f"{sealed_verdict.verdict.value}->{actual.verdict.value}"
                        )
                        verdict_moves[(name, label)] += 1
                        moved = moved or not same
                    label = (
                        "same"
                        if live_outcome is expected.outcome
                        else f"{expected.outcome.value}->{live_outcome.value}"
                    )
                    outcome_moves[(name, label)] += 1
                    moved = moved or live_outcome is not expected.outcome
                if hit:
                    scenarios_hit[name] += 1

                # 3. Derived impacts against the sealed ones.
                derived = derive_impacts(
                    view, spec.leave_id, leave.employee_id, leave.span, timezone
                )
                grounded_keys = set(derived.grounded)
                open_keys = {impact for impact, _ in derived.unresolved}
                derived_cells[(name, "sealed, grounded")] += len(sealed & grounded_keys)
                derived_cells[(name, "sealed, listed unresolved")] += len(sealed & open_keys)
                derived_cells[(name, "sealed, not listed")] += len(
                    sealed - grounded_keys - open_keys
                )
                derived_cells[(name, "new grounded")] += len(grounded_keys - sealed)
                derived_cells[(name, "new unresolved")] += len(open_keys - sealed)

                # 4. Whose unknowns, over the impacts that still ground.
                if not still_grounded:
                    claims[(name, "scenarios with no grounded impact")] += 1
                else:
                    must = {a.employee_id for e in still_grounded for a in e.must_assess}
                    over_grounded = derive_expectations(
                        view,
                        still_grounded,
                        key.constraints,
                        leave.employee_id,
                        leave.span,
                        timezone,
                        universe,
                    )
                    everyone = {(u.subject, u.required_fact) for u in over_grounded.unknowns}
                    seeding = {
                        (u.subject, u.required_fact)
                        for u in over_grounded.unknowns
                        if u.employee_id in must
                    }
                    claims[(name, "distinct unknown claims")] += len(everyone)
                    claims[(name, "seeding a must-assess candidate")] += len(seeding)
                    claims[(name, "seeding only other colleagues")] += len(everyone - seeding)

                if name == "normal":
                    continue
                # 2, continued: the rules' unknowns and conflicts over every sealed impact,
                # and whether the key's required sources predicted the movement.
                over_sealed = derive_expectations(
                    view,
                    key.impacts,
                    key.constraints,
                    leave.employee_id,
                    leave.span,
                    timezone,
                    universe,
                )
                unknowns[name] += len(over_sealed.unknowns)
                conflicts[name] += len(over_sealed.conflicts)
                moved = moved or over_sealed.conflicts != key.expected_conflicts
                source = Source(name.removesuffix("_down"))
                needed = "required" if source in key.required_sources else "not required"
                required_and_moved[(needed, "moved" if moved else "nothing moved")] += 1

    print(f"runtime truth, measured on the {PLAN} plan under generator version {GENERATOR_VERSION}")
    print(f"seeds {seeds[0]}..{seeds[-1]} ({len(seeds)} worlds), scenarios {scenario_count}, "
          f"impacts {impact_count}, must-assess pairs {must_count} "
          f"({must_count / impact_count:.2f} per impact), organization "
          f"{universe_count / impact_count:.0f} per impact")

    print("\n1. Divergence between the dated and the runtime view")
    print(f"{'condition':<15}{'must-assess':>22}{'extra':>22}{'outcomes':>18}{'scenarios':>14}")
    for name in CONDITIONS:
        print(
            f"{name:<15}"
            f"{differ[(name, 'must_assess')]:>8} of {pairs[(name, 'must_assess')]:<10}"
            f"{differ[(name, 'extra')]:>8} of {pairs[(name, 'extra')]:<10}"
            f"{outcomes_differ[name]:>6} of {outcomes[name]:<8}"
            f"{scenarios_hit[name]:>5} of {scenario_count}"
        )
    print(f"normal condition: {len(normal_worlds)} of {len(seeds)} worlds hold a difference; "
          f"{dict(normal_kinds)}; by class {dict(sorted(normal_classes.items()))}")
    print("must-assess differences under an outage, traced:")
    for line in traces or ["  none"]:
        print(f"  {line}")

    def table(title: str, counter: Counter) -> None:
        print(f"\n{title}")
        for name in OUTAGES:
            row = {label: count for (cond, label), count in counter.items() if cond == name}
            cells = ", ".join(f"{k} {v}" for k, v in sorted(row.items(), key=lambda kv: -kv[1]))
            print(f"  {name:<15}{cells}")

    print("\n2. Outage shape, the rules over the runtime view")
    table("sealed impacts asked by their exact key", grounding)
    table("must-assess verdicts (sealed -> under the outage)", verdict_moves)
    table("outcomes (sealed -> under the outage)", outcome_moves)
    print("\nunknowns and conflicts the rules derive over every sealed impact")
    for name in CONDITIONS:
        print(f"  {name:<15}unknowns {unknowns[name]:>6}   conflicts {conflicts[name]:>4}")
    print("\nis the downed source in the key's required sources, and did anything move")
    for (needed, what), count in sorted(required_and_moved.items()):
        print(f"  {needed:<13}{what:<15}{count}")

    print("\n3. derive_impacts against the sealed impacts")
    columns = ["sealed, grounded", "sealed, listed unresolved", "sealed, not listed",
               "new grounded", "new unresolved"]
    print(f"{'condition':<15}" + "".join(f"{column:>27}" for column in columns))
    for name in CONDITIONS:
        print(f"{name:<15}" + "".join(f"{derived_cells[(name, c)]:>27}" for c in columns))

    print("\n4. Whose the unknowns are, over the impacts that still ground")
    columns = ["distinct unknown claims", "seeding a must-assess candidate",
               "seeding only other colleagues", "scenarios with no grounded impact"]
    print(f"{'condition':<15}" + "".join(f"{column:>35}" for column in columns))
    for name in CONDITIONS:
        print(f"{name:<15}" + "".join(f"{claims[(name, c)]:>35}" for c in columns))


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]] or list(range(1, 41)))
