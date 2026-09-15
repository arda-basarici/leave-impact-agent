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
from leaveimpact.world import OwnedEntities, Planted
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
