"""The source-dependence probe: which sources does a class's key require, and does the set
rest on a source none of the class's own artifacts plant? Each remaining Tier 2 and 3
class runs it before the step 8 carry closes at 15.5 (DESIGN, "The responsibility class,
ruled", the second ruling; `probes/FINDINGS.md`, `source-dependence`).

It constructs the class's shape on the unit fixture organization and prints the sealed
key's required sources and verdicts, then re-derives the required set with a foreign
tracker fact added to the truth base, once restating a viable candidate's skill and once
granting the skill to the non-viable one. The responsibility class showed the tracker
required with no tracker artifact planted: a known-negative on a skill needs the HR
record and the tracker both to have answered, so derivation is semantic and not
provenance-based. A foreign fact that moves a verdict is assembly's refusal to seal, not
this script's reading; the required set is. Runs offline, no credentials; a new class
replaces or joins the probe class below with a `plant` that mirrors its production
construction.
"""
import sys
sys.path.insert(0, "tests/unit")
from dataclasses import dataclass
from random import Random
from prose_fixture import (ORG, WORLD_START, WINDOW, TZ, KAFKA, ContactInNote, pending_scenario)
from leaveimpact.core import (
    ConstraintKey, CoverageActionKind, Document, DocumentKind, DocumentSection, EvidenceRef, Fact,
    ImpactKey, ImpactSubtype, Leave, LeaveKind, LeaveStatus, PredicateName, Requirement,
    SkillCriterion, Source, Verdict, clause_ref, comment_ref, employee_ref,
)
from leaveimpact.core.ids import comment_id, scenario_id
from leaveimpact.core.claims import AssessmentReason
from leaveimpact.world import (AuthoredVerdict, Draft, ExpectedImpact, Frame, Minting, OrgSpec,
    OwnedEntities, PendingProse, Planted, ReleaseCardinalityConstraint, ScenarioClassName, SectionTarget,
    Tier, construct)
from leaveimpact.world.construction import required_sources_for
from leaveimpact.world.truth_facts import truth_fact_base


@dataclass(frozen=True)
class ResponsibilityProbe:
    name = ScenarioClassName.FREE_TEXT_RESPONSIBILITY
    tier = Tier.FRAGMENTED
    affordance = "a Kafka holder, a record-holder lacking it, a leaver"

    def admissible(self, org: OrgSpec):
        holders = [e for e in org.holders_of(KAFKA)]
        lacking = [e for e in org.employees if e.skills is not None and e.id not in {h.id for h in holders}]
        viable, other, leaver = holders[0], lacking[0], lacking[1]

        def plant(frame: Frame, rng: Random) -> Draft:
            visible = frame.window.start
            leave = Leave(frame.ids.leave(), leaver.id, frame.leave.start, frame.leave.end,
                          LeaveKind.ANNUAL, LeaveStatus.APPROVED)
            section = frame.ids.clause()
            note = Document(frame.ids.document(), "Acme account notes", DocumentKind.CLIENT_NOTE, visible, ())
            names = Fact(clause_ref(section), PredicateName.NAMES_RESPONSIBLE, employee_ref(leaver.id),
                         EvidenceRef(Source.CORPUS, clause_ref(section)), visible)
            clause = frame.ids.clause()
            procedure = Document(frame.ids.document(), "Account handover procedure: Acme", DocumentKind.PROCEDURE,
                                 visible, (DocumentSection(clause, "The Acme account's contact needs Kafka experience."),))
            requires = Fact(clause_ref(clause), PredicateName.REQUIRES, Requirement(1, (SkillCriterion(KAFKA),)),
                            EvidenceRef(Source.CORPUS, clause_ref(clause)), visible)
            impact = ImpactKey(leave.id, ImpactSubtype.RESPONSIBILITY, clause_ref(section))
            expected = ExpectedImpact(impact, CoverageActionKind.ASSIGN, (
                AuthoredVerdict(viable.id, Verdict.VIABLE),
                AuthoredVerdict(other.id, Verdict.NON_VIABLE, (AssessmentReason.SKILL,)),
            ))
            owned = OwnedEntities(leaves=(Planted(leave, visible),),
                                  documents=(Planted(note, visible), Planted(procedure, visible)))
            return Draft(owned, leave.id, (expected,),
                         constraints=(ConstraintKey(clause, clause_ref(section)),),
                         authored_facts=(requires, names),
                         pending=(PendingProse(SectionTarget(section, note.id, 0), (names,)),))
        return (plant,)

