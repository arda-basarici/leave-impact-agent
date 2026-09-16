"""The silent-drift probe: can a foreign fact change a class's required-source set while
every ordinary conclusion stays the same? Each remaining Tier 2 and 3 class runs it before
the step 8 carry closes at 15.5 (DESIGN, "The responsibility class, ruled", the second
ruling; `probes/FINDINGS.md`, `source-dependence`).

For each fixture class it builds the pending scenario, derives the conclusions tuple
(groundings, assessments, open questions, outcomes, conflicts) and the required-source
set under every source reachable, then adds one foreign fact at a time around the
candidate, a tracker comment restating a skill and a tracker ticket the candidate owns
due inside the leave, and prints whether the conclusions moved and what the required
set became. Drift is a required set that changed with the conclusions unchanged; the
argument that no current class can produce it rests on provenance pinning every
artifact's source and on the tracker entering only through a moved verdict, which is why
a run on a new class is evidence and not a proof. Runs offline on the unit fixtures
(`tests/unit/prose_fixture.py`), no credentials; a new class is added to the list at the
bottom with a construction that plants its shape.
"""
import sys
sys.path.insert(0, "tests/unit")
from datetime import timedelta
from prose_fixture import ORG, WORLD_START, TZ, KAFKA, SkillInComment, ContactInNote, pending_scenario
from leaveimpact.core import (DateSpan, EvidenceRef, Fact, PredicateName, Source, WorkItem, WorkItemStatus,
    employee_ref, comment_ref, work_item_ref)
from leaveimpact.core.ids import comment_id, work_item_id
from leaveimpact.core.facts import RunCondition
from leaveimpact.world import Minting, OwnedEntities, Planted, ReleaseCardinalityConstraint, construct
from leaveimpact.core.ids import scenario_id
from leaveimpact.core import Verdict
from random import Random
from prose_fixture import WINDOW
from leaveimpact.world.construction import required_sources_for, _conclusions
from leaveimpact.world.truth_facts import truth_fact_base

def study(scn, label, extra_facts=(), extra_owned=()):
    leave = scn.owned.leaves[0].entity
    span = DateSpan(leave.start, leave.end)
    base = truth_fact_base(ORG, WORLD_START, [scn.owned, *extra_owned], (*scn.authored_facts, *extra_facts))
    normal = base.at(scn.spec.today, RunCondition.all_reachable())
    concl = _conclusions(normal, scn.key.impacts, scn.key.constraints, scn.spec.leave_id, leave.employee_id, span, TZ, ORG)
    req = sorted(s.value for s in required_sources_for(base, scn.spec.today, scn.key.impacts, scn.key.constraints, span, TZ, ORG, scn.spec.leave_id, leave.employee_id))
    return concl, req

for cls, name in [(SkillInComment(), "qualification (skill only in a Jira comment)"), (ContactInNote(), "contact-in-note (no clause)")]:
    scn = pending_scenario(cls)
    cand = [v.employee_id for i in scn.key.impacts for v in i.must_assess][0]
    visible = scn.spec.window.start
    c0, r0 = study(scn, "base")
    print(f"== {name}: required {r0}")
    fj = Fact(employee_ref(cand), PredicateName.HAS_SKILL, KAFKA, EvidenceRef(Source.JIRA, comment_ref(comment_id(999))), visible)
    c1, r1 = study(scn, "x", (fj,))
    print(f"   + foreign Jira comment, candidate has Kafka: conclusions same={c1==c0}, required {r1}")
    ticket = WorkItem(work_item_id(999), "Foreign ticket", cand, WorkItemStatus.IN_PROGRESS, ORG.components[0].id, visible, None, scn.owned.leaves[0].entity.start + timedelta(days=1), ())
    c2, r2 = study(scn, "y", (), (OwnedEntities(work_items=(Planted(ticket, visible),)),))
    print(f"   + foreign Jira ticket owned by the candidate, due in the leave: conclusions same={c2==c0}, required {r2}")


# The cardinality class (15.3): the failing candidate's skill is the fact a foreign tracker
# comment can move, and moving it moves a verdict, so nothing here is silent by construction;
# the holders' skills restated change nothing, and a foreign ticket on a holder is outside
# the key's reading (a candidate's own workload is not a criterion).
scn = construct(ReleaseCardinalityConstraint(), [], ORG, scenario_id=scenario_id(1), window=WINDOW,
                world_start=WORLD_START, reference_timezone=TZ, ids=Minting(), rng=Random(1))
