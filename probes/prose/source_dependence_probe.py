"""Q2 probe: the responsibility class's required sources, with and without a foreign fact."""
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
    OwnedEntities, PendingProse, Planted, ScenarioClassName, SectionTarget, Tier, construct)
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
from leaveimpact.world.construction import _verify
base = truth_fact_base(ORG, WORLD_START, [r.owned], (*r.authored_facts, foreign_o))
print("(a verdict moves? checked separately by assembly; see problems below)")