def build(cls):
    return construct(cls, [], ORG, scenario_id=scenario_id(1), window=WINDOW, world_start=WORLD_START,
                     reference_timezone=TZ, ids=Minting(), rng=Random(1))

def required(scn, extra=()):
    base = truth_fact_base(ORG, WORLD_START, [scn.owned], (*scn.authored_facts, *extra))
    leaver = scn.owned.leaves[0].entity.employee_id
    frame_leave = scn.owned.leaves[0].entity
    from leaveimpact.core import DateSpan
    span = DateSpan(frame_leave.start, frame_leave.end)
    return sorted(s.value for s in required_sources_for(base, scn.spec.today, scn.key.impacts, scn.key.constraints,
                                                       span, TZ, ORG, scn.spec.leave_id, leaver))

print("== fixture ContactInNote (no clause) ==")
c = build(ContactInNote())
print("required_sources:", [s.value for s in c.key.required_sources])
print("verdicts:", [(v.employee_id, v.verdict.value, [r.value for r in v.reasons]) for i in c.key.impacts for v in i.must_assess])

print("\n== responsibility probe (clause on the section, viable + skill-failing) ==")
r = build(ResponsibilityProbe())
print("required_sources:", [s.value for s in r.key.required_sources])
for i in r.key.impacts:
    print("impact:", i.key.subtype.value, i.key.artifact.id, "outcome:", i.outcome.value)
    for v in i.must_assess:
        print("  ", v.employee_id, v.verdict.value, [x.value for x in v.reasons])
viable_id = [v.employee_id for i in r.key.impacts for v in i.must_assess if v.verdict is Verdict.VIABLE][0]
other_id = [v.employee_id for i in r.key.impacts for v in i.must_assess if v.verdict is Verdict.NON_VIABLE][0]
visible = WINDOW.start

print("\n-- foreign Jira comment evidencing the VIABLE candidate's Kafka (already on HR record) --")
foreign_v = Fact(employee_ref(viable_id), PredicateName.HAS_SKILL, KAFKA, EvidenceRef(Source.JIRA, comment_ref(comment_id(999))), visible)
print("required_sources:", required(r, (foreign_v,)))

print("\n-- foreign Jira comment giving the NON-VIABLE candidate Kafka --")
foreign_o = Fact(employee_ref(other_id), PredicateName.HAS_SKILL, KAFKA, EvidenceRef(Source.JIRA, comment_ref(comment_id(998))), visible)
print("required_sources:", required(r, (foreign_o,)))

print("\n== cardinality class (15.3): a release ticket, a two-person clause with skill and employment ==")
c = build(ReleaseCardinalityConstraint())
print("required_sources:", [s.value for s in c.key.required_sources])
for i in c.key.impacts:
    print("impact:", i.key.subtype.value, i.key.artifact.id, "outcome:", i.outcome.value)
    for v in i.must_assess:
        print("  ", v.employee_id, v.verdict.value, [x.value for x in v.reasons])
skill = [crit.skill for f in c.authored_facts for crit in f.value.criteria if hasattr(crit, "skill")][0]
holder = [v.employee_id for i in c.key.impacts for v in i.must_assess if v.verdict is Verdict.VIABLE][0]
lacking = [v.employee_id for i in c.key.impacts for v in i.must_assess
           if v.verdict is Verdict.NON_VIABLE and AssessmentReason.SKILL in v.reasons][0]
print("-- foreign Jira comment restating a viable holder's skill --")
print("required_sources:", required(c, (Fact(employee_ref(holder), PredicateName.HAS_SKILL, skill,
      EvidenceRef(Source.JIRA, comment_ref(comment_id(999))), WINDOW.start),)))