skill = [c.skill for f in scn.authored_facts for c in f.value.criteria if hasattr(c, "skill")][0]
[expected] = scn.key.impacts
viable = [v.employee_id for v in expected.must_assess if v.verdict is Verdict.VIABLE]
failing = [v.employee_id for v in expected.must_assess if v.verdict is Verdict.NON_VIABLE and "skill" in [r.value for r in v.reasons]][0]
visible = scn.spec.window.start
c0, r0 = study(scn, "base")
print(f"== cardinality (ticket + two-person clause): required {r0}")
for who, label in ((viable[0], "a viable holder"), (failing, "the skill-failing candidate")):
    fj = Fact(employee_ref(who), PredicateName.HAS_SKILL, skill, EvidenceRef(Source.JIRA, comment_ref(comment_id(999))), visible)
    c1, r1 = study(scn, "x", (fj,))
    print(f"   + foreign Jira comment, {label} has the skill: conclusions same={c1==c0}, required {r1}")
ticket = WorkItem(work_item_id(999), "Foreign ticket", viable[0], WorkItemStatus.IN_PROGRESS, ORG.components[0].id, visible, None, scn.owned.leaves[0].entity.start + timedelta(days=1), ())
c2, r2 = study(scn, "y", (), (OwnedEntities(work_items=(Planted(ticket, visible),)),))
print(f"   + foreign Jira ticket owned by a viable holder, due in the leave: conclusions same={c2==c0}, required {r2}")


# The composite (15.4): the section carries the contact naming and the cover's skill, so a
# corpus outage removes the impact and the cover's qualification together; the failing
# candidate's known-negative is the one fact a foreign positive can move, and moving it
# moves a verdict, over the tracker route and over the corpus route the class opened.
from leaveimpact.world import FragmentedComposite
from leaveimpact.core import clause_ref
from leaveimpact.core.ids import clause_id
scn = construct(FragmentedComposite(), [], ORG, scenario_id=scenario_id(1), window=WINDOW,
                world_start=WORLD_START, reference_timezone=TZ, ids=Minting(), rng=Random(1))
skill = [c.skill for f in scn.authored_facts for c in getattr(f.value, "criteria", ()) if hasattr(c, "skill")][0]
[expected] = scn.key.impacts
cover = [v.employee_id for v in expected.must_assess if v.verdict is Verdict.VIABLE][0]
failing = [v.employee_id for v in expected.must_assess if v.verdict is Verdict.NON_VIABLE and "skill" in [r.value for r in v.reasons]][0]
visible = scn.spec.window.start
c0, r0 = study(scn, "base")
print(f"== composite (section: contact + the cover's skill; procedure clause): required {r0}")
for who, label, source, ref in (
    (cover, "the cover", Source.JIRA, comment_ref(comment_id(999))),
    (failing, "the failing candidate", Source.JIRA, comment_ref(comment_id(998))),
    (failing, "the failing candidate", Source.CORPUS, clause_ref(clause_id(999))),
):
    fj = Fact(employee_ref(who), PredicateName.HAS_SKILL, skill, EvidenceRef(source, ref), visible)
    c1, r1 = study(scn, "x", (fj,))
    print(f"   + foreign {source.value} fact, {label} has the skill: conclusions same={c1==c0}, required {r1}")
ticket = WorkItem(work_item_id(999), "Foreign ticket", cover, WorkItemStatus.IN_PROGRESS, ORG.components[0].id, visible, None, scn.owned.leaves[0].entity.start + timedelta(days=1), ())
c2, r2 = study(scn, "y", (), (OwnedEntities(work_items=(Planted(ticket, visible),)),))
print(f"   + foreign Jira ticket owned by the cover, due in the leave: conclusions same={c2==c0}, required {r2}")


# The stale conflict class (15.5): the runbook's ownership fact is the one the conclusions see
# only through the expected conflict. A second document naming any owner for the ticket is not
# a world the fact base admits (one value per source and key), so no foreign fact can touch the
# conflict; what can be added around the graded people changes nothing they are asked.
from leaveimpact.world import StaleSourceConflict
scn = construct(StaleSourceConflict(), [], ORG, scenario_id=scenario_id(1), window=WINDOW,
                world_start=WORLD_START, reference_timezone=TZ, ids=Minting(), rng=Random(1))
