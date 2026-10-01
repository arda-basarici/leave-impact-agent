"""The grounding replay's basis: what a run must read for the rules to reproduce its claims.

A measurement, not a pass-or-fail probe: it has no criterion, it produced the numbers four
rulings of the investigator milestone's fourth build step were made on (the stream's
`m2-build/2026-10-02-step-4-rulings.md`, rulings 1, 2, 3 and 5). It was first run on
2026-10-02 from seven scratch scripts, one question at a time, while the rulings were
being argued; this file is the same computation in one pass per world, committed with its
capture so the numbers are regenerable from recorded inputs: the seeds, the golden plan,
the default organization, the generator version the run prints.

The grounding replay asks whether the rules, fed only what a run's completed reads
returned, conclude what the report claims. Five questions about the worlds decide what
that replay has to be:

1. *Where prose-only facts live.* `core`'s derivation makes facts from structured records
   and nothing from prose. Every authored fact by predicate, source and carrier kind: if
   all of them sit on comments and clauses, a view built from records alone grounds no
   claim that rests on prose, and the view needs a gate that admits a sealed fact when
   its carrier was read.
2. *How much rests on a negative.* The sealed must-assess verdicts by verdict and reasons.
   Closure infers "known false" from reachability; a view holding only what a run read
   would turn every unread record into a negative, so the share of verdicts that need one
   says how much the coverage rule touches.
3. *Whether a constraint's scope can be admitted through its clause.* The fact base holds
   what a clause requires and nothing about what it applies to. The sealed constraint
   pairings against the authored `requires` facts: the same clauses, one target each, and
   one section in the document behind a clause-kind target, or the pairing is not a
   function of the clause.
4. *What the sealed role tags cover.* The carriers of authored facts, how many a brief
   tags answer-changing, and the required sources per scenario. The tags are derived for
   model-written text only, so a retrieval target read off them would miss the
   class-written requirement clauses.
5. *Which unit of prose moves the answer.* Over the runtime view, normal condition, three
   removals compared with the scenario's unablated conclusions: each of its carriers (the
   facts it holds, and the scope pairing of a requirement clause); each of its authored
   facts alone, the carrier's other facts kept; each of its statements on every carrier
   in the world. A carrier that moves nothing is traced to the other carrier of its
   statement. And a requirement fact removed with its constraint kept, which the rules
   refuse.

Question 5 imports `world.construction._conclusions`, a private name, on purpose. That
tuple is the generator's own definition of "the conclusions moved" (the role derivation
and the required-sources derivation both compare it), so the measurement is what the
sealed tags would have said had they been derived over the runtime view. The evaluator's
retrieval targets are defined on the oracle's complete answer and not on this tuple; a
public entry in `world.construction` for one measurement would widen that module for
nothing the package uses.

The worlds are assembled in memory from seeds and hold nothing private; nothing is read
from a bucket and nothing is written but the report on standard output.

Run: `uv run python probes/grounding-basis/probe.py > probes/captures/grounding-basis/twenty-seeds.txt`
from a POSIX shell (Windows PowerShell 5.1 redirects as UTF-16). Seeds 1 to 20 by
default; pass seeds as arguments for another set.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import date

from leaveimpact.core.claims import AssessmentReason, Verdict
from leaveimpact.core.enums import Source
from leaveimpact.core.facts import Fact, RunCondition
from leaveimpact.core.predicates import PredicateName
from leaveimpact.world.assembly import assemble_semantic_world
from leaveimpact.world.briefs import SectionTarget
from leaveimpact.world.construction import _conclusions
from leaveimpact.world.org import DEFAULT_PARAMS
from leaveimpact.world.prose import FactRole
from leaveimpact.world.runtime_view import runtime_facts, runtime_records
from leaveimpact.world.version import GENERATOR_VERSION

WORLD_START = date(2026, 1, 1)
PLAN = "golden"
NORMAL = RunCondition.all_reachable()


def statement_of(fact: Fact) -> tuple:
    """What a fact says, whatever carries it: the unit a second carrier can restate."""
    return (fact.subject, fact.predicate, fact.value)


def verdict_group(verdict: Verdict, reasons: tuple[AssessmentReason, ...]) -> str:
    """The negative a sealed verdict rests on, the widest domain first: a skill negative
    needs three sources closed, an availability one a window, a component one a record."""
    if verdict is not Verdict.NON_VIABLE:
        return verdict.value
    if AssessmentReason.SKILL in reasons:
        return "non_viable, skill among the reasons"
    if AssessmentReason.AVAILABILITY in reasons:
        return "non_viable, availability among the reasons"
    if reasons == (AssessmentReason.COMPONENT,):
        return "non_viable, component only"
    return "non_viable, " + "+".join(sorted(reason.value for reason in reasons))


def spread(counter: Counter) -> str:
    return ", ".join(f"{key}: {count}" for key, count in sorted(counter.items()))


def main(seeds: list[int]) -> None:
    scenario_count = 0
    # 1. Where prose-only facts live.
    authored_rows: Counter = Counter()
    off_prose_scenarios = 0
    # 2. How much rests on a negative.
    verdict_rows: Counter = Counter()
    verdict_groups: Counter = Counter()
    skill_by_tier: Counter = Counter()
    # 3. Constraints against requires facts.
    requires_facts = pairings = same_clauses = 0
    constraints_per_scenario: Counter = Counter()
    target_kinds: Counter = Counter()
    targets_per_clause: Counter = Counter()
    sections_behind_target: Counter = Counter()
    targets_per_document: Counter = Counter()
    # 4. Carriers, role tags, required sources.
    carriers: Counter = Counter()
    carrier_scenarios = 0
    unbriefed = 0
    required_roles: Counter = Counter()
    tagged: Counter = Counter()
    tagged_sections_by_tier: Counter = Counter()
    tier_scenarios: Counter = Counter()
    required_sources: Counter = Counter()
    corpus_required = 0
    # 5. Which carriers and which statements move the answer.
    carrier_moves: Counter = Counter()
    fact_moves: Counter = Counter()
    fact_only: Counter = Counter()
    world_statements: Counter = Counter()
    statement_moves: Counter = Counter()
    traces: list[str] = []

    for seed in seeds:
        world = assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, PLAN)
        owned = [scenario.owned for scenario in world.scenarios]
        authored = [fact for scenario in world.scenarios for fact in scenario.authored_facts]
        briefs = [brief for scenario in world.scenarios for brief in scenario.briefs]

        carriers_of: dict[tuple, set] = {}
        for fact in authored:
            carriers_of.setdefault(statement_of(fact), set()).add(fact.evidence.target)
        for stating in carriers_of.values():
            world_statements[len(stating)] += 1

        targets_of_clause: dict[str, set] = {}
        for scenario in world.scenarios:
            scenario_count += 1
            spec, key, leave = scenario.spec, scenario.key, scenario.investigated_leave
            own = scenario.authored_facts

            # 1. Where prose-only facts live.
            for fact in own:
                kind = fact.evidence.target.kind.value
                authored_rows[(fact.predicate.value, fact.evidence.source.value, kind)] += 1
            off_prose_scenarios += any(
                fact.evidence.target.kind.value not in ("comment", "clause") for fact in own
            )

            # 2. How much rests on a negative.
            for expected in key.impacts:
                for sealed in expected.must_assess:
                    reasons = "+".join(sorted(r.value for r in sealed.reasons)) or "-"
                    verdict_rows[(sealed.verdict.value, reasons)] += 1
                    verdict_groups[verdict_group(sealed.verdict, sealed.reasons)] += 1
                    if AssessmentReason.SKILL in sealed.reasons:
                        skill_by_tier[key.tier.value] += 1

            # 3. Constraints against requires facts.
            stated = [fact for fact in own if fact.predicate is PredicateName.REQUIRES]
            requires_facts += len(stated)
            pairings += len(key.constraints)
            constraints_per_scenario[len(key.constraints)] += 1
            same_clauses += sorted(fact.subject.id for fact in stated) == sorted(
                constraint.clause_id for constraint in key.constraints
            )
            # A clause-kind target is a section a brief leaves pending, absent from the
            # owned documents until the prose is written: the briefs say where it will sit.
            document_of: dict[str, str] = {}
            sections_in: Counter = Counter()
            for planted in scenario.owned.documents:
                for section in planted.entity.sections:
                    document_of[section.id] = planted.entity.id
                    sections_in[planted.entity.id] += 1
            for brief in scenario.briefs:
                if isinstance(brief.target, SectionTarget):
                    document_of[brief.target.id] = brief.target.document_id
                    sections_in[brief.target.document_id] += 1
            scoped_in: Counter = Counter()
            for constraint in key.constraints:
                target = constraint.applies_to
                target_kinds[target.kind.value] += 1
                targets_of_clause.setdefault(constraint.clause_id, set()).add(target)
                if target.kind.value == "clause":
                    document = document_of[target.id]
                    sections_behind_target[sections_in[document]] += 1
                    scoped_in[document] += 1
            for count in scoped_in.values():
                targets_per_document[count] += 1

            # 4. Carriers, role tags, required sources.
            tier_scenarios[key.tier.value] += 1
            required_sources[tuple(sorted(s.value for s in key.required_sources))] += 1
            corpus_required += Source.CORPUS in key.required_sources
            briefed = set()
            tagged_sections = 0
            for brief in scenario.briefs:
                kind = "clause" if isinstance(brief.target, SectionTarget) else "comment"
                for required in brief.required:
                    briefed.add(required.fact)
                    required_roles[(kind, required.role.value)] += 1
                if any(r.role is FactRole.ANSWER_CHANGING for r in brief.required):
                    tagged[kind] += 1
                    tagged_sections += kind == "clause"
            tagged_sections_by_tier[(key.tier.value, tagged_sections)] += 1
            unbriefed += sum(fact not in briefed for fact in own)
            own_carriers = sorted(
                {fact.evidence.target for fact in own}, key=lambda ref: (ref.kind.value, ref.id)
            )
            carrier_scenarios += bool(own_carriers)

            # 5. Which carriers and which statements move the answer.
            records = runtime_records(world.org, owned, spec, briefs)

            def concluded(facts, constraints, records=records, scenario=scenario):
                spec, key, leave = scenario.spec, scenario.key, scenario.investigated_leave
                view = runtime_facts(records, spec.today, facts).at(spec.today, NORMAL)
                return _conclusions(
                    view,
                    key.impacts,
                    constraints,
                    spec.leave_id,
                    leave.employee_id,
                    leave.span,
                    spec.reference_timezone,
                    world.org,
                )

            baseline = concluded(authored, key.constraints) if own else None
            for carrier in own_carriers:
                kind = carrier.kind.value
                carried = [fact for fact in own if fact.evidence.target == carrier]
                requirement = any(fact.predicate is PredicateName.REQUIRES for fact in carried)
                carriers[(kind, "requirement" if requirement else "other")] += 1
                remaining = [fact for fact in authored if fact.evidence.target != carrier]
                unpaired = tuple(c for c in key.constraints if c.clause_id != carrier.id)
                moved = concluded(remaining, unpaired) != baseline
                carrier_moves[(kind, "moved" if moved else "moved nothing")] += 1
                if requirement:
                    try:
                        concluded(remaining, key.constraints)
                        fact_only["concluded"] += 1
                    except ValueError as problem:
                        fact_only["raised: " + str(problem).split(" ", 1)[1]] += 1
                if moved:
                    continue
                traces.append(
                    f"seed {seed} {key.scenario_id} [{key.scenario_class.value}, run day "
                    f"{spec.today}] {carrier.id} moves nothing"
                )
                structured = runtime_facts(records, spec.today, ()).facts
                for fact in carried:
                    elsewhere = [
                        f"{other.source.value}:{other.evidence.target.id} of "
                        f"{owner.key.scenario_id}, run day {owner.spec.today}"
                        for owner in world.scenarios
                        for other in owner.authored_facts
                        if statement_of(other) == statement_of(fact)
                        and other.evidence.target != carrier
                    ]
                    in_records = [
                        other.evidence.target.id
                        for other in structured
                        if statement_of(other) == statement_of(fact)
                    ]
                    traces.append(
                        f"   carries {fact.predicate.value}({fact.subject.id}) = {fact.value}; "
                        f"the same statement on other carriers: {elsewhere}; in structured "
                        f"records: {in_records}"
                    )

            for fact in own:
                remaining = [other for other in authored if other != fact]
                clause = fact.subject.id if fact.predicate is PredicateName.REQUIRES else None
                unpaired = tuple(c for c in key.constraints if c.clause_id != clause)
                moved = concluded(remaining, unpaired) != baseline
                fact_moves["moved" if moved else "moved nothing"] += 1

            seen: set[tuple] = set()
            for fact in own:
                statement = statement_of(fact)
                if statement in seen:
                    continue
                seen.add(statement)
                remaining = [other for other in authored if statement_of(other) != statement]
                clause = fact.subject.id if fact.predicate is PredicateName.REQUIRES else None
                unpaired = tuple(c for c in key.constraints if c.clause_id != clause)
                moved = concluded(remaining, unpaired) != baseline
                statement_moves[
                    (len(carriers_of[statement]), "moved" if moved else "moved nothing")
                ] += 1

        for targets in targets_of_clause.values():
            targets_per_clause[len(targets)] += 1

    print(
        f"the grounding replay's basis, measured on the {PLAN} plan under generator "
        f"version {GENERATOR_VERSION}"
    )
    print(f"seeds {seeds[0]}..{seeds[-1]} ({len(seeds)} worlds), scenarios {scenario_count}")

    authored_total = sum(authored_rows.values())
    print("\n1. Where prose-only facts live")
    print(f"authored facts: {authored_total}")
    print(f"  {'predicate':<22}{'source':<10}{'carrier kind':<14}{'count':>6}")
    for (name, source, kind), count in sorted(authored_rows.items()):
        print(f"  {name:<22}{source:<10}{kind:<14}{count:>6}")
    print(
        "scenarios holding an authored fact carried by neither a comment nor a clause: "
        f"{off_prose_scenarios}"
    )

    verdict_total = sum(verdict_rows.values())
    print("\n2. How much rests on a negative")
    print(f"sealed must-assess verdicts: {verdict_total}")
    print(f"  {'verdict':<12}{'reasons':<26}{'count':>6}{'share':>8}")
    for (verdict, reasons), count in sorted(verdict_rows.items()):
        print(f"  {verdict:<12}{reasons:<26}{count:>6}{count / verdict_total:>8.1%}")
    print("grouped by the negative the verdict rests on:")
    for group, count in sorted(verdict_groups.items(), key=lambda row: -row[1]):
        print(f"  {group:<44}{count:>6}{count / verdict_total:>8.1%}")
    print(f"skill among the reasons, by tier: {spread(skill_by_tier)}")

    print("\n3. Constraints against requires facts")
    print(f"authored requires facts: {requires_facts}; sealed constraint pairings: {pairings}")
    print(
        f"scenarios whose constraints and requires facts name the same clauses: "
        f"{same_clauses} of {scenario_count}"
    )
    print(f"constraints per scenario: {spread(constraints_per_scenario)}")
    print(f"targets per clause within a world: {spread(targets_per_clause)}")
    print(f"target kinds: {spread(target_kinds)}")
    print(
        "sections, written and pending, in the document behind a clause-kind target: "
        f"{spread(sections_behind_target)}"
    )
    print(f"clause-kind targets per such document: {spread(targets_per_document)}")

    print("\n4. Carriers, role tags, required sources")
    print(
        f"distinct carriers: {sum(carriers.values())} "
        f"({spread(Counter({f'{kind}, {what}': n for (kind, what), n in carriers.items()}))})"
    )
    print(f"scenarios holding at least one carrier: {carrier_scenarios} of {scenario_count}")
    print(f"scenarios whose required sources include the corpus: {corpus_required}")
    print(
        f"authored facts required by a brief: {authored_total - unbriefed}; by none "
        f"(class-written text): {unbriefed}"
    )
    print(
        "required facts by carrier kind and role: "
        f"{spread(Counter({f'{kind}, {role}': n for (kind, role), n in required_roles.items()}))}"
    )
    print(
        f"carriers a brief tags answer-changing: {sum(tagged.values())} ({spread(tagged)}); "
        f"untagged: {sum(carriers.values()) - sum(tagged.values())}"
    )
    print("tagged sections per scenario, by tier:")
    for (tier, sections), count in sorted(tagged_sections_by_tier.items()):
        print(f"  {tier:<14}{sections} tagged{count:>6} of {tier_scenarios[tier]}")
    print("required sources per scenario:")
    for sources, count in sorted(required_sources.items(), key=lambda row: (-row[1], row[0])):
        print(f"  {', '.join(sources):<34}{count:>5}")

    print("\n5. Which carriers and which statements move the answer (runtime view, normal)")
    print("a carrier removed, its facts and a requirement's scope pairing with it:")
    for (kind, what), count in sorted(carrier_moves.items()):
        print(f"  {kind:<10}{what:<16}{count:>5}")
    print("the carriers that move nothing, traced:")
    for line in traces or ["  none"]:
        print(f"  {line}")
    print(f"a requirement fact removed, its constraint kept: {spread(fact_only)}")
    print(
        "an authored fact removed alone, a requirement's scope pairing with it: "
        f"{spread(fact_moves)}"
    )
    print(
        "distinct statements per world, by the number of carriers stating them: "
        f"{spread(world_statements)} (total {sum(world_statements.values())})"
    )
    print("a scenario's statement removed on every carrier in its world:")
    for (count_of_carriers, what), count in sorted(statement_moves.items()):
        print(f"  on {count_of_carriers} carrier(s)  {what:<16}{count:>5}")


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]] or list(range(1, 21)))