print("-- foreign Jira comment giving the skill-failing candidate the skill (a verdict moves) --")
print("required_sources:", required(c, (Fact(employee_ref(lacking), PredicateName.HAS_SKILL, skill,
      EvidenceRef(Source.JIRA, comment_ref(comment_id(998))), WINDOW.start),)))

print("\n== composite class (15.4): the note's section names the contact and provides the cover's skill ==")
from leaveimpact.world import FragmentedComposite
from leaveimpact.core.ids import clause_id
f = build(FragmentedComposite())
print("required_sources:", [s.value for s in f.key.required_sources])
for i in f.key.impacts:
    print("impact:", i.key.subtype.value, i.key.artifact.id, "outcome:", i.outcome.value)
    for v in i.must_assess:
        print("  ", v.employee_id, v.verdict.value, [x.value for x in v.reasons])
skill = [crit.skill for x in f.authored_facts for crit in getattr(x.value, "criteria", ()) if hasattr(crit, "skill")][0]
cover = [v.employee_id for i in f.key.impacts for v in i.must_assess if v.verdict is Verdict.VIABLE][0]
failing = [v.employee_id for i in f.key.impacts for v in i.must_assess
           if v.verdict is Verdict.NON_VIABLE and AssessmentReason.SKILL in v.reasons][0]
print("-- foreign Jira comment restating the cover's skill (the note already provides it) --")
print("required_sources:", required(f, (Fact(employee_ref(cover), PredicateName.HAS_SKILL, skill,
      EvidenceRef(Source.JIRA, comment_ref(comment_id(999))), WINDOW.start),)))
print("-- foreign Jira comment giving the failing candidate the skill (a verdict moves) --")
print("required_sources:", required(f, (Fact(employee_ref(failing), PredicateName.HAS_SKILL, skill,
      EvidenceRef(Source.JIRA, comment_ref(comment_id(998))), WINDOW.start),)))
print("-- foreign corpus section giving the failing candidate the skill, the route the composite opened (a verdict moves) --")
print("required_sources:", required(f, (Fact(employee_ref(failing), PredicateName.HAS_SKILL, skill,
      EvidenceRef(Source.CORPUS, clause_ref(clause_id(999))), WINDOW.start),)))

print("\n== stale conflict class (15.5): the deadline cast, a runbook section naming the outsider as owner ==")
# A second document naming any owner for the same ticket is not a world the fact base admits
# (one value per source and key), so that class of foreign fact is excluded by construction;
# the perturbations left are facts of other predicates around the graded people.
from leaveimpact.world import StaleSourceConflict
from leaveimpact.core import work_item_ref
k = build(StaleSourceConflict())
print("required_sources:", [s.value for s in k.key.required_sources])
for i in k.key.impacts:
    print("impact:", i.key.subtype.value, i.key.artifact.id, "outcome:", i.outcome.value)
    for v in i.must_assess:
        print("  ", v.employee_id, v.verdict.value, [x.value for x in v.reasons])
print("expected_conflicts:", [(c.entity.id, c.predicate.value, c.resolved_value.id, c.authority_rule.value) for c in k.key.expected_conflicts])
outsider_id = [v.employee_id for i in k.key.impacts for v in i.must_assess if v.verdict is Verdict.NON_VIABLE][0]
print("-- foreign Jira comment giving the outsider a skill (no clause asks one) --")
print("required_sources:", required(k, (Fact(employee_ref(outsider_id), PredicateName.HAS_SKILL, KAFKA,
      EvidenceRef(Source.JIRA, comment_ref(comment_id(997))), WINDOW.start),)))
print("-- foreign Jira comment giving the cover a skill (no clause asks one) --")
cover_id = [v.employee_id for i in k.key.impacts for v in i.must_assess if v.verdict is Verdict.VIABLE][0]
print("required_sources:", required(k, (Fact(employee_ref(cover_id), PredicateName.HAS_SKILL, KAFKA,
      EvidenceRef(Source.JIRA, comment_ref(comment_id(996))), WINDOW.start),)))