[expected] = scn.key.impacts
outsider = [v.employee_id for v in expected.must_assess if v.verdict is Verdict.NON_VIABLE][0]
cover = [v.employee_id for v in expected.must_assess if v.verdict is Verdict.VIABLE][0]
visible = scn.spec.window.start
c0, r0 = study(scn, "base")
print(f"== stale conflict (deadline cast + runbook naming the outsider): required {r0}")
for who, label in ((outsider, "the outsider"), (cover, "the cover")):
    fj = Fact(employee_ref(who), PredicateName.HAS_SKILL, KAFKA, EvidenceRef(Source.JIRA, comment_ref(comment_id(997))), visible)
    c1, r1 = study(scn, "x", (fj,))
    print(f"   + foreign Jira comment, {label} has Kafka (no clause asks): conclusions same={c1==c0}, required {r1}")
ticket_f = WorkItem(work_item_id(999), "Foreign ticket", outsider, WorkItemStatus.IN_PROGRESS, ORG.components[0].id, visible, None, scn.owned.leaves[0].entity.start + timedelta(days=1), ())
c2, r2 = study(scn, "y", (), (OwnedEntities(work_items=(Planted(ticket_f, visible),)),))
print(f"   + foreign Jira ticket owned by the outsider, due in the leave: conclusions same={c2==c0}, required {r2}")


# The pair (15.5): a foreign positive on the unheld skill moves a verdict (unknown to viable, or
# skill-failing to viable) and with it the outcome, never the required set alone; a foreign
# ticket on a graded person is outside the key's reading.
from leaveimpact.world import MissingInformation, Uncovered
from leaveimpact.world.adversarial import unheld_skill
unheld = unheld_skill(ORG)
for cls, label in ((MissingInformation(), "missing information"), (Uncovered(), "uncovered")):
    scn = construct(cls, [], ORG, scenario_id=scenario_id(1), window=WINDOW,
                    world_start=WORLD_START, reference_timezone=TZ, ids=Minting(), rng=Random(1))
    [expected] = scn.key.impacts
    graded = [v.employee_id for v in expected.must_assess]
    visible = scn.spec.window.start
    c0, r0 = study(scn, "base")
    print(f"== {label} (ticket + clause on the unheld skill): required {r0}, outcome {expected.outcome.value}")
    for who in graded:
        fj = Fact(employee_ref(who), PredicateName.HAS_SKILL, unheld, EvidenceRef(Source.JIRA, comment_ref(comment_id(999))), visible)
        c1, r1 = study(scn, "x", (fj,))
        print(f"   + foreign Jira comment, {who} has the unheld skill: conclusions same={c1==c0}, required {r1}")
    ticket_f = WorkItem(work_item_id(999), "Foreign ticket", graded[0], WorkItemStatus.IN_PROGRESS, ORG.components[0].id, visible, None, scn.owned.leaves[0].entity.start + timedelta(days=1), ())
    c2, r2 = study(scn, "y", (), (OwnedEntities(work_items=(Planted(ticket_f, visible),)),))
    print(f"   + foreign Jira ticket owned by {graded[0]}, due in the leave: conclusions same={c2==c0}, required {r2}")


# The composite (15.5): the conflict's section and the pair's clause together; a foreign
# positive on the unheld skill moves a verdict wherever the skill is asked, the outsider's
# component failure dominates, and nothing can touch the conflict (one value per source).
from leaveimpact.world import AdversarialComposite
scn = construct(AdversarialComposite(), [], ORG, scenario_id=scenario_id(1), window=WINDOW,
                world_start=WORLD_START, reference_timezone=TZ, ids=Minting(), rng=Random(1))
[expected] = scn.key.impacts
graded = [v.employee_id for v in expected.must_assess]
visible = scn.spec.window.start
c0, r0 = study(scn, "base")
print(f"== adversarial composite: required {r0}, outcome {expected.outcome.value}")
for who in graded:
    fj = Fact(employee_ref(who), PredicateName.HAS_SKILL, unheld, EvidenceRef(Source.JIRA, comment_ref(comment_id(999))), visible)
    c1, r1 = study(scn, "x", (fj,))
    print(f"   + foreign Jira comment, {who} has the unheld skill: conclusions same={c1==c0}, required {r1}")
ticket_f = WorkItem(work_item_id(999), "Foreign ticket", graded[0], WorkItemStatus.IN_PROGRESS, ORG.components[0].id, visible, None, scn.owned.leaves[0].entity.start + timedelta(days=1), ())
c2, r2 = study(scn, "y", (), (OwnedEntities(work_items=(Planted(ticket_f, visible),)),))
print(f"   + foreign Jira ticket owned by {graded[0]}, due in the leave: conclusions same={c2==c0}, required {r2}")
