# Audit sheet, world `40c9657b3182…`

- world version `40c9657b318258601375d310432c3b9855e7a81eb299d31ea4e4de48ae6f41c4`
- seed 1, start 2026-01-05, plan golden, generator version 15, semantic digest `c249e5107de1…`
- org parameters: org_size=28, team_count=5, component_count=5, blank_skill_records=2, skills_per_person=[1, 4], contractor_share=0.15, remote_share=0.25, reference_timezone=Europe/Istanbul, timezone_gap_hours=6
- outcome witness: the semantic world rebuilt from this provenance by the generator's assembly, semantic digest verified equal; per impact the generator's own assessment at the scenario's `now` under the dated view
- writer `eu.anthropic.claude-haiku-4-5-20251001-v1:0` [('max_tokens', 400), ('temperature', 0.7)]
- checker `eu.amazon.nova-pro-v1:0` [('max_tokens', 1200), ('temperature', 0.0)]
- prompt digests: checker_system `b8b400da`, register_client_note `66ef3af4`, register_policy `da31a905`, register_procedure `0393d977`, register_runbook `8994f0f0`, register_ticket_comment `aaef3ab1`, writer_system `3a5c9b81`
- attempt cap 8, prose targets 12, scenarios 30, fact base 495 facts, 2 gaps
- record counters: writer_attempts=16, targets_first_attempt_pass=10, targets_eventual_pass=12, targets_cap_exhausted=0, namespace_refusals=0, required_fact_refusals=0, extraction_refusals=4, checker_retries=0, checker_unusable=0, writer_retries=0, writer_input_tokens=9845, writer_output_tokens=429, checker_input_tokens=24962, checker_output_tokens=1570, writer_latency_ms=9835, checker_latency_ms=15684, canonicalized_pairs=0
- throwaway world: generated on a workstation from the recipe above by the generator's own fresh stage (assemble, materialize, compose, bundle) and left there; never sealed, never projected into a vendor, never scored; the version is the bundle's content hash and names nothing in any bucket
- the sections of rows observable only after a scenario's `now` are kept in this sheet: the per-scenario retirement ruling excludes them from a released golden scenario because they leak other scenarios' plantings, and a throwaway world has nothing to protect

## Rollups

- client_note: 5 targets, first-attempt 4, attempts histogram {1: 4, 4: 1}
- runbook: 4 targets, first-attempt 4, attempts histogram {1: 4}
- ticket_comment: 3 targets, first-attempt 2, attempts histogram {1: 2, 2: 1}
- refusals by guard: {'extraction': 4}
- refusal findings by reason: {'required_not_asserted': 3, 'untyped_proposition': 3, 'not_permitted_fact': 1}
- targets accepted above attempt four (struggling briefs): none
- opening frames (first four words) per register:
    - client_note: 1 × "Ines Yilmaz is the …"
    - client_note: 1 × "Hanna Patel is the …"
    - client_note: 1 × "Zeynep Schmidt is the …"
    - client_note: 1 × "Yusuf Okafor is the …"
    - client_note: 1 × "Yusuf Muller is the …"
    - runbook: 2 × "Yusuf Chen owns the …"
    - runbook: 1 × "Bob Rossi owns the …"
    - runbook: 1 × "Liam Haddad owns the …"
    - ticket_comment: 3 × "I have experience with …"

## Scenarios, in the plan's order

### scenario_001 — tier structured, structured_meeting, modifiers wrong_team, outside_window

- asked: leave leave_023, now 2026-01-09T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-01-05 … 2026-01-18

#### Key

- stable interval 2026-01-05 … 2026-01-12
- required sources: calendar, frappe
- impact meeting on event:event_011 (leave leave_023) -> outcome **assign**
    - must assess emp_023 (Priya Haddad): **viable** (no reason)
    - must assess emp_010 (Bob Yilmaz): **non_viable** (availability)
- distractor event:event_013: wrong_team
- distractor event:event_014: outside_window

#### Outcome witness (dated view at 2026-01-09, the generator's own assessment over every employee)

- impact meeting on event_011: required 1; viable 26, unknown 0, non-viable 2 -> **assign**, agrees with the key
    - need: event:event_011 scheduled_at = {'start': '2026-01-14T11:00:00+03:00', 'end': '2026-01-14T12:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_001 (Hanna Patel), emp_002 (Yusuf Costa), emp_004 (Jonas Nakamura), emp_005 (Omar Jansen), emp_006 (Jonas Moreau), emp_007 (Jonas Novak), emp_008 (Liam Haddad), emp_009 (Priya Moreau), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_015 (Arjun Schmidt), emp_016 (Zeynep Schmidt), emp_017 (Omar Demir), emp_018 (Yusuf Muller), emp_019 (Felix Muller), emp_020 (Yusuf Chen), emp_021 (Kerem Visser), emp_022 (Arjun Haddad), emp_023 (Priya Haddad), emp_024 (Yusuf Okafor), emp_025 (Yusuf Byrne), emp_026 (Ines Yilmaz), emp_027 (Bob Rossi), emp_028 (Chloe Okafor)
    - emp_003 (Nadia Fernandes) [the leaver]: non-viable, availability (employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-01-13', 'end': '2026-01-16'} <- frappe)
    - emp_010 (Bob Yilmaz): non-viable, availability (event:event_012 scheduled_at = {'start': '2026-01-14T11:30:00+03:00', 'end': '2026-01-14T12:30:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-01-09, every employee's facts the criteria read, no rule applied)

- impact meeting on event_011
    - need window: 2026-01-14 … 2026-01-14 (the meeting's day in Europe/Istanbul)
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes) [the leaver]: components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [2026-01-13 … 2026-01-16]; events on the window's days [event_011 {'start': '2026-01-14T11:00:00+03:00', 'end': '2026-01-14T12:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [event_012 {'start': '2026-01-14T11:30:00+03:00', 'end': '2026-01-14T12:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [event_011 {'start': '2026-01-14T11:00:00+03:00', 'end': '2026-01-14T12:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_023: emp_003 (Nadia Fernandes) 2026-01-13 … 2026-01-16, annual, approved (observable from 2026-01-05)
- event event_011 "Payments: release go/no-go with the platform leads": 2026-01-14T11:00:00+03:00 [Europe/Istanbul] … 2026-01-14T12:00:00+03:00 [Europe/Istanbul], attendees emp_003 (Nadia Fernandes), emp_020 (Yusuf Chen) (observable from 2026-01-05)
- event event_012 "Vendor security review": 2026-01-14T11:30:00+03:00 [Europe/Istanbul] … 2026-01-14T12:30:00+03:00 [Europe/Istanbul], attendees emp_010 (Bob Yilmaz) (observable from 2026-01-05)
- event event_013 "Mobile: on-call handover for the next release": 2026-01-13T09:00:00+03:00 [Europe/Istanbul] … 2026-01-13T10:00:00+03:00 [Europe/Istanbul], attendees emp_002 (Yusuf Costa), emp_004 (Jonas Nakamura), emp_005 (Omar Jansen), emp_019 (Felix Muller), emp_020 (Yusuf Chen), emp_021 (Kerem Visser) (observable from 2026-01-05)
- event event_014 "Payments: release go/no-go with the platform leads (debrief)": 2026-01-17T11:00:00+03:00 [Europe/Istanbul] … 2026-01-17T12:00:00+03:00 [Europe/Istanbul], attendees emp_003 (Nadia Fernandes), emp_020 (Yusuf Chen) (observable from 2026-01-05)

#### Fact base, cited entries (in the dated view)

- employee:emp_003 (Nadia Fernandes) employed_as = employee  <- frappe employee:emp_003 (Nadia Fernandes).employment_type  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) has_skill = kafka  <- frappe employee:emp_003 (Nadia Fernandes).skills  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) has_skill = terraform  <- frappe employee:emp_003 (Nadia Fernandes).skills  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) located_in = Toronto  <- frappe employee:emp_003 (Nadia Fernandes).location  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_003 (Nadia Fernandes).team_id  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-01-13', 'end': '2026-01-16'}  <- frappe leave:leave_023  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_003 (Nadia Fernandes).manager_id  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) employed_as = contractor  <- frappe employee:emp_010 (Bob Yilmaz).employment_type  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) has_skill = airflow  <- frappe employee:emp_010 (Bob Yilmaz).skills  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) has_skill = android  <- frappe employee:emp_010 (Bob Yilmaz).skills  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) has_skill = java  <- frappe employee:emp_010 (Bob Yilmaz).skills  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) has_skill = kafka  <- frappe employee:emp_010 (Bob Yilmaz).skills  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) located_in = Toronto  <- frappe employee:emp_010 (Bob Yilmaz).location  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_010 (Bob Yilmaz).team_id  (from 2026-01-05)
- employee:emp_010 (Bob Yilmaz) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_010 (Bob Yilmaz).manager_id  (from 2026-01-05)
- employee:emp_023 (Priya Haddad) employed_as = employee  <- frappe employee:emp_023 (Priya Haddad).employment_type  (from 2026-01-05)
- employee:emp_023 (Priya Haddad) has_skill = python  <- frappe employee:emp_023 (Priya Haddad).skills  (from 2026-01-05)
- employee:emp_023 (Priya Haddad) located_in = Toronto  <- frappe employee:emp_023 (Priya Haddad).location  (from 2026-01-05)
- employee:emp_023 (Priya Haddad) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_023 (Priya Haddad).team_id  (from 2026-01-05)
- employee:emp_023 (Priya Haddad) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_023 (Priya Haddad).manager_id  (from 2026-01-05)
- event:event_011 attends_event = employee:emp_003 (Nadia Fernandes)  <- calendar event:event_011.attendee_ids  (from 2026-01-05)
- event:event_011 attends_event = employee:emp_020 (Yusuf Chen)  <- calendar event:event_011.attendee_ids  (from 2026-01-05)
- event:event_011 scheduled_at = {'start': '2026-01-14T11:00:00+03:00', 'end': '2026-01-14T12:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_011  (from 2026-01-05)
- event:event_012 attends_event = employee:emp_010 (Bob Yilmaz)  <- calendar event:event_012.attendee_ids  (from 2026-01-05)
- event:event_012 scheduled_at = {'start': '2026-01-14T11:30:00+03:00', 'end': '2026-01-14T12:30:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_012  (from 2026-01-05)
- event:event_013 attends_event = employee:emp_002 (Yusuf Costa)  <- calendar event:event_013.attendee_ids  (from 2026-01-05)
- event:event_013 attends_event = employee:emp_004 (Jonas Nakamura)  <- calendar event:event_013.attendee_ids  (from 2026-01-05)
- event:event_013 attends_event = employee:emp_005 (Omar Jansen)  <- calendar event:event_013.attendee_ids  (from 2026-01-05)
- event:event_013 attends_event = employee:emp_019 (Felix Muller)  <- calendar event:event_013.attendee_ids  (from 2026-01-05)
- event:event_013 attends_event = employee:emp_020 (Yusuf Chen)  <- calendar event:event_013.attendee_ids  (from 2026-01-05)
- event:event_013 attends_event = employee:emp_021 (Kerem Visser)  <- calendar event:event_013.attendee_ids  (from 2026-01-05)
- event:event_013 scheduled_at = {'start': '2026-01-13T09:00:00+03:00', 'end': '2026-01-13T10:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_013  (from 2026-01-05)
- event:event_014 attends_event = employee:emp_003 (Nadia Fernandes)  <- calendar event:event_014.attendee_ids  (from 2026-01-05)
- event:event_014 attends_event = employee:emp_020 (Yusuf Chen)  <- calendar event:event_014.attendee_ids  (from 2026-01-05)
- event:event_014 scheduled_at = {'start': '2026-01-17T11:00:00+03:00', 'end': '2026-01-17T12:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_014  (from 2026-01-05)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_003 (Nadia Fernandes) has_skill = elasticsearch  <- corpus clause:clause_019  (from 2026-07-27)
- employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-08-16', 'end': '2026-08-18'}  <- frappe leave:leave_028  (from 2026-08-11)

### scenario_002 — tier structured, structured_mixed, modifiers already_resolved

- asked: leave leave_016, now 2026-01-26T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-01-21 … 2026-02-03

#### Key

- stable interval 2026-01-25 … 2026-01-27
- required sources: calendar, frappe, jira
- impact deadline on work_item:ticket_019 (leave leave_016) -> outcome **assign**
    - must assess emp_016 (Zeynep Schmidt): **viable** (no reason)
    - must assess emp_002 (Yusuf Costa): **non_viable** (component)
- impact meeting on event:event_005 (leave leave_016) -> outcome **assign**
    - must assess emp_002 (Yusuf Costa): **viable** (no reason)
    - must assess emp_005 (Omar Jansen): **non_viable** (availability)
- distractor work_item:ticket_020: already_resolved

#### Outcome witness (dated view at 2026-01-26, the generator's own assessment over every employee)

- impact deadline on ticket_019: required 1; viable 4, unknown 0, non-viable 24 -> **assign**, agrees with the key
    - need: work_item:ticket_019 in_component = component:comp_004 (Billing) <- jira
    - viable: emp_007 (Jonas Novak), emp_011 (Felix Fernandes), emp_016 (Zeynep Schmidt), emp_021 (Kerem Visser)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura) [the leaver]: non-viable, availability (employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing) <- jira; employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'} <- frappe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived
- impact meeting on event_005: required 1; viable 26, unknown 0, non-viable 2 -> **assign**, agrees with the key
    - need: event:event_005 scheduled_at = {'start': '2026-01-31T16:00:00+03:00', 'end': '2026-01-31T17:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_001 (Hanna Patel), emp_002 (Yusuf Costa), emp_003 (Nadia Fernandes), emp_006 (Jonas Moreau), emp_007 (Jonas Novak), emp_008 (Liam Haddad), emp_009 (Priya Moreau), emp_010 (Bob Yilmaz), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_015 (Arjun Schmidt), emp_016 (Zeynep Schmidt), emp_017 (Omar Demir), emp_018 (Yusuf Muller), emp_019 (Felix Muller), emp_020 (Yusuf Chen), emp_021 (Kerem Visser), emp_022 (Arjun Haddad), emp_023 (Priya Haddad), emp_024 (Yusuf Okafor), emp_025 (Yusuf Byrne), emp_026 (Ines Yilmaz), emp_027 (Bob Rossi), emp_028 (Chloe Okafor)
    - emp_004 (Jonas Nakamura) [the leaver]: non-viable, availability (employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'} <- frappe)
    - emp_005 (Omar Jansen): non-viable, availability (event:event_006 scheduled_at = {'start': '2026-01-31T16:30:00+03:00', 'end': '2026-01-31T17:30:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-01-26, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_019
    - need window: 2026-01-28 … 2026-02-01 (the investigated leave's span)
    - artifact's component: work_item:ticket_019 in_component = component:comp_004 (Billing) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura) [the leaver]: components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [2026-01-28 … 2026-02-01]; events on the window's days [event_005 {'start': '2026-01-31T16:00:00+03:00', 'end': '2026-01-31T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [event_006 {'start': '2026-01-31T16:30:00+03:00', 'end': '2026-01-31T17:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [event_005 {'start': '2026-01-31T16:00:00+03:00', 'end': '2026-01-31T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed
- impact meeting on event_005
    - need window: 2026-01-31 … 2026-01-31 (the meeting's day in Europe/Istanbul)
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura) [the leaver]: components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [2026-01-28 … 2026-02-01]; events on the window's days [event_005 {'start': '2026-01-31T16:00:00+03:00', 'end': '2026-01-31T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [event_006 {'start': '2026-01-31T16:30:00+03:00', 'end': '2026-01-31T17:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [event_005 {'start': '2026-01-31T16:00:00+03:00', 'end': '2026-01-31T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_016: emp_004 (Jonas Nakamura) 2026-01-28 … 2026-02-01, annual, approved (observable from 2026-01-21)
- work item ticket_019 "Billing: rotate the signing keys for the EU region": owner emp_004 (Jonas Nakamura), in_progress, component comp_004 (Billing), opened 2026-01-21, due 2026-01-31, resolved — (observable from 2026-01-21)
- work item ticket_020 "Billing: rotate the signing keys for the EU region, phase one": owner emp_004 (Jonas Nakamura), done, component comp_004 (Billing), opened 2026-01-21, due 2026-02-01, resolved 2026-01-25 (observable from 2026-01-25)
- event event_005 "Mobile: quarterly planning for the next release": 2026-01-31T16:00:00+03:00 [Europe/Istanbul] … 2026-01-31T17:00:00+03:00 [Europe/Istanbul], attendees emp_004 (Jonas Nakamura), emp_010 (Bob Yilmaz) (observable from 2026-01-21)
- event event_006 "Budget review with finance": 2026-01-31T16:30:00+03:00 [Europe/Istanbul] … 2026-01-31T17:30:00+03:00 [Europe/Istanbul], attendees emp_005 (Omar Jansen) (observable from 2026-01-21)

#### Fact base, cited entries (in the dated view)

- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) employed_as = employee  <- frappe employee:emp_005 (Omar Jansen).employment_type  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = dbt  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = go  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = java  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = kafka  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = python  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) located_in = Lisbon  <- frappe employee:emp_005 (Omar Jansen).location  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_005 (Omar Jansen).team_id  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_005 (Omar Jansen).manager_id  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) employed_as = employee  <- frappe employee:emp_016 (Zeynep Schmidt).employment_type  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) has_skill = spark  <- frappe employee:emp_016 (Zeynep Schmidt).skills  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) has_skill = typescript  <- frappe employee:emp_016 (Zeynep Schmidt).skills  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) located_in = Toronto  <- frappe employee:emp_016 (Zeynep Schmidt).location  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_016 (Zeynep Schmidt).team_id  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_016 (Zeynep Schmidt).manager_id  (from 2026-01-05)
- event:event_005 attends_event = employee:emp_004 (Jonas Nakamura)  <- calendar event:event_005.attendee_ids  (from 2026-01-21)
- event:event_005 attends_event = employee:emp_010 (Bob Yilmaz)  <- calendar event:event_005.attendee_ids  (from 2026-01-21)
- event:event_005 scheduled_at = {'start': '2026-01-31T16:00:00+03:00', 'end': '2026-01-31T17:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_005  (from 2026-01-21)
- event:event_006 attends_event = employee:emp_005 (Omar Jansen)  <- calendar event:event_006.attendee_ids  (from 2026-01-21)
- event:event_006 scheduled_at = {'start': '2026-01-31T16:30:00+03:00', 'end': '2026-01-31T17:30:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_006  (from 2026-01-21)
- work_item:ticket_019 due_on = 2026-01-31  <- jira work_item:ticket_019.due_on  (from 2026-01-21)
- work_item:ticket_019 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_019.component_id  (from 2026-01-21)
- work_item:ticket_019 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_019.owner_id  (from 2026-01-21)
- work_item:ticket_019 work_item_status = in_progress  <- jira work_item:ticket_019.status  (from 2026-01-21)
- work_item:ticket_020 due_on = 2026-02-01  <- jira work_item:ticket_020.due_on  (from 2026-01-25)
- work_item:ticket_020 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_020.component_id  (from 2026-01-25)
- work_item:ticket_020 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_020.owner_id  (from 2026-01-25)
- work_item:ticket_020 work_item_status = done  <- jira work_item:ticket_020.status  (from 2026-01-25)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2026-07-18', 'end': '2026-07-21'}  <- frappe leave:leave_014  (from 2026-07-12)
- employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'}  <- frappe leave:leave_033  (from 2027-01-26)

### scenario_003 — tier structured, structured_mixed, modifiers already_resolved

- asked: leave leave_017, now 2026-02-11T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-02-07 … 2026-02-20

#### Key

- stable interval 2026-02-08 … 2026-02-14
- required sources: calendar, frappe, jira
- impact deadline on work_item:ticket_021 (leave leave_017) -> outcome **assign**
    - must assess emp_014 (Kerem Haddad): **viable** (no reason)
    - must assess emp_002 (Yusuf Costa): **non_viable** (component)
- impact meeting on event:event_007 (leave leave_017) -> outcome **assign**
    - must assess emp_002 (Yusuf Costa): **viable** (no reason)
    - must assess emp_005 (Omar Jansen): **non_viable** (availability)
- distractor work_item:ticket_022: already_resolved

#### Outcome witness (dated view at 2026-02-11, the generator's own assessment over every employee)

- impact deadline on ticket_021: required 1; viable 5, unknown 0, non-viable 23 -> **assign**, agrees with the key
    - need: work_item:ticket_021 in_component = component:comp_003 (Notifications) <- jira
    - viable: emp_006 (Jonas Moreau), emp_014 (Kerem Haddad), emp_015 (Arjun Schmidt), emp_021 (Kerem Visser), emp_028 (Chloe Okafor)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura) [the leaver]: non-viable, availability (employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications) <- jira; employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'} <- frappe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived
- impact meeting on event_007: required 1; viable 26, unknown 0, non-viable 2 -> **assign**, agrees with the key
    - need: event:event_007 scheduled_at = {'start': '2026-02-17T10:00:00+03:00', 'end': '2026-02-17T11:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_001 (Hanna Patel), emp_002 (Yusuf Costa), emp_003 (Nadia Fernandes), emp_006 (Jonas Moreau), emp_007 (Jonas Novak), emp_008 (Liam Haddad), emp_009 (Priya Moreau), emp_010 (Bob Yilmaz), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_015 (Arjun Schmidt), emp_016 (Zeynep Schmidt), emp_017 (Omar Demir), emp_018 (Yusuf Muller), emp_019 (Felix Muller), emp_020 (Yusuf Chen), emp_021 (Kerem Visser), emp_022 (Arjun Haddad), emp_023 (Priya Haddad), emp_024 (Yusuf Okafor), emp_025 (Yusuf Byrne), emp_026 (Ines Yilmaz), emp_027 (Bob Rossi), emp_028 (Chloe Okafor)
    - emp_004 (Jonas Nakamura) [the leaver]: non-viable, availability (employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'} <- frappe)
    - emp_005 (Omar Jansen): non-viable, availability (event:event_008 scheduled_at = {'start': '2026-02-17T10:30:00+03:00', 'end': '2026-02-17T11:30:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-02-11, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_021
    - need window: 2026-02-15 … 2026-02-17 (the investigated leave's span)
    - artifact's component: work_item:ticket_021 in_component = component:comp_003 (Notifications) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura) [the leaver]: components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [2026-02-15 … 2026-02-17]; events on the window's days [event_007 {'start': '2026-02-17T10:00:00+03:00', 'end': '2026-02-17T11:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [event_008 {'start': '2026-02-17T10:30:00+03:00', 'end': '2026-02-17T11:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [event_007 {'start': '2026-02-17T10:00:00+03:00', 'end': '2026-02-17T11:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed
- impact meeting on event_007
    - need window: 2026-02-17 … 2026-02-17 (the meeting's day in Europe/Istanbul)
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura) [the leaver]: components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [2026-02-15 … 2026-02-17]; events on the window's days [event_007 {'start': '2026-02-17T10:00:00+03:00', 'end': '2026-02-17T11:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [event_008 {'start': '2026-02-17T10:30:00+03:00', 'end': '2026-02-17T11:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [event_007 {'start': '2026-02-17T10:00:00+03:00', 'end': '2026-02-17T11:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_017: emp_004 (Jonas Nakamura) 2026-02-15 … 2026-02-17, annual, approved (observable from 2026-02-07)
- work item ticket_021 "Notifications: rotate the signing keys for the EU region": owner emp_004 (Jonas Nakamura), in_progress, component comp_003 (Notifications), opened 2026-02-07, due 2026-02-16, resolved — (observable from 2026-02-07)
- work item ticket_022 "Notifications: rotate the signing keys for the EU region, phase one": owner emp_004 (Jonas Nakamura), done, component comp_003 (Notifications), opened 2026-02-07, due 2026-02-15, resolved 2026-02-08 (observable from 2026-02-08)
- event event_007 "Mobile: customer escalation sync for the next release": 2026-02-17T10:00:00+03:00 [Europe/Istanbul] … 2026-02-17T11:00:00+03:00 [Europe/Istanbul], attendees emp_004 (Jonas Nakamura), emp_023 (Priya Haddad) (observable from 2026-02-07)
- event event_008 "Vendor security review": 2026-02-17T10:30:00+03:00 [Europe/Istanbul] … 2026-02-17T11:30:00+03:00 [Europe/Istanbul], attendees emp_005 (Omar Jansen) (observable from 2026-02-07)

#### Fact base, cited entries (in the dated view)

- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) employed_as = employee  <- frappe employee:emp_005 (Omar Jansen).employment_type  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = dbt  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = go  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = java  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = kafka  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = python  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) located_in = Lisbon  <- frappe employee:emp_005 (Omar Jansen).location  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_005 (Omar Jansen).team_id  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_005 (Omar Jansen).manager_id  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) employed_as = employee  <- frappe employee:emp_014 (Kerem Haddad).employment_type  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) has_skill = react  <- frappe employee:emp_014 (Kerem Haddad).skills  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) has_skill = terraform  <- frappe employee:emp_014 (Kerem Haddad).skills  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) located_in = Warsaw  <- frappe employee:emp_014 (Kerem Haddad).location  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_014 (Kerem Haddad).team_id  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_014 (Kerem Haddad).manager_id  (from 2026-01-05)
- event:event_007 attends_event = employee:emp_004 (Jonas Nakamura)  <- calendar event:event_007.attendee_ids  (from 2026-02-07)
- event:event_007 attends_event = employee:emp_023 (Priya Haddad)  <- calendar event:event_007.attendee_ids  (from 2026-02-07)
- event:event_007 scheduled_at = {'start': '2026-02-17T10:00:00+03:00', 'end': '2026-02-17T11:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_007  (from 2026-02-07)
- event:event_008 attends_event = employee:emp_005 (Omar Jansen)  <- calendar event:event_008.attendee_ids  (from 2026-02-07)
- event:event_008 scheduled_at = {'start': '2026-02-17T10:30:00+03:00', 'end': '2026-02-17T11:30:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_008  (from 2026-02-07)
- work_item:ticket_021 due_on = 2026-02-16  <- jira work_item:ticket_021.due_on  (from 2026-02-07)
- work_item:ticket_021 in_component = component:comp_003 (Notifications)  <- jira work_item:ticket_021.component_id  (from 2026-02-07)
- work_item:ticket_021 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_021.owner_id  (from 2026-02-07)
- work_item:ticket_021 work_item_status = in_progress  <- jira work_item:ticket_021.status  (from 2026-02-07)
- work_item:ticket_022 due_on = 2026-02-15  <- jira work_item:ticket_022.due_on  (from 2026-02-08)
- work_item:ticket_022 in_component = component:comp_003 (Notifications)  <- jira work_item:ticket_022.component_id  (from 2026-02-08)
- work_item:ticket_022 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_022.owner_id  (from 2026-02-08)
- work_item:ticket_022 work_item_status = done  <- jira work_item:ticket_022.status  (from 2026-02-08)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)

### scenario_004 — tier structured, structured_meeting, modifiers none

- asked: leave leave_024, now 2026-02-22T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-02-21 … 2026-03-06

#### Key

- stable interval 2026-02-21 … 2026-02-25
- required sources: calendar, frappe
- impact meeting on event:event_015 (leave leave_024) -> outcome **assign**
    - must assess emp_005 (Omar Jansen): **viable** (no reason)
    - must assess emp_002 (Yusuf Costa): **non_viable** (availability)

#### Outcome witness (dated view at 2026-02-22, the generator's own assessment over every employee)

- impact meeting on event_015: required 1; viable 26, unknown 0, non-viable 2 -> **assign**, agrees with the key
    - need: event:event_015 scheduled_at = {'start': '2026-03-01T14:00:00+03:00', 'end': '2026-03-01T15:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_001 (Hanna Patel), emp_003 (Nadia Fernandes), emp_004 (Jonas Nakamura), emp_005 (Omar Jansen), emp_006 (Jonas Moreau), emp_007 (Jonas Novak), emp_008 (Liam Haddad), emp_009 (Priya Moreau), emp_010 (Bob Yilmaz), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_015 (Arjun Schmidt), emp_016 (Zeynep Schmidt), emp_017 (Omar Demir), emp_018 (Yusuf Muller), emp_020 (Yusuf Chen), emp_021 (Kerem Visser), emp_022 (Arjun Haddad), emp_023 (Priya Haddad), emp_024 (Yusuf Okafor), emp_025 (Yusuf Byrne), emp_026 (Ines Yilmaz), emp_027 (Bob Rossi), emp_028 (Chloe Okafor)
    - emp_002 (Yusuf Costa): non-viable, availability (event:event_016 scheduled_at = {'start': '2026-03-01T14:30:00+03:00', 'end': '2026-03-01T15:30:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar)
    - emp_019 (Felix Muller) [the leaver]: non-viable, availability (employee:emp_019 (Felix Muller) on_leave = {'start': '2026-02-26', 'end': '2026-03-02'} <- frappe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-02-22, every employee's facts the criteria read, no rule applied)

- impact meeting on event_015
    - need window: 2026-03-01 … 2026-03-01 (the meeting's day in Europe/Istanbul)
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [event_016 {'start': '2026-03-01T14:30:00+03:00', 'end': '2026-03-01T15:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller) [the leaver]: components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [2026-02-26 … 2026-03-02]; events on the window's days [event_015 {'start': '2026-03-01T14:00:00+03:00', 'end': '2026-03-01T15:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [event_015 {'start': '2026-03-01T14:00:00+03:00', 'end': '2026-03-01T15:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_024: emp_019 (Felix Muller) 2026-02-26 … 2026-03-02, annual, approved (observable from 2026-02-21)
- event event_015 "Mobile: release go/no-go": 2026-03-01T14:00:00+03:00 [Europe/Istanbul] … 2026-03-01T15:00:00+03:00 [Europe/Istanbul], attendees emp_019 (Felix Muller), emp_027 (Bob Rossi) (observable from 2026-02-21)
- event event_016 "Vendor security review": 2026-03-01T14:30:00+03:00 [Europe/Istanbul] … 2026-03-01T15:30:00+03:00 [Europe/Istanbul], attendees emp_002 (Yusuf Costa) (observable from 2026-02-21)

#### Fact base, cited entries (in the dated view)

- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) employed_as = employee  <- frappe employee:emp_005 (Omar Jansen).employment_type  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = dbt  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = go  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = java  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = kafka  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) has_skill = python  <- frappe employee:emp_005 (Omar Jansen).skills  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) located_in = Lisbon  <- frappe employee:emp_005 (Omar Jansen).location  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_005 (Omar Jansen).team_id  (from 2026-01-05)
- employee:emp_005 (Omar Jansen) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_005 (Omar Jansen).manager_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) employed_as = employee  <- frappe employee:emp_019 (Felix Muller).employment_type  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = airflow  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = elasticsearch  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) located_in = Lisbon  <- frappe employee:emp_019 (Felix Muller).location  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_019 (Felix Muller).team_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-02-26', 'end': '2026-03-02'}  <- frappe leave:leave_024  (from 2026-02-21)
- employee:emp_019 (Felix Muller) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_019 (Felix Muller).manager_id  (from 2026-01-05)
- event:event_015 attends_event = employee:emp_019 (Felix Muller)  <- calendar event:event_015.attendee_ids  (from 2026-02-21)
- event:event_015 attends_event = employee:emp_027 (Bob Rossi)  <- calendar event:event_015.attendee_ids  (from 2026-02-21)
- event:event_015 scheduled_at = {'start': '2026-03-01T14:00:00+03:00', 'end': '2026-03-01T15:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_015  (from 2026-02-21)
- event:event_016 attends_event = employee:emp_002 (Yusuf Costa)  <- calendar event:event_016.attendee_ids  (from 2026-02-21)
- event:event_016 scheduled_at = {'start': '2026-03-01T14:30:00+03:00', 'end': '2026-03-01T15:30:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_016  (from 2026-02-21)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-12-01', 'end': '2026-12-05'}  <- frappe leave:leave_004  (from 2026-11-25)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-01-18', 'end': '2027-01-21'}  <- frappe leave:leave_006  (from 2027-01-11)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-02-18', 'end': '2027-02-20'}  <- frappe leave:leave_005  (from 2027-02-12)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_035  (from 2027-02-28)

### scenario_005 — tier structured, structured_meeting, modifiers none

- asked: leave leave_025, now 2026-03-09T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-03-07 … 2026-03-20

#### Key

- stable interval 2026-03-07 … 2026-03-12
- required sources: calendar, frappe
- impact meeting on event:event_017 (leave leave_025) -> outcome **assign**
    - must assess emp_013 (Mert Yilmaz): **viable** (no reason)
    - must assess emp_009 (Priya Moreau): **non_viable** (availability)

#### Outcome witness (dated view at 2026-03-09, the generator's own assessment over every employee)

- impact meeting on event_017: required 1; viable 26, unknown 0, non-viable 2 -> **assign**, agrees with the key
    - need: event:event_017 scheduled_at = {'start': '2026-03-15T10:00:00+03:00', 'end': '2026-03-15T11:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_001 (Hanna Patel), emp_002 (Yusuf Costa), emp_003 (Nadia Fernandes), emp_004 (Jonas Nakamura), emp_005 (Omar Jansen), emp_006 (Jonas Moreau), emp_007 (Jonas Novak), emp_008 (Liam Haddad), emp_010 (Bob Yilmaz), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_015 (Arjun Schmidt), emp_016 (Zeynep Schmidt), emp_017 (Omar Demir), emp_018 (Yusuf Muller), emp_019 (Felix Muller), emp_020 (Yusuf Chen), emp_021 (Kerem Visser), emp_022 (Arjun Haddad), emp_023 (Priya Haddad), emp_024 (Yusuf Okafor), emp_026 (Ines Yilmaz), emp_027 (Bob Rossi), emp_028 (Chloe Okafor)
    - emp_009 (Priya Moreau): non-viable, availability (event:event_018 scheduled_at = {'start': '2026-03-15T10:30:00+03:00', 'end': '2026-03-15T11:30:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar)
    - emp_025 (Yusuf Byrne) [the leaver]: non-viable, availability (employee:emp_025 (Yusuf Byrne) on_leave = {'start': '2026-03-13', 'end': '2026-03-15'} <- frappe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-03-09, every employee's facts the criteria read, no rule applied)

- impact meeting on event_017
    - need window: 2026-03-15 … 2026-03-15 (the meeting's day in Europe/Istanbul)
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [event_018 {'start': '2026-03-15T10:30:00+03:00', 'end': '2026-03-15T11:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [event_017 {'start': '2026-03-15T10:00:00+03:00', 'end': '2026-03-15T11:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne) [the leaver]: components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [2026-03-13 … 2026-03-15]; events on the window's days [event_017 {'start': '2026-03-15T10:00:00+03:00', 'end': '2026-03-15T11:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_025: emp_025 (Yusuf Byrne) 2026-03-13 … 2026-03-15, annual, approved (observable from 2026-03-07)
- event event_017 "Platform: sprint review for the next release": 2026-03-15T10:00:00+03:00 [Europe/Istanbul] … 2026-03-15T11:00:00+03:00 [Europe/Istanbul], attendees emp_025 (Yusuf Byrne), emp_016 (Zeynep Schmidt) (observable from 2026-03-07)
- event event_018 "Architecture forum": 2026-03-15T10:30:00+03:00 [Europe/Istanbul] … 2026-03-15T11:30:00+03:00 [Europe/Istanbul], attendees emp_009 (Priya Moreau) (observable from 2026-03-07)

#### Fact base, cited entries (in the dated view)

- employee:emp_009 (Priya Moreau) employed_as = employee  <- frappe employee:emp_009 (Priya Moreau).employment_type  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) has_skill = android  <- frappe employee:emp_009 (Priya Moreau).skills  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) has_skill = python  <- frappe employee:emp_009 (Priya Moreau).skills  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) has_skill = terraform  <- frappe employee:emp_009 (Priya Moreau).skills  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) located_in = Warsaw  <- frappe employee:emp_009 (Priya Moreau).location  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_009 (Priya Moreau).team_id  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_009 (Priya Moreau).manager_id  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) employed_as = employee  <- frappe employee:emp_013 (Mert Yilmaz).employment_type  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) has_skill = react  <- frappe employee:emp_013 (Mert Yilmaz).skills  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) located_in = Warsaw  <- frappe employee:emp_013 (Mert Yilmaz).location  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_013 (Mert Yilmaz).team_id  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_013 (Mert Yilmaz).manager_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) employed_as = contractor  <- frappe employee:emp_025 (Yusuf Byrne).employment_type  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = java  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kafka  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kubernetes  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) located_in = Warsaw  <- frappe employee:emp_025 (Yusuf Byrne).location  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_025 (Yusuf Byrne).team_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) on_leave = {'start': '2026-03-13', 'end': '2026-03-15'}  <- frappe leave:leave_025  (from 2026-03-07)
- employee:emp_025 (Yusuf Byrne) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_025 (Yusuf Byrne).manager_id  (from 2026-01-05)
- event:event_017 attends_event = employee:emp_016 (Zeynep Schmidt)  <- calendar event:event_017.attendee_ids  (from 2026-03-07)
- event:event_017 attends_event = employee:emp_025 (Yusuf Byrne)  <- calendar event:event_017.attendee_ids  (from 2026-03-07)
- event:event_017 scheduled_at = {'start': '2026-03-15T10:00:00+03:00', 'end': '2026-03-15T11:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_017  (from 2026-03-07)
- event:event_018 attends_event = employee:emp_009 (Priya Moreau)  <- calendar event:event_018.attendee_ids  (from 2026-03-07)
- event:event_018 scheduled_at = {'start': '2026-03-15T10:30:00+03:00', 'end': '2026-03-15T11:30:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_018  (from 2026-03-07)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_009 (Priya Moreau) on_leave = {'start': '2026-05-14', 'end': '2026-05-16'}  <- frappe leave:leave_020  (from 2026-05-09)
- employee:emp_013 (Mert Yilmaz) on_leave = {'start': '2026-05-14', 'end': '2026-05-16'}  <- frappe leave:leave_021  (from 2026-05-09)

### scenario_006 — tier structured, structured_deadline, modifiers none

- asked: leave leave_018, now 2026-03-25T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-03-23 … 2026-04-05

#### Key

- stable interval 2026-03-23 … 2026-03-28
- required sources: frappe, jira
- impact deadline on work_item:ticket_023 (leave leave_018) -> outcome **assign**
    - must assess emp_025 (Yusuf Byrne): **viable** (no reason)
    - must assess emp_001 (Hanna Patel): **non_viable** (component)

#### Outcome witness (dated view at 2026-03-25, the generator's own assessment over every employee)

- impact deadline on ticket_023: required 1; viable 4, unknown 0, non-viable 24 -> **assign**, agrees with the key
    - need: work_item:ticket_023 in_component = component:comp_002 (Payments API) <- jira
    - viable: emp_004 (Jonas Nakamura), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_025 (Yusuf Byrne)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak) [the leaver]: non-viable, availability (employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'} <- frappe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-03-25, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_023
    - need window: 2026-03-29 … 2026-04-02 (the investigated leave's span)
    - artifact's component: work_item:ticket_023 in_component = component:comp_002 (Payments API) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak) [the leaver]: components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [2026-03-29 … 2026-04-02]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_018: emp_007 (Jonas Novak) 2026-03-29 … 2026-04-02, annual, approved (observable from 2026-03-23)
- work item ticket_023 "Payments API: migrate the retry queue for the EU region": owner emp_007 (Jonas Novak), in_progress, component comp_002 (Payments API), opened 2026-03-23, due 2026-04-01, resolved — (observable from 2026-03-23)

#### Fact base, cited entries (in the dated view)

- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) employed_as = contractor  <- frappe employee:emp_025 (Yusuf Byrne).employment_type  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = java  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kafka  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kubernetes  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) located_in = Warsaw  <- frappe employee:emp_025 (Yusuf Byrne).location  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_025 (Yusuf Byrne).team_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) on_leave = {'start': '2026-03-13', 'end': '2026-03-15'}  <- frappe leave:leave_025  (from 2026-03-07)
- employee:emp_025 (Yusuf Byrne) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_025 (Yusuf Byrne).manager_id  (from 2026-01-05)
- work_item:ticket_023 due_on = 2026-04-01  <- jira work_item:ticket_023.due_on  (from 2026-03-23)
- work_item:ticket_023 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_023.component_id  (from 2026-03-23)
- work_item:ticket_023 owns_work_item = employee:emp_007 (Jonas Novak)  <- jira work_item:ticket_023.owner_id  (from 2026-03-23)
- work_item:ticket_023 work_item_status = in_progress  <- jira work_item:ticket_023.status  (from 2026-03-23)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)

### scenario_007 — tier structured, structured_deadline, modifiers outside_window, timezone_boundary

- asked: leave leave_019, now 2026-04-13T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-04-09 … 2026-04-22

#### Key

- stable interval 2026-04-09 … 2026-04-14
- required sources: frappe, jira
- impact deadline on work_item:ticket_024 (leave leave_019) -> outcome **assign**
    - must assess emp_004 (Jonas Nakamura): **viable** (no reason)
    - must assess emp_018 (Yusuf Muller): **non_viable** (component)
- distractor work_item:ticket_025: outside_window
- distractor event:event_009: timezone_boundary

#### Outcome witness (dated view at 2026-04-13, the generator's own assessment over every employee)

- impact deadline on ticket_024: required 1; viable 5, unknown 0, non-viable 23 -> **assign**, agrees with the key
    - need: work_item:ticket_024 in_component = component:comp_003 (Notifications) <- jira
    - viable: emp_004 (Jonas Nakamura), emp_006 (Jonas Moreau), emp_014 (Kerem Haddad), emp_021 (Kerem Visser), emp_028 (Chloe Okafor)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt) [the leaver]: non-viable, availability (employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications) <- jira; employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'} <- frappe)
    - emp_016 (Zeynep Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-04-13, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_024
    - need window: 2026-04-15 … 2026-04-19 (the investigated leave's span)
    - artifact's component: work_item:ticket_024 in_component = component:comp_003 (Notifications) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt) [the leaver]: components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [2026-04-15 … 2026-04-19]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_019: emp_015 (Arjun Schmidt) 2026-04-15 … 2026-04-19, annual, approved (observable from 2026-04-09)
- work item ticket_024 "Notifications: rotate the signing keys for the mobile clients": owner emp_015 (Arjun Schmidt), in_progress, component comp_003 (Notifications), opened 2026-04-09, due 2026-04-17, resolved — (observable from 2026-04-09)
- work item ticket_025 "Notifications: rotate the signing keys for the mobile clients, groundwork": owner emp_015 (Arjun Schmidt), in_progress, component comp_003 (Notifications), opened 2026-04-09, due 2026-04-14, resolved — (observable from 2026-04-09)
- event event_009 "Cross-region sync": 2026-04-19T17:00:00-04:00 [America/Toronto] … 2026-04-19T18:00:00-04:00 [America/Toronto], attendees emp_015 (Arjun Schmidt), emp_023 (Priya Haddad) (observable from 2026-04-09)

#### Fact base, cited entries (in the dated view)

- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) employed_as = employee  <- frappe employee:emp_018 (Yusuf Muller).employment_type  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = android  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = graphql  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = ios  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = java  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) located_in = Amsterdam  <- frappe employee:emp_018 (Yusuf Muller).location  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_018 (Yusuf Muller).team_id  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_018 (Yusuf Muller).manager_id  (from 2026-01-05)
- event:event_009 attends_event = employee:emp_015 (Arjun Schmidt)  <- calendar event:event_009.attendee_ids  (from 2026-04-09)
- event:event_009 attends_event = employee:emp_023 (Priya Haddad)  <- calendar event:event_009.attendee_ids  (from 2026-04-09)
- event:event_009 scheduled_at = {'start': '2026-04-19T17:00:00-04:00', 'end': '2026-04-19T18:00:00-04:00', 'zone': 'America/Toronto'}  <- calendar event:event_009  (from 2026-04-09)
- work_item:ticket_024 due_on = 2026-04-17  <- jira work_item:ticket_024.due_on  (from 2026-04-09)
- work_item:ticket_024 in_component = component:comp_003 (Notifications)  <- jira work_item:ticket_024.component_id  (from 2026-04-09)
- work_item:ticket_024 owns_work_item = employee:emp_015 (Arjun Schmidt)  <- jira work_item:ticket_024.owner_id  (from 2026-04-09)
- work_item:ticket_024 work_item_status = in_progress  <- jira work_item:ticket_024.status  (from 2026-04-09)
- work_item:ticket_025 due_on = 2026-04-14  <- jira work_item:ticket_025.due_on  (from 2026-04-09)
- work_item:ticket_025 in_component = component:comp_003 (Notifications)  <- jira work_item:ticket_025.component_id  (from 2026-04-09)
- work_item:ticket_025 owns_work_item = employee:emp_015 (Arjun Schmidt)  <- jira work_item:ticket_025.owner_id  (from 2026-04-09)
- work_item:ticket_025 work_item_status = in_progress  <- jira work_item:ticket_025.status  (from 2026-04-09)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_018 (Yusuf Muller) on_leave = {'start': '2026-11-03', 'end': '2026-11-04'}  <- frappe leave:leave_013  (from 2026-10-26)

### scenario_008 — tier structured, structured_meeting, modifiers wrong_team, concurrent_leave

- asked: leave leave_026, now 2026-04-27T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-04-23 … 2026-05-06

#### Key

- stable interval 2026-04-23 … 2026-04-30
- required sources: calendar, frappe
- impact meeting on event:event_019 (leave leave_026) -> outcome **assign**
    - must assess emp_001 (Hanna Patel): **non_viable** (availability)
    - must assess emp_011 (Felix Fernandes): **non_viable** (availability)
- distractor event:event_021: wrong_team

#### Outcome witness (dated view at 2026-04-27, the generator's own assessment over every employee)

- impact meeting on event_019: required 1; viable 25, unknown 0, non-viable 3 -> **assign**, agrees with the key
    - need: event:event_019 scheduled_at = {'start': '2026-05-01T16:00:00+03:00', 'end': '2026-05-01T17:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_002 (Yusuf Costa), emp_003 (Nadia Fernandes), emp_004 (Jonas Nakamura), emp_005 (Omar Jansen), emp_006 (Jonas Moreau), emp_008 (Liam Haddad), emp_009 (Priya Moreau), emp_010 (Bob Yilmaz), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_015 (Arjun Schmidt), emp_016 (Zeynep Schmidt), emp_017 (Omar Demir), emp_018 (Yusuf Muller), emp_019 (Felix Muller), emp_020 (Yusuf Chen), emp_021 (Kerem Visser), emp_022 (Arjun Haddad), emp_023 (Priya Haddad), emp_024 (Yusuf Okafor), emp_025 (Yusuf Byrne), emp_026 (Ines Yilmaz), emp_027 (Bob Rossi), emp_028 (Chloe Okafor)
    - emp_001 (Hanna Patel): non-viable, availability (event:event_020 scheduled_at = {'start': '2026-05-01T16:30:00+03:00', 'end': '2026-05-01T17:30:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar)
    - emp_007 (Jonas Novak) [the leaver]: non-viable, availability (employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'} <- frappe)
    - emp_011 (Felix Fernandes): non-viable, availability (employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'} <- frappe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-04-27, every employee's facts the criteria read, no rule applied)

- impact meeting on event_019
    - need window: 2026-05-01 … 2026-05-01 (the meeting's day in Europe/Istanbul)
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [event_020 {'start': '2026-05-01T16:30:00+03:00', 'end': '2026-05-01T17:30:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak) [the leaver]: components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [2026-05-01 … 2026-05-04]; events on the window's days [event_019 {'start': '2026-05-01T16:00:00+03:00', 'end': '2026-05-01T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [2026-05-01 … 2026-05-04]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [event_019 {'start': '2026-05-01T16:00:00+03:00', 'end': '2026-05-01T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_026: emp_007 (Jonas Novak) 2026-05-01 … 2026-05-04, annual, approved (observable from 2026-04-23)
- leave leave_027: emp_011 (Felix Fernandes) 2026-05-01 … 2026-05-04, sick, approved (observable from 2026-04-23)
- event event_019 "Growth: customer escalation sync (deep dive)": 2026-05-01T16:00:00+03:00 [Europe/Istanbul] … 2026-05-01T17:00:00+03:00 [Europe/Istanbul], attendees emp_007 (Jonas Novak), emp_018 (Yusuf Muller) (observable from 2026-04-23)
- event event_020 "Architecture forum": 2026-05-01T16:30:00+03:00 [Europe/Istanbul] … 2026-05-01T17:30:00+03:00 [Europe/Istanbul], attendees emp_001 (Hanna Patel) (observable from 2026-04-23)
- event event_021 "Payments: demo prep with product": 2026-05-04T09:00:00+03:00 [Europe/Istanbul] … 2026-05-04T10:00:00+03:00 [Europe/Istanbul], attendees emp_003 (Nadia Fernandes), emp_010 (Bob Yilmaz), emp_012 (Nadia Sharma), emp_016 (Zeynep Schmidt), emp_017 (Omar Demir), emp_023 (Priya Haddad) (observable from 2026-04-23)

#### Fact base, cited entries (in the dated view)

- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- event:event_019 attends_event = employee:emp_007 (Jonas Novak)  <- calendar event:event_019.attendee_ids  (from 2026-04-23)
- event:event_019 attends_event = employee:emp_018 (Yusuf Muller)  <- calendar event:event_019.attendee_ids  (from 2026-04-23)
- event:event_019 scheduled_at = {'start': '2026-05-01T16:00:00+03:00', 'end': '2026-05-01T17:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_019  (from 2026-04-23)
- event:event_020 attends_event = employee:emp_001 (Hanna Patel)  <- calendar event:event_020.attendee_ids  (from 2026-04-23)
- event:event_020 scheduled_at = {'start': '2026-05-01T16:30:00+03:00', 'end': '2026-05-01T17:30:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_020  (from 2026-04-23)
- event:event_021 attends_event = employee:emp_003 (Nadia Fernandes)  <- calendar event:event_021.attendee_ids  (from 2026-04-23)
- event:event_021 attends_event = employee:emp_010 (Bob Yilmaz)  <- calendar event:event_021.attendee_ids  (from 2026-04-23)
- event:event_021 attends_event = employee:emp_012 (Nadia Sharma)  <- calendar event:event_021.attendee_ids  (from 2026-04-23)
- event:event_021 attends_event = employee:emp_016 (Zeynep Schmidt)  <- calendar event:event_021.attendee_ids  (from 2026-04-23)
- event:event_021 attends_event = employee:emp_017 (Omar Demir)  <- calendar event:event_021.attendee_ids  (from 2026-04-23)
- event:event_021 attends_event = employee:emp_023 (Priya Haddad)  <- calendar event:event_021.attendee_ids  (from 2026-04-23)
- event:event_021 scheduled_at = {'start': '2026-05-04T09:00:00+03:00', 'end': '2026-05-04T10:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_021  (from 2026-04-23)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)

### scenario_009 — tier structured, structured_deadline, modifiers concurrent_leave

- asked: leave leave_020, now 2026-05-10T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-05-09 … 2026-05-22

#### Key

- stable interval 2026-05-09 … 2026-05-13
- required sources: frappe, jira
- impact deadline on work_item:ticket_026 (leave leave_020) -> outcome **assign**
    - must assess emp_014 (Kerem Haddad): **non_viable** (component)
    - must assess emp_013 (Mert Yilmaz): **non_viable** (availability)

#### Outcome witness (dated view at 2026-05-10, the generator's own assessment over every employee)

- impact deadline on ticket_026: required 1; viable 3, unknown 0, non-viable 25 -> **assign**, agrees with the key
    - need: work_item:ticket_026 in_component = component:comp_005 (Event Ingestion) <- jira
    - viable: emp_005 (Omar Jansen), emp_022 (Arjun Haddad), emp_026 (Ines Yilmaz)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau) [the leaver]: non-viable, availability (employee:emp_009 (Priya Moreau) member_of_component = component:comp_005 (Event Ingestion) <- jira; employee:emp_009 (Priya Moreau) on_leave = {'start': '2026-05-14', 'end': '2026-05-16'} <- frappe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, availability (employee:emp_013 (Mert Yilmaz) member_of_component = component:comp_005 (Event Ingestion) <- jira; employee:emp_013 (Mert Yilmaz) on_leave = {'start': '2026-05-14', 'end': '2026-05-16'} <- frappe)
    - emp_014 (Kerem Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-05-10, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_026
    - need window: 2026-05-14 … 2026-05-16 (the investigated leave's span)
    - artifact's component: work_item:ticket_026 in_component = component:comp_005 (Event Ingestion) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau) [the leaver]: components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [2026-05-14 … 2026-05-16]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [2026-05-14 … 2026-05-16]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_020: emp_009 (Priya Moreau) 2026-05-14 … 2026-05-16, annual, approved (observable from 2026-05-09)
- leave leave_021: emp_013 (Mert Yilmaz) 2026-05-14 … 2026-05-16, sick, approved (observable from 2026-05-09)
- work item ticket_026 "Event Ingestion: migrate the retry queue for the EU region": owner emp_009 (Priya Moreau), in_progress, component comp_005 (Event Ingestion), opened 2026-05-09, due 2026-05-15, resolved — (observable from 2026-05-09)

#### Fact base, cited entries (in the dated view)

- employee:emp_009 (Priya Moreau) employed_as = employee  <- frappe employee:emp_009 (Priya Moreau).employment_type  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) has_skill = android  <- frappe employee:emp_009 (Priya Moreau).skills  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) has_skill = python  <- frappe employee:emp_009 (Priya Moreau).skills  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) has_skill = terraform  <- frappe employee:emp_009 (Priya Moreau).skills  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) located_in = Warsaw  <- frappe employee:emp_009 (Priya Moreau).location  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_009 (Priya Moreau).team_id  (from 2026-01-05)
- employee:emp_009 (Priya Moreau) on_leave = {'start': '2026-05-14', 'end': '2026-05-16'}  <- frappe leave:leave_020  (from 2026-05-09)
- employee:emp_009 (Priya Moreau) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_009 (Priya Moreau).manager_id  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) employed_as = employee  <- frappe employee:emp_013 (Mert Yilmaz).employment_type  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) has_skill = react  <- frappe employee:emp_013 (Mert Yilmaz).skills  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) located_in = Warsaw  <- frappe employee:emp_013 (Mert Yilmaz).location  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_013 (Mert Yilmaz).team_id  (from 2026-01-05)
- employee:emp_013 (Mert Yilmaz) on_leave = {'start': '2026-05-14', 'end': '2026-05-16'}  <- frappe leave:leave_021  (from 2026-05-09)
- employee:emp_013 (Mert Yilmaz) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_013 (Mert Yilmaz).manager_id  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) employed_as = employee  <- frappe employee:emp_014 (Kerem Haddad).employment_type  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) has_skill = react  <- frappe employee:emp_014 (Kerem Haddad).skills  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) has_skill = terraform  <- frappe employee:emp_014 (Kerem Haddad).skills  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) located_in = Warsaw  <- frappe employee:emp_014 (Kerem Haddad).location  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_014 (Kerem Haddad).team_id  (from 2026-01-05)
- employee:emp_014 (Kerem Haddad) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_014 (Kerem Haddad).manager_id  (from 2026-01-05)
- work_item:ticket_026 due_on = 2026-05-15  <- jira work_item:ticket_026.due_on  (from 2026-05-09)
- work_item:ticket_026 in_component = component:comp_005 (Event Ingestion)  <- jira work_item:ticket_026.component_id  (from 2026-05-09)
- work_item:ticket_026 owns_work_item = employee:emp_009 (Priya Moreau)  <- jira work_item:ticket_026.owner_id  (from 2026-05-09)
- work_item:ticket_026 work_item_status = in_progress  <- jira work_item:ticket_026.status  (from 2026-05-09)

### scenario_010 — tier structured, structured_deadline, modifiers timezone_boundary

- asked: leave leave_022, now 2026-05-25T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-05-24 … 2026-06-06

#### Key

- stable interval 2026-05-24 … 2026-05-28
- required sources: frappe, jira
- impact deadline on work_item:ticket_027 (leave leave_022) -> outcome **assign**
    - must assess emp_004 (Jonas Nakamura): **viable** (no reason)
    - must assess emp_002 (Yusuf Costa): **non_viable** (component)
- distractor event:event_010: timezone_boundary

#### Outcome witness (dated view at 2026-05-25, the generator's own assessment over every employee)

- impact deadline on ticket_027: required 1; viable 4, unknown 0, non-viable 24 -> **assign**, agrees with the key
    - need: work_item:ticket_027 in_component = component:comp_004 (Billing) <- jira
    - viable: emp_004 (Jonas Nakamura), emp_007 (Jonas Novak), emp_011 (Felix Fernandes), emp_016 (Zeynep Schmidt)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser) [the leaver]: non-viable, availability (employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing) <- jira; employee:emp_021 (Kerem Visser) on_leave = {'start': '2026-05-29', 'end': '2026-05-31'} <- frappe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-05-25, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_027
    - need window: 2026-05-29 … 2026-05-31 (the investigated leave's span)
    - artifact's component: work_item:ticket_027 in_component = component:comp_004 (Billing) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser) [the leaver]: components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [2026-05-29 … 2026-05-31]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_022: emp_021 (Kerem Visser) 2026-05-29 … 2026-05-31, annual, approved (observable from 2026-05-24)
- work item ticket_027 "Billing: close the audit findings for the EU region": owner emp_021 (Kerem Visser), in_progress, component comp_004 (Billing), opened 2026-05-24, due 2026-05-29, resolved — (observable from 2026-05-24)
- event event_010 "Cross-region sync": 2026-05-31T17:00:00-04:00 [America/Toronto] … 2026-05-31T18:00:00-04:00 [America/Toronto], attendees emp_021 (Kerem Visser), emp_003 (Nadia Fernandes) (observable from 2026-05-24)

#### Fact base, cited entries (in the dated view)

- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) employed_as = contractor  <- frappe employee:emp_021 (Kerem Visser).employment_type  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = java  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = kafka  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = postgresql  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) located_in = Lisbon  <- frappe employee:emp_021 (Kerem Visser).location  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_021 (Kerem Visser).team_id  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) on_leave = {'start': '2026-05-29', 'end': '2026-05-31'}  <- frappe leave:leave_022  (from 2026-05-24)
- employee:emp_021 (Kerem Visser) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_021 (Kerem Visser).manager_id  (from 2026-01-05)
- event:event_010 attends_event = employee:emp_003 (Nadia Fernandes)  <- calendar event:event_010.attendee_ids  (from 2026-05-24)
- event:event_010 attends_event = employee:emp_021 (Kerem Visser)  <- calendar event:event_010.attendee_ids  (from 2026-05-24)
- event:event_010 scheduled_at = {'start': '2026-05-31T17:00:00-04:00', 'end': '2026-05-31T18:00:00-04:00', 'zone': 'America/Toronto'}  <- calendar event:event_010  (from 2026-05-24)
- work_item:ticket_027 due_on = 2026-05-29  <- jira work_item:ticket_027.due_on  (from 2026-05-24)
- work_item:ticket_027 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_027.component_id  (from 2026-05-24)
- work_item:ticket_027 owns_work_item = employee:emp_021 (Kerem Visser)  <- jira work_item:ticket_027.owner_id  (from 2026-05-24)
- work_item:ticket_027 work_item_status = in_progress  <- jira work_item:ticket_027.status  (from 2026-05-24)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_021 (Kerem Visser) has_skill = react  <- jira comment:comment_001  (from 2026-08-11)
- employee:emp_021 (Kerem Visser) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'}  <- frappe leave:leave_032  (from 2027-01-26)

### scenario_011 — tier fragmented, free_text_responsibility, modifiers none

- asked: leave leave_010, now 2026-06-12T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-06-10 … 2026-06-23

#### Key

- stable interval 2026-06-10 … 2026-06-15
- required sources: corpus, frappe, jira
- impact responsibility on clause:clause_011 (leave leave_010) -> outcome **assign**
    - must assess emp_018 (Yusuf Muller): **viable** (no reason)
    - must assess emp_001 (Hanna Patel): **non_viable** (skill)
- constraint clause_012 applies to clause:clause_011
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-06-12, the generator's own assessment over every employee)

- impact responsibility on clause_011: required 1; viable 2, unknown 2, non-viable 24 -> **assign**, agrees with the key
    - need: clause:clause_012 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'ios'}]} <- corpus
    - viable: emp_018 (Yusuf Muller), emp_020 (Yusuf Chen)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_001 (Hanna Patel): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz) [the leaver]: non-viable, availability (employee:emp_026 (Ines Yilmaz) on_leave = {'start': '2026-06-16', 'end': '2026-06-19'} <- frappe; employee:emp_026 (Ines Yilmaz) has_skill = ios <- frappe)
    - emp_027 (Bob Rossi): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-06-12, every employee's facts the criteria read, no rule applied)

- impact responsibility on clause_011
    - need window: 2026-06-16 … 2026-06-19 (the investigated leave's span)
    - constraint clause_012 names clause:clause_011; clause:clause_012 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'ios'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz) [the leaver]: components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [2026-06-16 … 2026-06-19]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_010: emp_026 (Ines Yilmaz) 2026-06-16 … 2026-06-19, annual, approved (observable from 2026-06-10)
- document doc_011 "Copperfield account notes": client_note, effective from 2026-06-10 (observable from 2026-06-10)
    - section clause_011: Ines Yilmaz is the contact responsible for the Copperfield account.
- document doc_012 "Account handover procedure: Copperfield": procedure, effective from 2026-06-10 (observable from 2026-06-10)
    - section clause_012: The contact named in the Copperfield account notes needs iOS experience.

#### Authored facts

- clause:clause_012 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'ios'}]}  <- corpus clause:clause_012  (from 2026-06-10)
- clause:clause_011 names_responsible = employee:emp_026 (Ines Yilmaz)  <- corpus clause:clause_011  (from 2026-06-10)

#### Fact base, cited entries (in the dated view)

- clause:clause_011 names_responsible = employee:emp_026 (Ines Yilmaz)  <- corpus clause:clause_011  (from 2026-06-10)
- clause:clause_012 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'ios'}]}  <- corpus clause:clause_012  (from 2026-06-10)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) employed_as = employee  <- frappe employee:emp_018 (Yusuf Muller).employment_type  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = android  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = graphql  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = ios  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = java  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) located_in = Amsterdam  <- frappe employee:emp_018 (Yusuf Muller).location  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_018 (Yusuf Muller).team_id  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_018 (Yusuf Muller).manager_id  (from 2026-01-05)
- employee:emp_026 (Ines Yilmaz) employed_as = employee  <- frappe employee:emp_026 (Ines Yilmaz).employment_type  (from 2026-01-05)
- employee:emp_026 (Ines Yilmaz) has_skill = ios  <- frappe employee:emp_026 (Ines Yilmaz).skills  (from 2026-01-05)
- employee:emp_026 (Ines Yilmaz) has_skill = java  <- frappe employee:emp_026 (Ines Yilmaz).skills  (from 2026-01-05)
- employee:emp_026 (Ines Yilmaz) located_in = Amsterdam  <- frappe employee:emp_026 (Ines Yilmaz).location  (from 2026-01-05)
- employee:emp_026 (Ines Yilmaz) member_of_component = component:comp_005 (Event Ingestion)  <- jira component:comp_005 (Event Ingestion).member_ids  (from 2026-01-05)
- employee:emp_026 (Ines Yilmaz) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_026 (Ines Yilmaz).team_id  (from 2026-01-05)
- employee:emp_026 (Ines Yilmaz) on_leave = {'start': '2026-06-16', 'end': '2026-06-19'}  <- frappe leave:leave_010  (from 2026-06-10)
- employee:emp_026 (Ines Yilmaz) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_026 (Ines Yilmaz).manager_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_018 (Yusuf Muller) on_leave = {'start': '2026-11-03', 'end': '2026-11-04'}  <- frappe leave:leave_013  (from 2026-10-26)

#### Prose targets

##### clause_011 — client_note in doc_011, position 0
- accepted on attempt 1; request `1b6e3d9f`, body `1e3bfb2e`
- required (answer_changing): clause:clause_011 names_responsible = employee:emp_026 (Ines Yilmaz)  <- corpus clause:clause_011  (from 2026-06-10)
- propositions read: clause_011 names_responsible employee:emp_026 (Ines Yilmaz) [affirmed/asserted]

> Ines Yilmaz is the contact responsible for the Copperfield account.

### scenario_012 — tier fragmented, free_text_responsibility, modifiers timezone_boundary, concurrent_leave

- asked: leave leave_011, now 2026-06-30T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-06-26 … 2026-07-09

#### Key

- stable interval 2026-06-26 … 2026-07-03
- required sources: corpus, frappe, jira
- impact responsibility on clause:clause_013 (leave leave_011) -> outcome **assign**
    - must assess emp_002 (Yusuf Costa): **non_viable** (skill)
    - must assess emp_006 (Jonas Moreau): **non_viable** (availability)
- constraint clause_014 applies to clause:clause_013
- distractor event:event_003: timezone_boundary
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-06-30, the generator's own assessment over every employee)

- impact responsibility on clause_013: required 1; viable 5, unknown 2, non-viable 21 -> **assign**, agrees with the key
    - need: clause:clause_014 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]} <- corpus
    - viable: emp_007 (Jonas Novak), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_020 (Yusuf Chen)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_001 (Hanna Patel) [the leaver]: non-viable, availability (employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'} <- frappe; employee:emp_001 (Hanna Patel) has_skill = react <- frappe)
    - emp_002 (Yusuf Costa): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, availability (employee:emp_006 (Jonas Moreau) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'} <- frappe; employee:emp_006 (Jonas Moreau) has_skill = react <- frappe)
    - emp_008 (Liam Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-06-30, every employee's facts the criteria read, no rule applied)

- impact responsibility on clause_013
    - need window: 2026-07-04 … 2026-07-08 (the investigated leave's span)
    - constraint clause_014 names clause:clause_013; clause:clause_014 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]} <- corpus
    - emp_001 (Hanna Patel) [the leaver]: components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [2026-07-04 … 2026-07-08]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [2026-07-04 … 2026-07-08]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_011: emp_001 (Hanna Patel) 2026-07-04 … 2026-07-08, annual, approved (observable from 2026-06-26)
- leave leave_012: emp_006 (Jonas Moreau) 2026-07-04 … 2026-07-08, sick, approved (observable from 2026-06-26)
- event event_003 "Cross-region sync": 2026-07-08T17:00:00-04:00 [America/Toronto] … 2026-07-08T18:00:00-04:00 [America/Toronto], attendees emp_001 (Hanna Patel), emp_006 (Jonas Moreau) (observable from 2026-06-26)
- document doc_013 "Ashgrove account notes": client_note, effective from 2026-06-26 (observable from 2026-06-26)
    - section clause_013: Hanna Patel is the contact responsible for the Ashgrove account.
- document doc_014 "Account handover procedure: Ashgrove": procedure, effective from 2026-06-26 (observable from 2026-06-26)
    - section clause_014: The contact named in the Ashgrove account notes needs React experience.

#### Authored facts

- clause:clause_014 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]}  <- corpus clause:clause_014  (from 2026-06-26)
- clause:clause_013 names_responsible = employee:emp_001 (Hanna Patel)  <- corpus clause:clause_013  (from 2026-06-26)

#### Fact base, cited entries (in the dated view)

- clause:clause_013 names_responsible = employee:emp_001 (Hanna Patel)  <- corpus clause:clause_013  (from 2026-06-26)
- clause:clause_014 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]}  <- corpus clause:clause_014  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) employed_as = employee  <- frappe employee:emp_006 (Jonas Moreau).employment_type  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) has_skill = aws  <- frappe employee:emp_006 (Jonas Moreau).skills  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) has_skill = java  <- frappe employee:emp_006 (Jonas Moreau).skills  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) has_skill = python  <- frappe employee:emp_006 (Jonas Moreau).skills  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) has_skill = react  <- frappe employee:emp_006 (Jonas Moreau).skills  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) located_in = Toronto  <- frappe employee:emp_006 (Jonas Moreau).location  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_006 (Jonas Moreau).team_id  (from 2026-01-05)
- employee:emp_006 (Jonas Moreau) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_012  (from 2026-06-26)
- employee:emp_006 (Jonas Moreau) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_006 (Jonas Moreau).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)
- event:event_003 attends_event = employee:emp_001 (Hanna Patel)  <- calendar event:event_003.attendee_ids  (from 2026-06-26)
- event:event_003 attends_event = employee:emp_006 (Jonas Moreau)  <- calendar event:event_003.attendee_ids  (from 2026-06-26)
- event:event_003 scheduled_at = {'start': '2026-07-08T17:00:00-04:00', 'end': '2026-07-08T18:00:00-04:00', 'zone': 'America/Toronto'}  <- calendar event:event_003  (from 2026-06-26)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)

#### Prose targets

##### clause_013 — client_note in doc_013, position 0
- accepted on attempt 1; request `930dd5b7`, body `cd864ede`
- required (answer_changing): clause:clause_013 names_responsible = employee:emp_001 (Hanna Patel)  <- corpus clause:clause_013  (from 2026-06-26)
- propositions read: clause_013 names_responsible employee:emp_001 (Hanna Patel) [affirmed/asserted]

> Hanna Patel is the contact responsible for the Ashgrove account.

### scenario_013 — tier fragmented, fragmented_composite, modifiers none

- asked: leave leave_014, now 2026-07-16T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-07-12 … 2026-07-25

#### Key

- stable interval 2026-07-12 … 2026-07-17
- required sources: corpus, frappe, jira
- impact responsibility on clause:clause_017 (leave leave_014) -> outcome **assign**
    - must assess emp_001 (Hanna Patel): **viable** (no reason)
    - must assess emp_002 (Yusuf Costa): **non_viable** (skill)
- constraint clause_018 applies to clause:clause_017
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-07-16, the generator's own assessment over every employee)

- impact responsibility on clause_017: required 1; viable 2, unknown 2, non-viable 24 -> **assign**, agrees with the key
    - need: clause:clause_018 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'typescript'}]} <- corpus
    - viable: emp_001 (Hanna Patel), emp_024 (Yusuf Okafor)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_002 (Yusuf Costa): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt) [the leaver]: non-viable, availability (employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2026-07-18', 'end': '2026-07-21'} <- frappe; employee:emp_016 (Zeynep Schmidt) has_skill = typescript <- frappe)
    - emp_017 (Omar Demir): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-07-16, every employee's facts the criteria read, no rule applied)

- impact responsibility on clause_017
    - need window: 2026-07-18 … 2026-07-21 (the investigated leave's span)
    - constraint clause_018 names clause:clause_017; clause:clause_018 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'typescript'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt) [the leaver]: components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [2026-07-18 … 2026-07-21]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_014: emp_016 (Zeynep Schmidt) 2026-07-18 … 2026-07-21, annual, approved (observable from 2026-07-12)
- document doc_017 "Redfern account notes": client_note, effective from 2026-07-12 (observable from 2026-07-12)
    - section clause_017: Zeynep Schmidt is the contact responsible for the Redfern account. Hanna Patel has experience with TypeScript.
- document doc_018 "Account handover procedure: Redfern": procedure, effective from 2026-07-12 (observable from 2026-07-12)
    - section clause_018: The contact named in the Redfern account notes needs TypeScript experience.

#### Authored facts

- clause:clause_018 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'typescript'}]}  <- corpus clause:clause_018  (from 2026-07-12)
- clause:clause_017 names_responsible = employee:emp_016 (Zeynep Schmidt)  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)

#### Fact base, cited entries (in the dated view)

- clause:clause_017 names_responsible = employee:emp_016 (Zeynep Schmidt)  <- corpus clause:clause_017  (from 2026-07-12)
- clause:clause_018 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'typescript'}]}  <- corpus clause:clause_018  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) employed_as = employee  <- frappe employee:emp_016 (Zeynep Schmidt).employment_type  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) has_skill = spark  <- frappe employee:emp_016 (Zeynep Schmidt).skills  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) has_skill = typescript  <- frappe employee:emp_016 (Zeynep Schmidt).skills  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) located_in = Toronto  <- frappe employee:emp_016 (Zeynep Schmidt).location  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_016 (Zeynep Schmidt).team_id  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2026-07-18', 'end': '2026-07-21'}  <- frappe leave:leave_014  (from 2026-07-12)
- employee:emp_016 (Zeynep Schmidt) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_016 (Zeynep Schmidt).manager_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'}  <- frappe leave:leave_033  (from 2027-01-26)

#### Prose targets

##### clause_017 — client_note in doc_017, position 0
- accepted on attempt 4; request `344b1c20`, body `58a443b4`
- attempt 1: refused by extraction (2: 1 required_not_asserted, 1 untyped_proposition)
- attempt 2: refused by extraction (2: 1 required_not_asserted, 1 untyped_proposition)
- attempt 3: refused by extraction (2: 1 required_not_asserted, 1 untyped_proposition)
- required (answer_changing): clause:clause_017 names_responsible = employee:emp_016 (Zeynep Schmidt)  <- corpus clause:clause_017  (from 2026-07-12)
- required (answer_changing): employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- propositions read: clause_017 names_responsible employee:emp_016 (Zeynep Schmidt) [affirmed/asserted]; emp_001 (Hanna Patel) has_skill typescript [affirmed/asserted]

> Zeynep Schmidt is the contact responsible for the Redfern account. Hanna Patel has experience with TypeScript.

### scenario_014 — tier fragmented, fragmented_composite, modifiers timezone_boundary

- asked: leave leave_015, now 2026-08-01T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-07-27 … 2026-08-09

#### Key

- stable interval 2026-07-27 … 2026-08-02
- required sources: corpus, frappe, jira
- impact responsibility on clause:clause_019 (leave leave_015) -> outcome **assign**
    - must assess emp_003 (Nadia Fernandes): **viable** (no reason)
    - must assess emp_004 (Jonas Nakamura): **non_viable** (skill)
- constraint clause_020 applies to clause:clause_019
- distractor event:event_004: timezone_boundary
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-08-01, the generator's own assessment over every employee)

- impact responsibility on clause_019: required 1; viable 5, unknown 2, non-viable 21 -> **assign**, agrees with the key
    - need: clause:clause_020 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'elasticsearch'}]} <- corpus
    - viable: emp_001 (Hanna Patel), emp_002 (Yusuf Costa), emp_003 (Nadia Fernandes), emp_019 (Felix Muller), emp_027 (Bob Rossi)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_004 (Jonas Nakamura): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor) [the leaver]: non-viable, availability (employee:emp_024 (Yusuf Okafor) on_leave = {'start': '2026-08-03', 'end': '2026-08-07'} <- frappe; employee:emp_024 (Yusuf Okafor) has_skill = elasticsearch <- frappe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-08-01, every employee's facts the criteria read, no rule applied)

- impact responsibility on clause_019
    - need window: 2026-08-03 … 2026-08-07 (the investigated leave's span)
    - constraint clause_020 names clause:clause_019; clause:clause_020 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'elasticsearch'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor) [the leaver]: components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [2026-08-03 … 2026-08-07]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_015: emp_024 (Yusuf Okafor) 2026-08-03 … 2026-08-07, annual, approved (observable from 2026-07-27)
- event event_004 "Cross-region sync": 2026-08-07T17:00:00-04:00 [America/Toronto] … 2026-08-07T18:00:00-04:00 [America/Toronto], attendees emp_024 (Yusuf Okafor), emp_010 (Bob Yilmaz) (observable from 2026-07-27)
- document doc_019 "Silverpine account notes": client_note, effective from 2026-07-27 (observable from 2026-07-27)
    - section clause_019: Yusuf Okafor is the contact responsible for the Silverpine account. Nadia Fernandes has experience with Elasticsearch.
- document doc_020 "Account handover procedure: Silverpine": procedure, effective from 2026-07-27 (observable from 2026-07-27)
    - section clause_020: The contact named in the Silverpine account notes needs Elasticsearch experience.

#### Authored facts

- clause:clause_020 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'elasticsearch'}]}  <- corpus clause:clause_020  (from 2026-07-27)
- clause:clause_019 names_responsible = employee:emp_024 (Yusuf Okafor)  <- corpus clause:clause_019  (from 2026-07-27)
- employee:emp_003 (Nadia Fernandes) has_skill = elasticsearch  <- corpus clause:clause_019  (from 2026-07-27)

#### Fact base, cited entries (in the dated view)

- clause:clause_019 names_responsible = employee:emp_024 (Yusuf Okafor)  <- corpus clause:clause_019  (from 2026-07-27)
- clause:clause_020 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'elasticsearch'}]}  <- corpus clause:clause_020  (from 2026-07-27)
- employee:emp_003 (Nadia Fernandes) employed_as = employee  <- frappe employee:emp_003 (Nadia Fernandes).employment_type  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) has_skill = elasticsearch  <- corpus clause:clause_019  (from 2026-07-27)
- employee:emp_003 (Nadia Fernandes) has_skill = kafka  <- frappe employee:emp_003 (Nadia Fernandes).skills  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) has_skill = terraform  <- frappe employee:emp_003 (Nadia Fernandes).skills  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) located_in = Toronto  <- frappe employee:emp_003 (Nadia Fernandes).location  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_003 (Nadia Fernandes).team_id  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-01-13', 'end': '2026-01-16'}  <- frappe leave:leave_023  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_003 (Nadia Fernandes).manager_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) employed_as = employee  <- frappe employee:emp_024 (Yusuf Okafor).employment_type  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = android  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = elasticsearch  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = redis  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = typescript  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) located_in = Warsaw  <- frappe employee:emp_024 (Yusuf Okafor).location  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_024 (Yusuf Okafor).team_id  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) on_leave = {'start': '2026-08-03', 'end': '2026-08-07'}  <- frappe leave:leave_015  (from 2026-07-27)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)
- event:event_004 attends_event = employee:emp_010 (Bob Yilmaz)  <- calendar event:event_004.attendee_ids  (from 2026-07-27)
- event:event_004 attends_event = employee:emp_024 (Yusuf Okafor)  <- calendar event:event_004.attendee_ids  (from 2026-07-27)
- event:event_004 scheduled_at = {'start': '2026-08-07T17:00:00-04:00', 'end': '2026-08-07T18:00:00-04:00', 'zone': 'America/Toronto'}  <- calendar event:event_004  (from 2026-07-27)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-08-16', 'end': '2026-08-18'}  <- frappe leave:leave_028  (from 2026-08-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)

#### Prose targets

##### clause_019 — client_note in doc_019, position 0
- accepted on attempt 1; request `b6c5861e`, body `0739dc3e`
- required (answer_changing): clause:clause_019 names_responsible = employee:emp_024 (Yusuf Okafor)  <- corpus clause:clause_019  (from 2026-07-27)
- required (answer_changing): employee:emp_003 (Nadia Fernandes) has_skill = elasticsearch  <- corpus clause:clause_019  (from 2026-07-27)
- propositions read: clause_019 names_responsible employee:emp_024 (Yusuf Okafor) [affirmed/asserted]; emp_003 (Nadia Fernandes) has_skill elasticsearch [affirmed/asserted]

> Yusuf Okafor is the contact responsible for the Silverpine account. Nadia Fernandes has experience with Elasticsearch.

### scenario_015 — tier fragmented, free_text_qualification, modifiers none

- asked: leave leave_028, now 2026-08-12T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-08-11 … 2026-08-24

#### Key

- stable interval 2026-08-11 … 2026-08-15
- required sources: calendar, corpus, frappe, jira
- impact meeting on event:event_022 (leave leave_028) -> outcome **assign**
    - must assess emp_021 (Kerem Visser): **viable** (no reason)
    - must assess emp_002 (Yusuf Costa): **non_viable** (skill)
- constraint clause_021 applies to event:event_022
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-08-12, the generator's own assessment over every employee)

- impact meeting on event_022: required 1; viable 8, unknown 2, non-viable 18 -> **assign**, agrees with the key
    - need: clause:clause_021 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]} <- corpus
    - need: event:event_022 scheduled_at = {'start': '2026-08-16T09:00:00+03:00', 'end': '2026-08-16T10:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_001 (Hanna Patel), emp_006 (Jonas Moreau), emp_007 (Jonas Novak), emp_012 (Nadia Sharma), emp_013 (Mert Yilmaz), emp_014 (Kerem Haddad), emp_020 (Yusuf Chen), emp_021 (Kerem Visser)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_002 (Yusuf Costa): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes) [the leaver]: non-viable, availability, skill (employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-08-16', 'end': '2026-08-18'} <- frappe)
    - emp_004 (Jonas Nakamura): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-08-12, every employee's facts the criteria read, no rule applied)

- impact meeting on event_022
    - need window: 2026-08-16 … 2026-08-16 (the meeting's day in Europe/Istanbul)
    - constraint clause_021 names event:event_022; clause:clause_021 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes) [the leaver]: components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [2026-08-16 … 2026-08-18]; events on the window's days [event_022 {'start': '2026-08-16T09:00:00+03:00', 'end': '2026-08-16T10:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [event_022 {'start': '2026-08-16T09:00:00+03:00', 'end': '2026-08-16T10:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_028: emp_003 (Nadia Fernandes) 2026-08-16 … 2026-08-18, annual, approved (observable from 2026-08-11)
- work item ticket_028 "Notifications: migrate the retry queue behind the flag": owner emp_021 (Kerem Visser), in_progress, component comp_003 (Notifications), opened 2026-08-11, due 2026-08-17, resolved — (observable from 2026-08-11)
    - comment comment_001 by emp_021 (Kerem Visser) on 2026-08-11: [comment_001, 2026-08-11, emp_021 — Kerem Visser] I have experience with React, which is relevant to this ticket. I own this ticket in the Notifications component.
- event event_022 "Payments: customer escalation sync (part two)": 2026-08-16T09:00:00+03:00 [Europe/Istanbul] … 2026-08-16T10:00:00+03:00 [Europe/Istanbul], attendees emp_003 (Nadia Fernandes), emp_008 (Liam Haddad) (observable from 2026-08-11)
- document doc_021 "Release policy: Payments: customer escalation sync (part two)": policy, effective from 2026-08-11 (observable from 2026-08-11)
    - section clause_021: The Payments: customer escalation sync (part two) needs an engineer with React experience.

#### Authored facts

- clause:clause_021 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]}  <- corpus clause:clause_021  (from 2026-08-11)
- employee:emp_021 (Kerem Visser) has_skill = react  <- jira comment:comment_001  (from 2026-08-11)

#### Fact base, cited entries (in the dated view)

- clause:clause_021 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'react'}]}  <- corpus clause:clause_021  (from 2026-08-11)
- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) employed_as = employee  <- frappe employee:emp_003 (Nadia Fernandes).employment_type  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) has_skill = elasticsearch  <- corpus clause:clause_019  (from 2026-07-27)
- employee:emp_003 (Nadia Fernandes) has_skill = kafka  <- frappe employee:emp_003 (Nadia Fernandes).skills  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) has_skill = terraform  <- frappe employee:emp_003 (Nadia Fernandes).skills  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) located_in = Toronto  <- frappe employee:emp_003 (Nadia Fernandes).location  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_003 (Nadia Fernandes).team_id  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-01-13', 'end': '2026-01-16'}  <- frappe leave:leave_023  (from 2026-01-05)
- employee:emp_003 (Nadia Fernandes) on_leave = {'start': '2026-08-16', 'end': '2026-08-18'}  <- frappe leave:leave_028  (from 2026-08-11)
- employee:emp_003 (Nadia Fernandes) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_003 (Nadia Fernandes).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) employed_as = contractor  <- frappe employee:emp_021 (Kerem Visser).employment_type  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = java  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = kafka  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = postgresql  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = react  <- jira comment:comment_001  (from 2026-08-11)
- employee:emp_021 (Kerem Visser) located_in = Lisbon  <- frappe employee:emp_021 (Kerem Visser).location  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_021 (Kerem Visser).team_id  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) on_leave = {'start': '2026-05-29', 'end': '2026-05-31'}  <- frappe leave:leave_022  (from 2026-05-24)
- employee:emp_021 (Kerem Visser) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_021 (Kerem Visser).manager_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)
- event:event_022 attends_event = employee:emp_003 (Nadia Fernandes)  <- calendar event:event_022.attendee_ids  (from 2026-08-11)
- event:event_022 attends_event = employee:emp_008 (Liam Haddad)  <- calendar event:event_022.attendee_ids  (from 2026-08-11)
- event:event_022 scheduled_at = {'start': '2026-08-16T09:00:00+03:00', 'end': '2026-08-16T10:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_022  (from 2026-08-11)
- work_item:ticket_028 due_on = 2026-08-17  <- jira work_item:ticket_028.due_on  (from 2026-08-11)
- work_item:ticket_028 in_component = component:comp_003 (Notifications)  <- jira work_item:ticket_028.component_id  (from 2026-08-11)
- work_item:ticket_028 owns_work_item = employee:emp_021 (Kerem Visser)  <- jira work_item:ticket_028.owner_id  (from 2026-08-11)
- work_item:ticket_028 work_item_status = in_progress  <- jira work_item:ticket_028.status  (from 2026-08-11)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_021 (Kerem Visser) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'}  <- frappe leave:leave_032  (from 2027-01-26)

#### Prose targets

##### comment_001 — ticket_comment in ticket_028, position 0, by emp_021 (Kerem Visser) on 2026-08-11
- accepted on attempt 1; request `aba02ede`, body `d3f48747`
- required (answer_changing): employee:emp_021 (Kerem Visser) has_skill = react  <- jira comment:comment_001  (from 2026-08-11)
- allowed: work_item:ticket_028 owns_work_item = employee:emp_021 (Kerem Visser)  <- jira work_item:ticket_028.owner_id  (from 2026-08-11)
- allowed: work_item:ticket_028 in_component = component:comp_003 (Notifications)  <- jira work_item:ticket_028.component_id  (from 2026-08-11)
- propositions read: emp_021 (Kerem Visser) has_skill react [affirmed/asserted]; ticket_028 owns_work_item employee:emp_021 (Kerem Visser) [affirmed/asserted]; ticket_028 in_component component:comp_003 (Notifications) [affirmed/asserted]

> [comment_001, 2026-08-11, emp_021 — Kerem Visser] I have experience with React, which is relevant to this ticket. I own this ticket in the Notifications component.

### scenario_016 — tier fragmented, release_cardinality_constraint, modifiers wrong_team, already_resolved

- asked: leave leave_001, now 2026-08-30T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-08-27 … 2026-09-09

#### Key

- stable interval 2026-08-29 … 2026-09-01
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_001 (leave leave_001) -> outcome **assign**
    - must assess emp_011 (Felix Fernandes): **viable** (no reason)
    - must assess emp_012 (Nadia Sharma): **viable** (no reason)
    - must assess emp_025 (Yusuf Byrne): **non_viable** (hard_rule)
    - must assess emp_007 (Jonas Novak): **non_viable** (skill)
- constraint clause_001 applies to work_item:ticket_001
- distractor work_item:ticket_002: wrong_team
- distractor work_item:ticket_003: already_resolved

#### Outcome witness (dated view at 2026-08-30, the generator's own assessment over every employee)

- impact deadline on ticket_001: required 2; viable 2, unknown 0, non-viable 26 -> **assign**, agrees with the key
    - need: clause:clause_001 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]} <- corpus
    - need: work_item:ticket_001 in_component = component:comp_002 (Payments API) <- jira
    - viable: emp_011 (Felix Fernandes), emp_012 (Nadia Sharma)
    - emp_001 (Hanna Patel): non-viable, component, skill (employee:emp_001 (Hanna Patel) employed_as = employee <- frappe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (employee:emp_002 (Yusuf Costa) employed_as = employee <- frappe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (employee:emp_003 (Nadia Fernandes) employed_as = employee <- frappe)
    - emp_004 (Jonas Nakamura) [the leaver]: non-viable, availability, skill (employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'} <- frappe; employee:emp_004 (Jonas Nakamura) employed_as = employee <- frappe)
    - emp_005 (Omar Jansen): non-viable, component, skill (employee:emp_005 (Omar Jansen) employed_as = employee <- frappe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (employee:emp_006 (Jonas Moreau) employed_as = employee <- frappe)
    - emp_007 (Jonas Novak): non-viable, skill (employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_007 (Jonas Novak) employed_as = employee <- frappe)
    - emp_008 (Liam Haddad): non-viable, component, skill (employee:emp_008 (Liam Haddad) employed_as = employee <- frappe)
    - emp_009 (Priya Moreau): non-viable, component, skill (employee:emp_009 (Priya Moreau) employed_as = employee <- frappe)
    - emp_010 (Bob Yilmaz): non-viable, component, hard_rule, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (employee:emp_013 (Mert Yilmaz) employed_as = employee <- frappe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (employee:emp_014 (Kerem Haddad) employed_as = employee <- frappe)
    - emp_015 (Arjun Schmidt): non-viable, component (employee:emp_015 (Arjun Schmidt) employed_as = employee <- frappe)
    - emp_016 (Zeynep Schmidt): non-viable, component, skill (employee:emp_016 (Zeynep Schmidt) employed_as = employee <- frappe)
    - emp_017 (Omar Demir): non-viable, component, skill (employee:emp_017 (Omar Demir) employed_as = employee <- frappe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (employee:emp_018 (Yusuf Muller) employed_as = employee <- frappe)
    - emp_019 (Felix Muller): non-viable, component, skill (employee:emp_019 (Felix Muller) employed_as = employee <- frappe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (employee:emp_020 (Yusuf Chen) employed_as = employee <- frappe)
    - emp_021 (Kerem Visser): non-viable, component, hard_rule, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component, skill (employee:emp_022 (Arjun Haddad) employed_as = employee <- frappe)
    - emp_023 (Priya Haddad): non-viable, component, skill (employee:emp_023 (Priya Haddad) employed_as = employee <- frappe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (employee:emp_024 (Yusuf Okafor) employed_as = employee <- frappe)
    - emp_025 (Yusuf Byrne): non-viable, hard_rule (employee:emp_025 (Yusuf Byrne) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_025 (Yusuf Byrne) has_skill = kubernetes <- frappe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (employee:emp_026 (Ines Yilmaz) employed_as = employee <- frappe)
    - emp_027 (Bob Rossi): non-viable, component, skill (employee:emp_027 (Bob Rossi) employed_as = employee <- frappe)
    - emp_028 (Chloe Okafor): non-viable, component (employee:emp_028 (Chloe Okafor) employed_as = employee <- frappe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-08-30, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_001
    - need window: 2026-09-02 … 2026-09-05 (the investigated leave's span)
    - artifact's component: work_item:ticket_001 in_component = component:comp_002 (Payments API) <- jira
    - constraint clause_001 names work_item:ticket_001; clause:clause_001 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura) [the leaver]: components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [2026-09-02 … 2026-09-05]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_001: emp_004 (Jonas Nakamura) 2026-09-02 … 2026-09-05, annual, approved (observable from 2026-08-27)
- work item ticket_001 "Payments API: retire the legacy endpoint for the mobile clients": owner emp_004 (Jonas Nakamura), in_progress, component comp_002 (Payments API), opened 2026-08-27, due 2026-09-02, resolved — (observable from 2026-08-27)
- work item ticket_002 "Payments API: refresh the dashboards for the new tenant": owner emp_007 (Jonas Novak), in_progress, component comp_002 (Payments API), opened 2026-08-27, due 2026-09-05, resolved — (observable from 2026-08-27)
- work item ticket_003 "Payments API: retire the legacy endpoint for the mobile clients, phase one": owner emp_004 (Jonas Nakamura), done, component comp_002 (Payments API), opened 2026-08-27, due 2026-09-05, resolved 2026-08-29 (observable from 2026-08-29)
- document doc_001 "Release policy: Payments API: retire the legacy endpoint for the mobile clients": policy, effective from 2026-08-27 (observable from 2026-08-27)
    - section clause_001: The Payments API: retire the legacy endpoint for the mobile clients release needs two engineers with Kubernetes experience, each an employee of the company.

#### Authored facts

- clause:clause_001 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]}  <- corpus clause:clause_001  (from 2026-08-27)

#### Fact base, cited entries (in the dated view)

- clause:clause_001 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]}  <- corpus clause:clause_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) employed_as = employee  <- frappe employee:emp_012 (Nadia Sharma).employment_type  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = android  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = kubernetes  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = react  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) located_in = Toronto  <- frappe employee:emp_012 (Nadia Sharma).location  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_012 (Nadia Sharma).team_id  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_012 (Nadia Sharma).manager_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) employed_as = contractor  <- frappe employee:emp_025 (Yusuf Byrne).employment_type  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = java  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kafka  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kubernetes  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) located_in = Warsaw  <- frappe employee:emp_025 (Yusuf Byrne).location  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_025 (Yusuf Byrne).team_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) on_leave = {'start': '2026-03-13', 'end': '2026-03-15'}  <- frappe leave:leave_025  (from 2026-03-07)
- employee:emp_025 (Yusuf Byrne) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_025 (Yusuf Byrne).manager_id  (from 2026-01-05)
- work_item:ticket_001 due_on = 2026-09-02  <- jira work_item:ticket_001.due_on  (from 2026-08-27)
- work_item:ticket_001 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_001.component_id  (from 2026-08-27)
- work_item:ticket_001 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_001.owner_id  (from 2026-08-27)
- work_item:ticket_001 work_item_status = in_progress  <- jira work_item:ticket_001.status  (from 2026-08-27)
- work_item:ticket_002 due_on = 2026-09-05  <- jira work_item:ticket_002.due_on  (from 2026-08-27)
- work_item:ticket_002 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_002.component_id  (from 2026-08-27)
- work_item:ticket_002 owns_work_item = employee:emp_007 (Jonas Novak)  <- jira work_item:ticket_002.owner_id  (from 2026-08-27)
- work_item:ticket_002 work_item_status = in_progress  <- jira work_item:ticket_002.status  (from 2026-08-27)
- work_item:ticket_003 due_on = 2026-09-05  <- jira work_item:ticket_003.due_on  (from 2026-08-29)
- work_item:ticket_003 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_003.component_id  (from 2026-08-29)
- work_item:ticket_003 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_003.owner_id  (from 2026-08-29)
- work_item:ticket_003 work_item_status = done  <- jira work_item:ticket_003.status  (from 2026-08-29)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)
- employee:emp_012 (Nadia Sharma) has_skill = postgresql  <- jira comment:comment_002  (from 2026-09-26)
- employee:emp_012 (Nadia Sharma) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_030  (from 2026-09-26)

### scenario_017 — tier fragmented, release_cardinality_constraint, modifiers wrong_team, already_resolved

- asked: leave leave_002, now 2026-09-12T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-09-11 … 2026-09-24

#### Key

- stable interval 2026-09-11 … 2026-09-15
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_004 (leave leave_002) -> outcome **assign**
    - must assess emp_011 (Felix Fernandes): **viable** (no reason)
    - must assess emp_012 (Nadia Sharma): **viable** (no reason)
    - must assess emp_025 (Yusuf Byrne): **non_viable** (hard_rule)
    - must assess emp_007 (Jonas Novak): **non_viable** (skill)
- constraint clause_002 applies to work_item:ticket_004
- distractor work_item:ticket_005: wrong_team
- distractor work_item:ticket_006: already_resolved

#### Outcome witness (dated view at 2026-09-12, the generator's own assessment over every employee)

- impact deadline on ticket_004: required 2; viable 2, unknown 0, non-viable 26 -> **assign**, agrees with the key
    - need: clause:clause_002 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]} <- corpus
    - need: work_item:ticket_004 in_component = component:comp_002 (Payments API) <- jira
    - viable: emp_011 (Felix Fernandes), emp_012 (Nadia Sharma)
    - emp_001 (Hanna Patel): non-viable, component, skill (employee:emp_001 (Hanna Patel) employed_as = employee <- frappe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (employee:emp_002 (Yusuf Costa) employed_as = employee <- frappe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (employee:emp_003 (Nadia Fernandes) employed_as = employee <- frappe)
    - emp_004 (Jonas Nakamura) [the leaver]: non-viable, availability, skill (employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'} <- frappe; employee:emp_004 (Jonas Nakamura) employed_as = employee <- frappe)
    - emp_005 (Omar Jansen): non-viable, component, skill (employee:emp_005 (Omar Jansen) employed_as = employee <- frappe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (employee:emp_006 (Jonas Moreau) employed_as = employee <- frappe)
    - emp_007 (Jonas Novak): non-viable, skill (employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_007 (Jonas Novak) employed_as = employee <- frappe)
    - emp_008 (Liam Haddad): non-viable, component, skill (employee:emp_008 (Liam Haddad) employed_as = employee <- frappe)
    - emp_009 (Priya Moreau): non-viable, component, skill (employee:emp_009 (Priya Moreau) employed_as = employee <- frappe)
    - emp_010 (Bob Yilmaz): non-viable, component, hard_rule, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (employee:emp_013 (Mert Yilmaz) employed_as = employee <- frappe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (employee:emp_014 (Kerem Haddad) employed_as = employee <- frappe)
    - emp_015 (Arjun Schmidt): non-viable, component (employee:emp_015 (Arjun Schmidt) employed_as = employee <- frappe)
    - emp_016 (Zeynep Schmidt): non-viable, component, skill (employee:emp_016 (Zeynep Schmidt) employed_as = employee <- frappe)
    - emp_017 (Omar Demir): non-viable, component, skill (employee:emp_017 (Omar Demir) employed_as = employee <- frappe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (employee:emp_018 (Yusuf Muller) employed_as = employee <- frappe)
    - emp_019 (Felix Muller): non-viable, component, skill (employee:emp_019 (Felix Muller) employed_as = employee <- frappe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (employee:emp_020 (Yusuf Chen) employed_as = employee <- frappe)
    - emp_021 (Kerem Visser): non-viable, component, hard_rule, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component, skill (employee:emp_022 (Arjun Haddad) employed_as = employee <- frappe)
    - emp_023 (Priya Haddad): non-viable, component, skill (employee:emp_023 (Priya Haddad) employed_as = employee <- frappe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (employee:emp_024 (Yusuf Okafor) employed_as = employee <- frappe)
    - emp_025 (Yusuf Byrne): non-viable, hard_rule (employee:emp_025 (Yusuf Byrne) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_025 (Yusuf Byrne) has_skill = kubernetes <- frappe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (employee:emp_026 (Ines Yilmaz) employed_as = employee <- frappe)
    - emp_027 (Bob Rossi): non-viable, component, skill (employee:emp_027 (Bob Rossi) employed_as = employee <- frappe)
    - emp_028 (Chloe Okafor): non-viable, component (employee:emp_028 (Chloe Okafor) employed_as = employee <- frappe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-09-12, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_004
    - need window: 2026-09-16 … 2026-09-17 (the investigated leave's span)
    - artifact's component: work_item:ticket_004 in_component = component:comp_002 (Payments API) <- jira
    - constraint clause_002 names work_item:ticket_004; clause:clause_002 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura) [the leaver]: components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [2026-09-16 … 2026-09-17]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_002: emp_004 (Jonas Nakamura) 2026-09-16 … 2026-09-17, annual, approved (observable from 2026-09-11)
- work item ticket_004 "Payments API: retire the legacy endpoint for the EU region": owner emp_004 (Jonas Nakamura), in_progress, component comp_002 (Payments API), opened 2026-09-11, due 2026-09-17, resolved — (observable from 2026-09-11)
- work item ticket_005 "Payments API: clean up stale branches for the mobile clients": owner emp_011 (Felix Fernandes), in_progress, component comp_002 (Payments API), opened 2026-09-11, due 2026-09-17, resolved — (observable from 2026-09-11)
- work item ticket_006 "Payments API: retire the legacy endpoint for the EU region, phase one": owner emp_004 (Jonas Nakamura), done, component comp_002 (Payments API), opened 2026-09-11, due 2026-09-16, resolved 2026-09-11 (observable from 2026-09-11)
- document doc_002 "Release policy: Payments API: retire the legacy endpoint for the EU region": policy, effective from 2026-09-11 (observable from 2026-09-11)
    - section clause_002: The Payments API: retire the legacy endpoint for the EU region release needs two engineers with Kubernetes experience, each an employee of the company.

#### Authored facts

- clause:clause_002 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]}  <- corpus clause:clause_002  (from 2026-09-11)

#### Fact base, cited entries (in the dated view)

- clause:clause_002 requires = {'count': 2, 'criteria': [{'kind': 'employment_type', 'employment_type': 'employee'}, {'kind': 'skill', 'skill': 'kubernetes'}]}  <- corpus clause:clause_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) employed_as = employee  <- frappe employee:emp_012 (Nadia Sharma).employment_type  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = android  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = kubernetes  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = react  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) located_in = Toronto  <- frappe employee:emp_012 (Nadia Sharma).location  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_012 (Nadia Sharma).team_id  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_012 (Nadia Sharma).manager_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) employed_as = contractor  <- frappe employee:emp_025 (Yusuf Byrne).employment_type  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = java  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kafka  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) has_skill = kubernetes  <- frappe employee:emp_025 (Yusuf Byrne).skills  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) located_in = Warsaw  <- frappe employee:emp_025 (Yusuf Byrne).location  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_025 (Yusuf Byrne).team_id  (from 2026-01-05)
- employee:emp_025 (Yusuf Byrne) on_leave = {'start': '2026-03-13', 'end': '2026-03-15'}  <- frappe leave:leave_025  (from 2026-03-07)
- employee:emp_025 (Yusuf Byrne) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_025 (Yusuf Byrne).manager_id  (from 2026-01-05)
- work_item:ticket_004 due_on = 2026-09-17  <- jira work_item:ticket_004.due_on  (from 2026-09-11)
- work_item:ticket_004 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_004.component_id  (from 2026-09-11)
- work_item:ticket_004 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_004.owner_id  (from 2026-09-11)
- work_item:ticket_004 work_item_status = in_progress  <- jira work_item:ticket_004.status  (from 2026-09-11)
- work_item:ticket_005 due_on = 2026-09-17  <- jira work_item:ticket_005.due_on  (from 2026-09-11)
- work_item:ticket_005 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_005.component_id  (from 2026-09-11)
- work_item:ticket_005 owns_work_item = employee:emp_011 (Felix Fernandes)  <- jira work_item:ticket_005.owner_id  (from 2026-09-11)
- work_item:ticket_005 work_item_status = in_progress  <- jira work_item:ticket_005.status  (from 2026-09-11)
- work_item:ticket_006 due_on = 2026-09-16  <- jira work_item:ticket_006.due_on  (from 2026-09-11)
- work_item:ticket_006 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_006.component_id  (from 2026-09-11)
- work_item:ticket_006 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_006.owner_id  (from 2026-09-11)
- work_item:ticket_006 work_item_status = done  <- jira work_item:ticket_006.status  (from 2026-09-11)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)
- employee:emp_012 (Nadia Sharma) has_skill = postgresql  <- jira comment:comment_002  (from 2026-09-26)
- employee:emp_012 (Nadia Sharma) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_030  (from 2026-09-26)

### scenario_018 — tier fragmented, free_text_qualification, modifiers outside_window, concurrent_leave

- asked: leave leave_029, now 2026-10-01T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-09-26 … 2026-10-09

#### Key

- stable interval 2026-09-26 … 2026-10-03
- required sources: calendar, corpus, frappe, jira
- impact meeting on event:event_023 (leave leave_029) -> outcome **assign**
    - must assess emp_001 (Hanna Patel): **non_viable** (skill)
    - must assess emp_012 (Nadia Sharma): **non_viable** (availability)
- constraint clause_022 applies to event:event_023
- distractor event:event_024: outside_window
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-10-01, the generator's own assessment over every employee)

- impact meeting on event_023: required 1; viable 2, unknown 2, non-viable 24 -> **assign**, agrees with the key
    - need: clause:clause_022 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'postgresql'}]} <- corpus
    - need: event:event_023 scheduled_at = {'start': '2026-10-04T13:00:00+03:00', 'end': '2026-10-04T14:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_008 (Liam Haddad), emp_021 (Kerem Visser)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_001 (Hanna Patel): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa) [the leaver]: non-viable, availability, skill (employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'} <- frappe)
    - emp_003 (Nadia Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, availability (employee:emp_012 (Nadia Sharma) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'} <- frappe; employee:emp_012 (Nadia Sharma) has_skill = postgresql <- jira)
    - emp_013 (Mert Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-10-01, every employee's facts the criteria read, no rule applied)

- impact meeting on event_023
    - need window: 2026-10-04 … 2026-10-04 (the meeting's day in Europe/Istanbul)
    - constraint clause_022 names event:event_023; clause:clause_022 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'postgresql'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa) [the leaver]: components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [2026-10-04 … 2026-10-05]; events on the window's days [event_023 {'start': '2026-10-04T13:00:00+03:00', 'end': '2026-10-04T14:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [2026-10-04 … 2026-10-05]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [event_023 {'start': '2026-10-04T13:00:00+03:00', 'end': '2026-10-04T14:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_029: emp_002 (Yusuf Costa) 2026-10-04 … 2026-10-05, annual, approved (observable from 2026-09-26)
- leave leave_030: emp_012 (Nadia Sharma) 2026-10-04 … 2026-10-05, sick, approved (observable from 2026-09-26)
- work item ticket_029 "Payments API: close the audit findings behind the flag": owner emp_012 (Nadia Sharma), in_progress, component comp_002 (Payments API), opened 2026-09-26, due 2026-10-04, resolved — (observable from 2026-09-26)
    - comment comment_002 by emp_012 (Nadia Sharma) on 2026-09-26: [comment_002, 2026-09-26, emp_012 — Nadia Sharma] I have experience with PostgreSQL, which is relevant to this ticket.
- event event_023 "Mobile: quarterly planning (part two)": 2026-10-04T13:00:00+03:00 [Europe/Istanbul] … 2026-10-04T14:00:00+03:00 [Europe/Istanbul], attendees emp_002 (Yusuf Costa), emp_028 (Chloe Okafor) (observable from 2026-09-26)
- event event_024 "Mobile: quarterly planning (part two) (debrief)": 2026-10-06T13:00:00+03:00 [Europe/Istanbul] … 2026-10-06T14:00:00+03:00 [Europe/Istanbul], attendees emp_002 (Yusuf Costa), emp_028 (Chloe Okafor) (observable from 2026-09-26)
- document doc_022 "Release policy: Mobile: quarterly planning (part two)": policy, effective from 2026-09-26 (observable from 2026-09-26)
    - section clause_022: The Mobile: quarterly planning (part two) needs an engineer with PostgreSQL experience.

#### Authored facts

- clause:clause_022 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'postgresql'}]}  <- corpus clause:clause_022  (from 2026-09-26)
- employee:emp_012 (Nadia Sharma) has_skill = postgresql  <- jira comment:comment_002  (from 2026-09-26)

#### Fact base, cited entries (in the dated view)

- clause:clause_022 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'postgresql'}]}  <- corpus clause:clause_022  (from 2026-09-26)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) employed_as = employee  <- frappe employee:emp_012 (Nadia Sharma).employment_type  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = android  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = kubernetes  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) has_skill = postgresql  <- jira comment:comment_002  (from 2026-09-26)
- employee:emp_012 (Nadia Sharma) has_skill = react  <- frappe employee:emp_012 (Nadia Sharma).skills  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) located_in = Toronto  <- frappe employee:emp_012 (Nadia Sharma).location  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_012 (Nadia Sharma).team_id  (from 2026-01-05)
- employee:emp_012 (Nadia Sharma) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_030  (from 2026-09-26)
- employee:emp_012 (Nadia Sharma) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_012 (Nadia Sharma).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)
- event:event_023 attends_event = employee:emp_002 (Yusuf Costa)  <- calendar event:event_023.attendee_ids  (from 2026-09-26)
- event:event_023 attends_event = employee:emp_028 (Chloe Okafor)  <- calendar event:event_023.attendee_ids  (from 2026-09-26)
- event:event_023 scheduled_at = {'start': '2026-10-04T13:00:00+03:00', 'end': '2026-10-04T14:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_023  (from 2026-09-26)
- event:event_024 attends_event = employee:emp_002 (Yusuf Costa)  <- calendar event:event_024.attendee_ids  (from 2026-09-26)
- event:event_024 attends_event = employee:emp_028 (Chloe Okafor)  <- calendar event:event_024.attendee_ids  (from 2026-09-26)
- event:event_024 scheduled_at = {'start': '2026-10-06T13:00:00+03:00', 'end': '2026-10-06T14:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_024  (from 2026-09-26)
- work_item:ticket_029 due_on = 2026-10-04  <- jira work_item:ticket_029.due_on  (from 2026-09-26)
- work_item:ticket_029 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_029.component_id  (from 2026-09-26)
- work_item:ticket_029 owns_work_item = employee:emp_012 (Nadia Sharma)  <- jira work_item:ticket_029.owner_id  (from 2026-09-26)
- work_item:ticket_029 work_item_status = in_progress  <- jira work_item:ticket_029.status  (from 2026-09-26)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)

#### Prose targets

##### comment_002 — ticket_comment in ticket_029, position 0, by emp_012 (Nadia Sharma) on 2026-09-26
- accepted on attempt 1; request `b7deac9a`, body `de73e7b6`
- required (answer_changing): employee:emp_012 (Nadia Sharma) has_skill = postgresql  <- jira comment:comment_002  (from 2026-09-26)
- allowed: work_item:ticket_029 owns_work_item = employee:emp_012 (Nadia Sharma)  <- jira work_item:ticket_029.owner_id  (from 2026-09-26)
- allowed: work_item:ticket_029 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_029.component_id  (from 2026-09-26)
- propositions read: emp_012 (Nadia Sharma) has_skill postgresql [affirmed/asserted]

> [comment_002, 2026-09-26, emp_012 — Nadia Sharma] I have experience with PostgreSQL, which is relevant to this ticket.

### scenario_019 — tier fragmented, free_text_qualification, modifiers outside_window

- asked: leave leave_031, now 2026-10-17T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-10-12 … 2026-10-25

#### Key

- stable interval 2026-10-12 … 2026-10-19
- required sources: calendar, corpus, frappe, jira
- impact meeting on event:event_025 (leave leave_031) -> outcome **assign**
    - must assess emp_007 (Jonas Novak): **viable** (no reason)
    - must assess emp_001 (Hanna Patel): **non_viable** (skill)
- constraint clause_023 applies to event:event_025
- distractor event:event_026: outside_window
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-10-17, the generator's own assessment over every employee)

- impact meeting on event_025: required 1; viable 10, unknown 2, non-viable 16 -> **assign**, agrees with the key
    - need: clause:clause_023 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]} <- corpus
    - need: event:event_025 scheduled_at = {'start': '2026-10-21T16:00:00+03:00', 'end': '2026-10-21T17:00:00+03:00', 'zone': 'Europe/Istanbul'} <- calendar
    - viable: emp_004 (Jonas Nakamura), emp_007 (Jonas Novak), emp_008 (Liam Haddad), emp_009 (Priya Moreau), emp_010 (Bob Yilmaz), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_017 (Omar Demir), emp_018 (Yusuf Muller), emp_024 (Yusuf Okafor)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_001 (Hanna Patel): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa) [the leaver]: non-viable, availability, skill (employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'} <- frappe)
    - emp_003 (Nadia Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-10-17, every employee's facts the criteria read, no rule applied)

- impact meeting on event_025
    - need window: 2026-10-21 … 2026-10-21 (the meeting's day in Europe/Istanbul)
    - constraint clause_023 names event:event_025; clause:clause_023 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa) [the leaver]: components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [2026-10-20 … 2026-10-22]; events on the window's days [event_025 {'start': '2026-10-21T16:00:00+03:00', 'end': '2026-10-21T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [event_025 {'start': '2026-10-21T16:00:00+03:00', 'end': '2026-10-21T17:00:00+03:00', 'zone': 'Europe/Istanbul'}]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_031: emp_002 (Yusuf Costa) 2026-10-20 … 2026-10-22, annual, approved (observable from 2026-10-12)
- work item ticket_030 "Payments API: close the audit findings ahead of the freeze": owner emp_007 (Jonas Novak), in_progress, component comp_002 (Payments API), opened 2026-10-12, due 2026-10-22, resolved — (observable from 2026-10-12)
    - comment comment_003 by emp_007 (Jonas Novak) on 2026-10-12: [comment_003, 2026-10-12, emp_007 — Jonas Novak] I have experience with Android. Since I own this ticket, I'm familiar with what the audit findings cover in the Payments API component.
- event event_025 "Mobile: sprint review (part two)": 2026-10-21T16:00:00+03:00 [Europe/Istanbul] … 2026-10-21T17:00:00+03:00 [Europe/Istanbul], attendees emp_002 (Yusuf Costa), emp_016 (Zeynep Schmidt) (observable from 2026-10-12)
- event event_026 "Mobile: sprint review (part two) (prep)": 2026-10-19T16:00:00+03:00 [Europe/Istanbul] … 2026-10-19T17:00:00+03:00 [Europe/Istanbul], attendees emp_002 (Yusuf Costa), emp_016 (Zeynep Schmidt) (observable from 2026-10-12)
- document doc_023 "Release policy: Mobile: sprint review (part two)": policy, effective from 2026-10-12 (observable from 2026-10-12)
    - section clause_023: The Mobile: sprint review (part two) needs an engineer with Android experience.

#### Authored facts

- clause:clause_023 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]}  <- corpus clause:clause_023  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)

#### Fact base, cited entries (in the dated view)

- clause:clause_023 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]}  <- corpus clause:clause_023  (from 2026-10-12)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)
- event:event_025 attends_event = employee:emp_002 (Yusuf Costa)  <- calendar event:event_025.attendee_ids  (from 2026-10-12)
- event:event_025 attends_event = employee:emp_016 (Zeynep Schmidt)  <- calendar event:event_025.attendee_ids  (from 2026-10-12)
- event:event_025 scheduled_at = {'start': '2026-10-21T16:00:00+03:00', 'end': '2026-10-21T17:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_025  (from 2026-10-12)
- event:event_026 attends_event = employee:emp_002 (Yusuf Costa)  <- calendar event:event_026.attendee_ids  (from 2026-10-12)
- event:event_026 attends_event = employee:emp_016 (Zeynep Schmidt)  <- calendar event:event_026.attendee_ids  (from 2026-10-12)
- event:event_026 scheduled_at = {'start': '2026-10-19T16:00:00+03:00', 'end': '2026-10-19T17:00:00+03:00', 'zone': 'Europe/Istanbul'}  <- calendar event:event_026  (from 2026-10-12)
- work_item:ticket_030 due_on = 2026-10-22  <- jira work_item:ticket_030.due_on  (from 2026-10-12)
- work_item:ticket_030 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_030.component_id  (from 2026-10-12)
- work_item:ticket_030 owns_work_item = employee:emp_007 (Jonas Novak)  <- jira work_item:ticket_030.owner_id  (from 2026-10-12)
- work_item:ticket_030 work_item_status = in_progress  <- jira work_item:ticket_030.status  (from 2026-10-12)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)

#### Prose targets

##### comment_003 — ticket_comment in ticket_030, position 0, by emp_007 (Jonas Novak) on 2026-10-12
- accepted on attempt 2; request `973cf0f8`, body `f3f5da32`
- attempt 1: refused by extraction (1: 1 not_permitted_fact)
- required (answer_changing): employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- allowed: work_item:ticket_030 owns_work_item = employee:emp_007 (Jonas Novak)  <- jira work_item:ticket_030.owner_id  (from 2026-10-12)
- allowed: work_item:ticket_030 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_030.component_id  (from 2026-10-12)
- propositions read: emp_007 (Jonas Novak) has_skill android [affirmed/asserted]; ticket_030 owns_work_item employee:emp_007 (Jonas Novak) [affirmed/asserted]; ticket_030 in_component component:comp_002 (Payments API) [affirmed/asserted]

> [comment_003, 2026-10-12, emp_007 — Jonas Novak] I have experience with Android. Since I own this ticket, I'm familiar with what the audit findings cover in the Payments API component.

### scenario_020 — tier fragmented, free_text_responsibility, modifiers none

- asked: leave leave_013, now 2026-11-01T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-10-26 … 2026-11-08

#### Key

- stable interval 2026-10-26 … 2026-11-02
- required sources: corpus, frappe, jira
- impact responsibility on clause:clause_015 (leave leave_013) -> outcome **assign**
    - must assess emp_024 (Yusuf Okafor): **viable** (no reason)
    - must assess emp_001 (Hanna Patel): **non_viable** (skill)
- constraint clause_016 applies to clause:clause_015
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)
- expected unknown for emp_028 (Chloe Okafor): has_skill of employee:emp_028 (Chloe Okafor) (absent)

#### Outcome witness (dated view at 2026-11-01, the generator's own assessment over every employee)

- impact responsibility on clause_015: required 1; viable 9, unknown 2, non-viable 17 -> **assign**, agrees with the key
    - need: clause:clause_016 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]} <- corpus
    - viable: emp_004 (Jonas Nakamura), emp_007 (Jonas Novak), emp_008 (Liam Haddad), emp_009 (Priya Moreau), emp_010 (Bob Yilmaz), emp_011 (Felix Fernandes), emp_012 (Nadia Sharma), emp_017 (Omar Demir), emp_024 (Yusuf Okafor)
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_028 (Chloe Okafor): unknown, has_skill of emp_028 (Chloe Okafor) (absent)
    - emp_001 (Hanna Patel): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller) [the leaver]: non-viable, availability (employee:emp_018 (Yusuf Muller) on_leave = {'start': '2026-11-03', 'end': '2026-11-04'} <- frappe; employee:emp_018 (Yusuf Muller) has_skill = android <- frappe)
    - emp_019 (Felix Muller): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-11-01, every employee's facts the criteria read, no rule applied)

- impact responsibility on clause_015
    - need window: 2026-11-03 … 2026-11-04 (the investigated leave's span)
    - constraint clause_016 names clause:clause_015; clause:clause_016 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller) [the leaver]: components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [2026-11-03 … 2026-11-04]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_013: emp_018 (Yusuf Muller) 2026-11-03 … 2026-11-04, annual, approved (observable from 2026-10-26)
- document doc_015 "Maplecroft account notes": client_note, effective from 2026-10-26 (observable from 2026-10-26)
    - section clause_015: Yusuf Muller is the contact responsible for the Maplecroft account.
- document doc_016 "Account handover procedure: Maplecroft": procedure, effective from 2026-10-26 (observable from 2026-10-26)
    - section clause_016: The contact named in the Maplecroft account notes needs Android experience.

#### Authored facts

- clause:clause_016 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]}  <- corpus clause:clause_016  (from 2026-10-26)
- clause:clause_015 names_responsible = employee:emp_018 (Yusuf Muller)  <- corpus clause:clause_015  (from 2026-10-26)

#### Fact base, cited entries (in the dated view)

- clause:clause_015 names_responsible = employee:emp_018 (Yusuf Muller)  <- corpus clause:clause_015  (from 2026-10-26)
- clause:clause_016 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'android'}]}  <- corpus clause:clause_016  (from 2026-10-26)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) employed_as = employee  <- frappe employee:emp_018 (Yusuf Muller).employment_type  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = android  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = graphql  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = ios  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) has_skill = java  <- frappe employee:emp_018 (Yusuf Muller).skills  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) located_in = Amsterdam  <- frappe employee:emp_018 (Yusuf Muller).location  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_018 (Yusuf Muller).team_id  (from 2026-01-05)
- employee:emp_018 (Yusuf Muller) on_leave = {'start': '2026-11-03', 'end': '2026-11-04'}  <- frappe leave:leave_013  (from 2026-10-26)
- employee:emp_018 (Yusuf Muller) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_018 (Yusuf Muller).manager_id  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) employed_as = employee  <- frappe employee:emp_024 (Yusuf Okafor).employment_type  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = android  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = elasticsearch  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = redis  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) has_skill = typescript  <- frappe employee:emp_024 (Yusuf Okafor).skills  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) located_in = Warsaw  <- frappe employee:emp_024 (Yusuf Okafor).location  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_024 (Yusuf Okafor).team_id  (from 2026-01-05)
- employee:emp_024 (Yusuf Okafor) on_leave = {'start': '2026-08-03', 'end': '2026-08-07'}  <- frappe leave:leave_015  (from 2026-07-27)
- employee:emp_028 (Chloe Okafor) employed_as = employee  <- frappe employee:emp_028 (Chloe Okafor).employment_type  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) has_skill = GAP  <- frappe employee:emp_028 (Chloe Okafor).skills  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) located_in = Warsaw  <- frappe employee:emp_028 (Chloe Okafor).location  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) member_of_team = team:team_001 (Platform)  <- frappe employee:emp_028 (Chloe Okafor).team_id  (from 2026-01-05)
- employee:emp_028 (Chloe Okafor) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_028 (Chloe Okafor).manager_id  (from 2026-01-05)

#### Prose targets

##### clause_015 — client_note in doc_015, position 0
- accepted on attempt 1; request `8c0d33b9`, body `2867f84a`
- required (answer_changing): clause:clause_015 names_responsible = employee:emp_018 (Yusuf Muller)  <- corpus clause:clause_015  (from 2026-10-26)
- propositions read: clause_015 names_responsible employee:emp_018 (Yusuf Muller) [affirmed/asserted]

> Yusuf Muller is the contact responsible for the Maplecroft account.

### scenario_021 — tier adversarial, missing_information, modifiers outside_window

- asked: leave leave_003, now 2026-11-12T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-11-11 … 2026-11-24

#### Key

- stable interval 2026-11-11 … 2026-11-15
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_007 (leave leave_003) -> outcome **unknown**
    - must assess emp_015 (Arjun Schmidt): **unknown** (no reason)
    - must assess emp_019 (Felix Muller): **non_viable** (skill)
- constraint clause_003 applies to work_item:ticket_007
- distractor work_item:ticket_008: outside_window
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)

#### Outcome witness (dated view at 2026-11-12, the generator's own assessment over every employee)

- impact deadline on ticket_007: required 1; viable 0, unknown 1, non-viable 27 -> **unknown**, agrees with the key
    - need: clause:clause_003 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - need: work_item:ticket_007 in_component = component:comp_001 (Mobile Release) <- jira
    - viable: none
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_001 (Hanna Patel): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes) [the leaver]: non-viable, availability, skill (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release) <- jira; employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'} <- frappe)
    - emp_012 (Nadia Sharma): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, skill (employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release) <- jira)
    - emp_020 (Yusuf Chen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-11-12, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_007
    - need window: 2026-11-16 … 2026-11-19 (the investigated leave's span)
    - artifact's component: work_item:ticket_007 in_component = component:comp_001 (Mobile Release) <- jira
    - constraint clause_003 names work_item:ticket_007; clause:clause_003 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes) [the leaver]: components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [2026-11-16 … 2026-11-19]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_003: emp_011 (Felix Fernandes) 2026-11-16 … 2026-11-19, annual, approved (observable from 2026-11-11)
- work item ticket_007 "Mobile Release: upgrade the client library": owner emp_011 (Felix Fernandes), in_progress, component comp_001 (Mobile Release), opened 2026-11-11, due 2026-11-17, resolved — (observable from 2026-11-11)
- work item ticket_008 "Mobile Release: upgrade the client library, groundwork": owner emp_011 (Felix Fernandes), in_progress, component comp_001 (Mobile Release), opened 2026-11-11, due 2026-11-15, resolved — (observable from 2026-11-11)
- document doc_003 "Release policy: Mobile Release: upgrade the client library": policy, effective from 2026-11-11 (observable from 2026-11-11)
    - section clause_003: The Mobile Release: upgrade the client library release needs an engineer with Google Cloud experience.

#### Authored facts

- clause:clause_003 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_003  (from 2026-11-11)

#### Fact base, cited entries (in the dated view)

- clause:clause_003 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) employed_as = employee  <- frappe employee:emp_019 (Felix Muller).employment_type  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = airflow  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = elasticsearch  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) located_in = Lisbon  <- frappe employee:emp_019 (Felix Muller).location  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_019 (Felix Muller).team_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-02-26', 'end': '2026-03-02'}  <- frappe leave:leave_024  (from 2026-02-21)
- employee:emp_019 (Felix Muller) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_019 (Felix Muller).manager_id  (from 2026-01-05)
- work_item:ticket_007 due_on = 2026-11-17  <- jira work_item:ticket_007.due_on  (from 2026-11-11)
- work_item:ticket_007 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_007.component_id  (from 2026-11-11)
- work_item:ticket_007 owns_work_item = employee:emp_011 (Felix Fernandes)  <- jira work_item:ticket_007.owner_id  (from 2026-11-11)
- work_item:ticket_007 work_item_status = in_progress  <- jira work_item:ticket_007.status  (from 2026-11-11)
- work_item:ticket_008 due_on = 2026-11-15  <- jira work_item:ticket_008.due_on  (from 2026-11-11)
- work_item:ticket_008 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_008.component_id  (from 2026-11-11)
- work_item:ticket_008 owns_work_item = employee:emp_011 (Felix Fernandes)  <- jira work_item:ticket_008.owner_id  (from 2026-11-11)
- work_item:ticket_008 work_item_status = in_progress  <- jira work_item:ticket_008.status  (from 2026-11-11)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-12-01', 'end': '2026-12-05'}  <- frappe leave:leave_004  (from 2026-11-25)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-01-18', 'end': '2027-01-21'}  <- frappe leave:leave_006  (from 2027-01-11)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-02-18', 'end': '2027-02-20'}  <- frappe leave:leave_005  (from 2027-02-12)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_035  (from 2027-02-28)

### scenario_022 — tier adversarial, missing_information, modifiers outside_window, timezone_boundary

- asked: leave leave_004, now 2026-11-28T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-11-25 … 2026-12-08

#### Key

- stable interval 2026-11-25 … 2026-11-30
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_009 (leave leave_004) -> outcome **unknown**
    - must assess emp_015 (Arjun Schmidt): **unknown** (no reason)
    - must assess emp_011 (Felix Fernandes): **non_viable** (skill)
- constraint clause_004 applies to work_item:ticket_009
- distractor work_item:ticket_010: outside_window
- distractor event:event_001: timezone_boundary
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)

#### Outcome witness (dated view at 2026-11-28, the generator's own assessment over every employee)

- impact deadline on ticket_009: required 1; viable 0, unknown 1, non-viable 27 -> **unknown**, agrees with the key
    - need: clause:clause_004 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - need: work_item:ticket_009 in_component = component:comp_001 (Mobile Release) <- jira
    - viable: none
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_001 (Hanna Patel): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release) <- jira)
    - emp_012 (Nadia Sharma): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller) [the leaver]: non-viable, availability, skill (employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release) <- jira; employee:emp_019 (Felix Muller) on_leave = {'start': '2026-12-01', 'end': '2026-12-05'} <- frappe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-11-28, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_009
    - need window: 2026-12-01 … 2026-12-05 (the investigated leave's span)
    - artifact's component: work_item:ticket_009 in_component = component:comp_001 (Mobile Release) <- jira
    - constraint clause_004 names work_item:ticket_009; clause:clause_004 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller) [the leaver]: components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [2026-12-01 … 2026-12-05]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_004: emp_019 (Felix Muller) 2026-12-01 … 2026-12-05, annual, approved (observable from 2026-11-25)
- work item ticket_009 "Mobile Release: retire the legacy endpoint for the mobile clients": owner emp_019 (Felix Muller), in_progress, component comp_001 (Mobile Release), opened 2026-11-25, due 2026-12-02, resolved — (observable from 2026-11-25)
- work item ticket_010 "Mobile Release: retire the legacy endpoint for the mobile clients, groundwork": owner emp_019 (Felix Muller), in_progress, component comp_001 (Mobile Release), opened 2026-11-25, due 2026-11-30, resolved — (observable from 2026-11-25)
- event event_001 "Cross-region sync": 2026-12-05T16:00:00-05:00 [America/Toronto] … 2026-12-05T17:00:00-05:00 [America/Toronto], attendees emp_019 (Felix Muller), emp_001 (Hanna Patel) (observable from 2026-11-25)
- document doc_004 "Release policy: Mobile Release: retire the legacy endpoint for the mobile clients": policy, effective from 2026-11-25 (observable from 2026-11-25)
    - section clause_004: The Mobile Release: retire the legacy endpoint for the mobile clients release needs an engineer with Google Cloud experience.

#### Authored facts

- clause:clause_004 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_004  (from 2026-11-25)

#### Fact base, cited entries (in the dated view)

- clause:clause_004 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_004  (from 2026-11-25)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) employed_as = employee  <- frappe employee:emp_019 (Felix Muller).employment_type  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = airflow  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = elasticsearch  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) located_in = Lisbon  <- frappe employee:emp_019 (Felix Muller).location  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_019 (Felix Muller).team_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-02-26', 'end': '2026-03-02'}  <- frappe leave:leave_024  (from 2026-02-21)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-12-01', 'end': '2026-12-05'}  <- frappe leave:leave_004  (from 2026-11-25)
- employee:emp_019 (Felix Muller) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_019 (Felix Muller).manager_id  (from 2026-01-05)
- event:event_001 attends_event = employee:emp_001 (Hanna Patel)  <- calendar event:event_001.attendee_ids  (from 2026-11-25)
- event:event_001 attends_event = employee:emp_019 (Felix Muller)  <- calendar event:event_001.attendee_ids  (from 2026-11-25)
- event:event_001 scheduled_at = {'start': '2026-12-05T16:00:00-05:00', 'end': '2026-12-05T17:00:00-05:00', 'zone': 'America/Toronto'}  <- calendar event:event_001  (from 2026-11-25)
- work_item:ticket_009 due_on = 2026-12-02  <- jira work_item:ticket_009.due_on  (from 2026-11-25)
- work_item:ticket_009 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_009.component_id  (from 2026-11-25)
- work_item:ticket_009 owns_work_item = employee:emp_019 (Felix Muller)  <- jira work_item:ticket_009.owner_id  (from 2026-11-25)
- work_item:ticket_009 work_item_status = in_progress  <- jira work_item:ticket_009.status  (from 2026-11-25)
- work_item:ticket_010 due_on = 2026-11-30  <- jira work_item:ticket_010.due_on  (from 2026-11-25)
- work_item:ticket_010 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_010.component_id  (from 2026-11-25)
- work_item:ticket_010 owns_work_item = employee:emp_019 (Felix Muller)  <- jira work_item:ticket_010.owner_id  (from 2026-11-25)
- work_item:ticket_010 work_item_status = in_progress  <- jira work_item:ticket_010.status  (from 2026-11-25)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-01-18', 'end': '2027-01-21'}  <- frappe leave:leave_006  (from 2027-01-11)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-02-18', 'end': '2027-02-20'}  <- frappe leave:leave_005  (from 2027-02-12)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_035  (from 2027-02-28)

### scenario_023 — tier adversarial, uncovered, modifiers none

- asked: leave leave_007, now 2026-12-13T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-12-12 … 2026-12-25

#### Key

- stable interval 2026-12-12 … 2026-12-16
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_015 (leave leave_007) -> outcome **uncovered**
    - must assess emp_004 (Jonas Nakamura): **non_viable** (skill)
    - must assess emp_001 (Hanna Patel): **non_viable** (component, skill)
    - must assess emp_015 (Arjun Schmidt): **non_viable** (component)
- constraint clause_008 applies to work_item:ticket_015

#### Outcome witness (dated view at 2026-12-13, the generator's own assessment over every employee)

- impact deadline on ticket_015: required 1; viable 0, unknown 0, non-viable 28 -> **uncovered**, agrees with the key
    - need: clause:clause_008 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - need: work_item:ticket_015 in_component = component:comp_004 (Billing) <- jira
    - viable: none
    - emp_001 (Hanna Patel): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, skill (employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_005 (Omar Jansen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, skill (employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_008 (Liam Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes) [the leaver]: non-viable, availability, skill (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing) <- jira; employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'} <- frappe)
    - emp_012 (Nadia Sharma): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (employee:emp_016 (Zeynep Schmidt) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_017 (Omar Demir): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_022 (Arjun Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-12-13, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_015
    - need window: 2026-12-17 … 2026-12-19 (the investigated leave's span)
    - artifact's component: work_item:ticket_015 in_component = component:comp_004 (Billing) <- jira
    - constraint clause_008 names work_item:ticket_015; clause:clause_008 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes) [the leaver]: components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [2026-12-17 … 2026-12-19]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_007: emp_011 (Felix Fernandes) 2026-12-17 … 2026-12-19, annual, approved (observable from 2026-12-12)
- work item ticket_015 "Billing: upgrade the client library ahead of the freeze": owner emp_011 (Felix Fernandes), in_progress, component comp_004 (Billing), opened 2026-12-12, due 2026-12-19, resolved — (observable from 2026-12-12)
- document doc_008 "Release policy: Billing: upgrade the client library ahead of the freeze": policy, effective from 2026-12-12 (observable from 2026-12-12)
    - section clause_008: The Billing: upgrade the client library ahead of the freeze release needs an engineer with Google Cloud experience.

#### Authored facts

- clause:clause_008 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_008  (from 2026-12-12)

#### Fact base, cited entries (in the dated view)

- clause:clause_008 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_008  (from 2026-12-12)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- work_item:ticket_015 due_on = 2026-12-19  <- jira work_item:ticket_015.due_on  (from 2026-12-12)
- work_item:ticket_015 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_015.component_id  (from 2026-12-12)
- work_item:ticket_015 owns_work_item = employee:emp_011 (Felix Fernandes)  <- jira work_item:ticket_015.owner_id  (from 2026-12-12)
- work_item:ticket_015 work_item_status = in_progress  <- jira work_item:ticket_015.status  (from 2026-12-12)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)

### scenario_024 — tier adversarial, uncovered, modifiers none

- asked: leave leave_008, now 2026-12-29T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2026-12-26 … 2027-01-08

#### Key

- stable interval 2026-12-26 … 2026-12-30
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_016 (leave leave_008) -> outcome **uncovered**
    - must assess emp_007 (Jonas Novak): **non_viable** (skill)
    - must assess emp_002 (Yusuf Costa): **non_viable** (component, skill)
    - must assess emp_015 (Arjun Schmidt): **non_viable** (component)
- constraint clause_009 applies to work_item:ticket_016

#### Outcome witness (dated view at 2026-12-29, the generator's own assessment over every employee)

- impact deadline on ticket_016: required 1; viable 0, unknown 0, non-viable 28 -> **uncovered**, agrees with the key
    - need: clause:clause_009 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - need: work_item:ticket_016 in_component = component:comp_004 (Billing) <- jira
    - viable: none
    - emp_001 (Hanna Patel): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura) [the leaver]: non-viable, availability, skill (employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing) <- jira; employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'} <- frappe)
    - emp_005 (Omar Jansen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, skill (employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_008 (Liam Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_012 (Nadia Sharma): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (employee:emp_016 (Zeynep Schmidt) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_017 (Omar Demir): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_022 (Arjun Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2026-12-29, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_016
    - need window: 2026-12-31 … 2027-01-02 (the investigated leave's span)
    - artifact's component: work_item:ticket_016 in_component = component:comp_004 (Billing) <- jira
    - constraint clause_009 names work_item:ticket_016; clause:clause_009 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura) [the leaver]: components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [2026-12-31 … 2027-01-02]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_008: emp_004 (Jonas Nakamura) 2026-12-31 … 2027-01-02, annual, approved (observable from 2026-12-26)
- work item ticket_016 "Billing: rotate the signing keys": owner emp_004 (Jonas Nakamura), in_progress, component comp_004 (Billing), opened 2026-12-26, due 2026-12-31, resolved — (observable from 2026-12-26)
- document doc_009 "Release policy: Billing: rotate the signing keys": policy, effective from 2026-12-26 (observable from 2026-12-26)
    - section clause_009: The Billing: rotate the signing keys release needs an engineer with Google Cloud experience.

#### Authored facts

- clause:clause_009 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_009  (from 2026-12-26)

#### Fact base, cited entries (in the dated view)

- clause:clause_009 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_009  (from 2026-12-26)
- employee:emp_002 (Yusuf Costa) employed_as = employee  <- frappe employee:emp_002 (Yusuf Costa).employment_type  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = elasticsearch  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = java  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) has_skill = kafka  <- frappe employee:emp_002 (Yusuf Costa).skills  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) located_in = Lisbon  <- frappe employee:emp_002 (Yusuf Costa).location  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_002 (Yusuf Costa).team_id  (from 2026-01-05)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-04', 'end': '2026-10-05'}  <- frappe leave:leave_029  (from 2026-09-26)
- employee:emp_002 (Yusuf Costa) on_leave = {'start': '2026-10-20', 'end': '2026-10-22'}  <- frappe leave:leave_031  (from 2026-10-12)
- employee:emp_002 (Yusuf Costa) reports_to = employee:emp_024 (Yusuf Okafor)  <- frappe employee:emp_002 (Yusuf Costa).manager_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- work_item:ticket_016 due_on = 2026-12-31  <- jira work_item:ticket_016.due_on  (from 2026-12-26)
- work_item:ticket_016 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_016.component_id  (from 2026-12-26)
- work_item:ticket_016 owns_work_item = employee:emp_004 (Jonas Nakamura)  <- jira work_item:ticket_016.owner_id  (from 2026-12-26)
- work_item:ticket_016 work_item_status = in_progress  <- jira work_item:ticket_016.status  (from 2026-12-26)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)

### scenario_025 — tier adversarial, adversarial_composite, modifiers timezone_boundary

- asked: leave leave_006, now 2027-01-16T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2027-01-11 … 2027-01-24

#### Key

- stable interval 2027-01-11 … 2027-01-17
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_014 (leave leave_006) -> outcome **unknown**
    - must assess emp_020 (Yusuf Chen): **non_viable** (component, skill)
    - must assess emp_015 (Arjun Schmidt): **unknown** (no reason)
    - must assess emp_011 (Felix Fernandes): **non_viable** (skill)
- constraint clause_006 applies to work_item:ticket_014
- distractor event:event_002: timezone_boundary
- expected conflict on work_item:ticket_014 owns_work_item: resolves to employee:emp_019 (Felix Muller) by system_of_record_wins
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)

#### Outcome witness (dated view at 2027-01-16, the generator's own assessment over every employee)

- impact deadline on ticket_014: required 1; viable 0, unknown 1, non-viable 27 -> **unknown**, agrees with the key
    - need: clause:clause_006 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - need: work_item:ticket_014 in_component = component:comp_001 (Mobile Release) <- jira
    - viable: none
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_001 (Hanna Patel): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release) <- jira)
    - emp_012 (Nadia Sharma): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller) [the leaver]: non-viable, availability, skill (employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release) <- jira; employee:emp_019 (Felix Muller) on_leave = {'start': '2027-01-18', 'end': '2027-01-21'} <- frappe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2027-01-16, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_014
    - need window: 2027-01-18 … 2027-01-21 (the investigated leave's span)
    - artifact's component: work_item:ticket_014 in_component = component:comp_001 (Mobile Release) <- jira
    - constraint clause_006 names work_item:ticket_014; clause:clause_006 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller) [the leaver]: components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [2027-01-18 … 2027-01-21]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_006: emp_019 (Felix Muller) 2027-01-18 … 2027-01-21, annual, approved (observable from 2027-01-11)
- work item ticket_014 "Mobile Release: upgrade the client library for the mobile clients": owner emp_019 (Felix Muller), in_progress, component comp_001 (Mobile Release), opened 2027-01-11, due 2027-01-20, resolved — (observable from 2027-01-11)
- event event_002 "Cross-region sync": 2027-01-21T16:00:00-05:00 [America/Toronto] … 2027-01-21T17:00:00-05:00 [America/Toronto], attendees emp_019 (Felix Muller), emp_008 (Liam Haddad) (observable from 2027-01-11)
- document doc_006 "Release policy: Mobile Release: upgrade the client library for the mobile clients": policy, effective from 2027-01-11 (observable from 2027-01-11)
    - section clause_006: The Mobile Release: upgrade the client library for the mobile clients release needs an engineer with Google Cloud experience.
- document doc_007 "Release runbook: Mobile Release: upgrade the client library for the mobile clients": runbook, effective from 2027-01-11 (observable from 2027-01-11)
    - section clause_007: Yusuf Chen owns the ticket Mobile Release: upgrade the client library for the mobile clients.

#### Authored facts

- clause:clause_006 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_006  (from 2027-01-11)
- work_item:ticket_014 owns_work_item = employee:emp_020 (Yusuf Chen)  <- corpus clause:clause_007  (from 2027-01-11)

#### Fact base, cited entries (in the dated view)

- clause:clause_006 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_006  (from 2027-01-11)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) employed_as = employee  <- frappe employee:emp_019 (Felix Muller).employment_type  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = airflow  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = elasticsearch  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) located_in = Lisbon  <- frappe employee:emp_019 (Felix Muller).location  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_019 (Felix Muller).team_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-02-26', 'end': '2026-03-02'}  <- frappe leave:leave_024  (from 2026-02-21)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-12-01', 'end': '2026-12-05'}  <- frappe leave:leave_004  (from 2026-11-25)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-01-18', 'end': '2027-01-21'}  <- frappe leave:leave_006  (from 2027-01-11)
- employee:emp_019 (Felix Muller) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_019 (Felix Muller).manager_id  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) employed_as = employee  <- frappe employee:emp_020 (Yusuf Chen).employment_type  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = ios  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = java  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = kafka  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = react  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) located_in = Lisbon  <- frappe employee:emp_020 (Yusuf Chen).location  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_020 (Yusuf Chen).team_id  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_020 (Yusuf Chen).manager_id  (from 2026-01-05)
- event:event_002 attends_event = employee:emp_008 (Liam Haddad)  <- calendar event:event_002.attendee_ids  (from 2027-01-11)
- event:event_002 attends_event = employee:emp_019 (Felix Muller)  <- calendar event:event_002.attendee_ids  (from 2027-01-11)
- event:event_002 scheduled_at = {'start': '2027-01-21T16:00:00-05:00', 'end': '2027-01-21T17:00:00-05:00', 'zone': 'America/Toronto'}  <- calendar event:event_002  (from 2027-01-11)
- work_item:ticket_014 due_on = 2027-01-20  <- jira work_item:ticket_014.due_on  (from 2027-01-11)
- work_item:ticket_014 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_014.component_id  (from 2027-01-11)
- work_item:ticket_014 owns_work_item = employee:emp_019 (Felix Muller)  <- jira work_item:ticket_014.owner_id  (from 2027-01-11)
- work_item:ticket_014 owns_work_item = employee:emp_020 (Yusuf Chen)  <- corpus clause:clause_007  (from 2027-01-11)
- work_item:ticket_014 work_item_status = in_progress  <- jira work_item:ticket_014.status  (from 2027-01-11)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-02-18', 'end': '2027-02-20'}  <- frappe leave:leave_005  (from 2027-02-12)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_035  (from 2027-02-28)

#### Prose targets

##### clause_007 — runbook in doc_007, position 0
- accepted on attempt 1; request `e4621dcb`, body `6f185b66`
- required (answer_changing): work_item:ticket_014 owns_work_item = employee:emp_020 (Yusuf Chen)  <- corpus clause:clause_007  (from 2027-01-11)
- propositions read: ticket_014 owns_work_item employee:emp_020 (Yusuf Chen) [affirmed/asserted]

> Yusuf Chen owns the ticket Mobile Release: upgrade the client library for the mobile clients.

### scenario_026 — tier adversarial, stale_source_conflict, modifiers wrong_team, concurrent_leave

- asked: leave leave_032, now 2027-01-29T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2027-01-26 … 2027-02-08

#### Key

- stable interval 2027-01-26 … 2027-01-30
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_031 (leave leave_032) -> outcome **assign**
    - must assess emp_020 (Yusuf Chen): **non_viable** (component)
    - must assess emp_016 (Zeynep Schmidt): **non_viable** (availability)
- distractor work_item:ticket_032: wrong_team
- expected conflict on work_item:ticket_031 owns_work_item: resolves to employee:emp_021 (Kerem Visser) by system_of_record_wins

#### Outcome witness (dated view at 2027-01-29, the generator's own assessment over every employee)

- impact deadline on ticket_031: required 1; viable 3, unknown 0, non-viable 25 -> **assign**, agrees with the key
    - need: work_item:ticket_031 in_component = component:comp_004 (Billing) <- jira
    - viable: emp_004 (Jonas Nakamura), emp_007 (Jonas Novak), emp_011 (Felix Fernandes)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_012 (Nadia Sharma): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, availability (employee:emp_016 (Zeynep Schmidt) member_of_component = component:comp_004 (Billing) <- jira; employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'} <- frappe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser) [the leaver]: non-viable, availability (employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing) <- jira; employee:emp_021 (Kerem Visser) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'} <- frappe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2027-01-29, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_031
    - need window: 2027-01-31 … 2027-02-01 (the investigated leave's span)
    - artifact's component: work_item:ticket_031 in_component = component:comp_004 (Billing) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [2027-01-31 … 2027-02-01]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser) [the leaver]: components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [2027-01-31 … 2027-02-01]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_032: emp_021 (Kerem Visser) 2027-01-31 … 2027-02-01, annual, approved (observable from 2027-01-26)
- leave leave_033: emp_016 (Zeynep Schmidt) 2027-01-31 … 2027-02-01, sick, approved (observable from 2027-01-26)
- work item ticket_031 "Billing: migrate the retry queue for the mobile clients": owner emp_021 (Kerem Visser), in_progress, component comp_004 (Billing), opened 2027-01-26, due 2027-02-01, resolved — (observable from 2027-01-26)
- work item ticket_032 "Billing: clean up stale branches behind the flag": owner emp_007 (Jonas Novak), in_progress, component comp_004 (Billing), opened 2027-01-26, due 2027-02-01, resolved — (observable from 2027-01-26)
- document doc_024 "Release runbook: Billing: migrate the retry queue for the mobile clients": runbook, effective from 2027-01-26 (observable from 2027-01-26)
    - section clause_024: Yusuf Chen owns the ticket Billing: migrate the retry queue for the mobile clients.

#### Authored facts

- work_item:ticket_031 owns_work_item = employee:emp_020 (Yusuf Chen)  <- corpus clause:clause_024  (from 2027-01-26)

#### Fact base, cited entries (in the dated view)

- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) employed_as = employee  <- frappe employee:emp_016 (Zeynep Schmidt).employment_type  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) has_skill = spark  <- frappe employee:emp_016 (Zeynep Schmidt).skills  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) has_skill = typescript  <- frappe employee:emp_016 (Zeynep Schmidt).skills  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) located_in = Toronto  <- frappe employee:emp_016 (Zeynep Schmidt).location  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) member_of_team = team:team_003 (Payments)  <- frappe employee:emp_016 (Zeynep Schmidt).team_id  (from 2026-01-05)
- employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2026-07-18', 'end': '2026-07-21'}  <- frappe leave:leave_014  (from 2026-07-12)
- employee:emp_016 (Zeynep Schmidt) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'}  <- frappe leave:leave_033  (from 2027-01-26)
- employee:emp_016 (Zeynep Schmidt) reports_to = employee:emp_003 (Nadia Fernandes)  <- frappe employee:emp_016 (Zeynep Schmidt).manager_id  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) employed_as = employee  <- frappe employee:emp_020 (Yusuf Chen).employment_type  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = ios  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = java  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = kafka  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) has_skill = react  <- frappe employee:emp_020 (Yusuf Chen).skills  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) located_in = Lisbon  <- frappe employee:emp_020 (Yusuf Chen).location  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_020 (Yusuf Chen).team_id  (from 2026-01-05)
- employee:emp_020 (Yusuf Chen) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_020 (Yusuf Chen).manager_id  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) employed_as = contractor  <- frappe employee:emp_021 (Kerem Visser).employment_type  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = java  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = kafka  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = postgresql  <- frappe employee:emp_021 (Kerem Visser).skills  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) has_skill = react  <- jira comment:comment_001  (from 2026-08-11)
- employee:emp_021 (Kerem Visser) located_in = Lisbon  <- frappe employee:emp_021 (Kerem Visser).location  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_021 (Kerem Visser).team_id  (from 2026-01-05)
- employee:emp_021 (Kerem Visser) on_leave = {'start': '2026-05-29', 'end': '2026-05-31'}  <- frappe leave:leave_022  (from 2026-05-24)
- employee:emp_021 (Kerem Visser) on_leave = {'start': '2027-01-31', 'end': '2027-02-01'}  <- frappe leave:leave_032  (from 2027-01-26)
- employee:emp_021 (Kerem Visser) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_021 (Kerem Visser).manager_id  (from 2026-01-05)
- work_item:ticket_031 due_on = 2027-02-01  <- jira work_item:ticket_031.due_on  (from 2027-01-26)
- work_item:ticket_031 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_031.component_id  (from 2027-01-26)
- work_item:ticket_031 owns_work_item = employee:emp_020 (Yusuf Chen)  <- corpus clause:clause_024  (from 2027-01-26)
- work_item:ticket_031 owns_work_item = employee:emp_021 (Kerem Visser)  <- jira work_item:ticket_031.owner_id  (from 2027-01-26)
- work_item:ticket_031 work_item_status = in_progress  <- jira work_item:ticket_031.status  (from 2027-01-26)
- work_item:ticket_032 due_on = 2027-02-01  <- jira work_item:ticket_032.due_on  (from 2027-01-26)
- work_item:ticket_032 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_032.component_id  (from 2027-01-26)
- work_item:ticket_032 owns_work_item = employee:emp_007 (Jonas Novak)  <- jira work_item:ticket_032.owner_id  (from 2027-01-26)
- work_item:ticket_032 work_item_status = in_progress  <- jira work_item:ticket_032.status  (from 2027-01-26)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)

#### Prose targets

##### clause_024 — runbook in doc_024, position 0
- accepted on attempt 1; request `ad56eb34`, body `d0ba24cb`
- required (answer_changing): work_item:ticket_031 owns_work_item = employee:emp_020 (Yusuf Chen)  <- corpus clause:clause_024  (from 2027-01-26)
- propositions read: ticket_031 owns_work_item employee:emp_020 (Yusuf Chen) [affirmed/asserted]

> Yusuf Chen owns the ticket Billing: migrate the retry queue for the mobile clients.

### scenario_027 — tier adversarial, missing_information, modifiers wrong_team, already_resolved

- asked: leave leave_005, now 2027-02-16T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2027-02-12 … 2027-02-25

#### Key

- stable interval 2027-02-15 … 2027-02-17
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_011 (leave leave_005) -> outcome **unknown**
    - must assess emp_015 (Arjun Schmidt): **unknown** (no reason)
    - must assess emp_011 (Felix Fernandes): **non_viable** (skill)
- constraint clause_005 applies to work_item:ticket_011
- distractor work_item:ticket_012: wrong_team
- distractor work_item:ticket_013: already_resolved
- expected unknown for emp_015 (Arjun Schmidt): has_skill of employee:emp_015 (Arjun Schmidt) (absent)

#### Outcome witness (dated view at 2027-02-16, the generator's own assessment over every employee)

- impact deadline on ticket_011: required 1; viable 0, unknown 1, non-viable 27 -> **unknown**, agrees with the key
    - need: clause:clause_005 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - need: work_item:ticket_011 in_component = component:comp_001 (Mobile Release) <- jira
    - viable: none
    - emp_015 (Arjun Schmidt): unknown, has_skill of emp_015 (Arjun Schmidt) (absent)
    - emp_001 (Hanna Patel): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release) <- jira)
    - emp_012 (Nadia Sharma): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller) [the leaver]: non-viable, availability, skill (employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release) <- jira; employee:emp_019 (Felix Muller) on_leave = {'start': '2027-02-18', 'end': '2027-02-20'} <- frappe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2027-02-16, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_011
    - need window: 2027-02-18 … 2027-02-20 (the investigated leave's span)
    - artifact's component: work_item:ticket_011 in_component = component:comp_001 (Mobile Release) <- jira
    - constraint clause_005 names work_item:ticket_011; clause:clause_005 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller) [the leaver]: components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [2027-02-18 … 2027-02-20]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_005: emp_019 (Felix Muller) 2027-02-18 … 2027-02-20, annual, approved (observable from 2027-02-12)
- work item ticket_011 "Mobile Release: retire the legacy endpoint for the new tenant": owner emp_019 (Felix Muller), in_progress, component comp_001 (Mobile Release), opened 2027-02-12, due 2027-02-18, resolved — (observable from 2027-02-12)
- work item ticket_012 "Mobile Release: clean up stale branches for the EU region": owner emp_015 (Arjun Schmidt), in_progress, component comp_001 (Mobile Release), opened 2027-02-12, due 2027-02-19, resolved — (observable from 2027-02-12)
- work item ticket_013 "Mobile Release: retire the legacy endpoint for the new tenant, phase one": owner emp_019 (Felix Muller), done, component comp_001 (Mobile Release), opened 2027-02-12, due 2027-02-20, resolved 2027-02-15 (observable from 2027-02-15)
- document doc_005 "Release policy: Mobile Release: retire the legacy endpoint for the new tenant": policy, effective from 2027-02-12 (observable from 2027-02-12)
    - section clause_005: The Mobile Release: retire the legacy endpoint for the new tenant release needs an engineer with Google Cloud experience.

#### Authored facts

- clause:clause_005 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_005  (from 2027-02-12)

#### Fact base, cited entries (in the dated view)

- clause:clause_005 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_005  (from 2027-02-12)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) employed_as = employee  <- frappe employee:emp_019 (Felix Muller).employment_type  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = airflow  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = elasticsearch  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) located_in = Lisbon  <- frappe employee:emp_019 (Felix Muller).location  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_019 (Felix Muller).team_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-02-26', 'end': '2026-03-02'}  <- frappe leave:leave_024  (from 2026-02-21)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-12-01', 'end': '2026-12-05'}  <- frappe leave:leave_004  (from 2026-11-25)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-01-18', 'end': '2027-01-21'}  <- frappe leave:leave_006  (from 2027-01-11)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-02-18', 'end': '2027-02-20'}  <- frappe leave:leave_005  (from 2027-02-12)
- employee:emp_019 (Felix Muller) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_019 (Felix Muller).manager_id  (from 2026-01-05)
- work_item:ticket_011 due_on = 2027-02-18  <- jira work_item:ticket_011.due_on  (from 2027-02-12)
- work_item:ticket_011 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_011.component_id  (from 2027-02-12)
- work_item:ticket_011 owns_work_item = employee:emp_019 (Felix Muller)  <- jira work_item:ticket_011.owner_id  (from 2027-02-12)
- work_item:ticket_011 work_item_status = in_progress  <- jira work_item:ticket_011.status  (from 2027-02-12)
- work_item:ticket_012 due_on = 2027-02-19  <- jira work_item:ticket_012.due_on  (from 2027-02-12)
- work_item:ticket_012 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_012.component_id  (from 2027-02-12)
- work_item:ticket_012 owns_work_item = employee:emp_015 (Arjun Schmidt)  <- jira work_item:ticket_012.owner_id  (from 2027-02-12)
- work_item:ticket_012 work_item_status = in_progress  <- jira work_item:ticket_012.status  (from 2027-02-12)
- work_item:ticket_013 due_on = 2027-02-20  <- jira work_item:ticket_013.due_on  (from 2027-02-15)
- work_item:ticket_013 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_013.component_id  (from 2027-02-15)
- work_item:ticket_013 owns_work_item = employee:emp_019 (Felix Muller)  <- jira work_item:ticket_013.owner_id  (from 2027-02-15)
- work_item:ticket_013 work_item_status = done  <- jira work_item:ticket_013.status  (from 2027-02-15)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_035  (from 2027-02-28)

### scenario_028 — tier adversarial, stale_source_conflict, modifiers concurrent_leave

- asked: leave leave_034, now 2027-03-03T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2027-02-28 … 2027-03-13

#### Key

- stable interval 2027-02-28 … 2027-03-05
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_033 (leave leave_034) -> outcome **assign**
    - must assess emp_027 (Bob Rossi): **non_viable** (component)
    - must assess emp_019 (Felix Muller): **non_viable** (availability)
- expected conflict on work_item:ticket_033 owns_work_item: resolves to employee:emp_011 (Felix Fernandes) by system_of_record_wins

#### Outcome witness (dated view at 2027-03-03, the generator's own assessment over every employee)

- impact deadline on ticket_033: required 1; viable 1, unknown 0, non-viable 27 -> **assign**, agrees with the key
    - need: work_item:ticket_033 in_component = component:comp_001 (Mobile Release) <- jira
    - viable: emp_015 (Arjun Schmidt)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes) [the leaver]: non-viable, availability (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release) <- jira; employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'} <- frappe)
    - emp_012 (Nadia Sharma): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, availability (employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release) <- jira; employee:emp_019 (Felix Muller) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'} <- frappe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2027-03-03, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_033
    - need window: 2027-03-06 … 2027-03-07 (the investigated leave's span)
    - artifact's component: work_item:ticket_033 in_component = component:comp_001 (Mobile Release) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes) [the leaver]: components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [2027-03-06 … 2027-03-07]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [2027-03-06 … 2027-03-07]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_034: emp_011 (Felix Fernandes) 2027-03-06 … 2027-03-07, annual, approved (observable from 2027-02-28)
- leave leave_035: emp_019 (Felix Muller) 2027-03-06 … 2027-03-07, sick, approved (observable from 2027-02-28)
- work item ticket_033 "Mobile Release: close the audit findings for the new tenant": owner emp_011 (Felix Fernandes), in_progress, component comp_001 (Mobile Release), opened 2027-02-28, due 2027-03-06, resolved — (observable from 2027-02-28)
- document doc_025 "Release runbook: Mobile Release: close the audit findings for the new tenant": runbook, effective from 2027-02-28 (observable from 2027-02-28)
    - section clause_025: Bob Rossi owns the ticket Mobile Release: close the audit findings for the new tenant.

#### Authored facts

- work_item:ticket_033 owns_work_item = employee:emp_027 (Bob Rossi)  <- corpus clause:clause_025  (from 2027-02-28)

#### Fact base, cited entries (in the dated view)

- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) employed_as = employee  <- frappe employee:emp_019 (Felix Muller).employment_type  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = airflow  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) has_skill = elasticsearch  <- frappe employee:emp_019 (Felix Muller).skills  (from 2026-01-05)
- employee:emp_019 (Felix Muller) located_in = Lisbon  <- frappe employee:emp_019 (Felix Muller).location  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_019 (Felix Muller) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_019 (Felix Muller).team_id  (from 2026-01-05)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-02-26', 'end': '2026-03-02'}  <- frappe leave:leave_024  (from 2026-02-21)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2026-12-01', 'end': '2026-12-05'}  <- frappe leave:leave_004  (from 2026-11-25)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-01-18', 'end': '2027-01-21'}  <- frappe leave:leave_006  (from 2027-01-11)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-02-18', 'end': '2027-02-20'}  <- frappe leave:leave_005  (from 2027-02-12)
- employee:emp_019 (Felix Muller) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_035  (from 2027-02-28)
- employee:emp_019 (Felix Muller) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_019 (Felix Muller).manager_id  (from 2026-01-05)
- employee:emp_027 (Bob Rossi) employed_as = employee  <- frappe employee:emp_027 (Bob Rossi).employment_type  (from 2026-01-05)
- employee:emp_027 (Bob Rossi) has_skill = elasticsearch  <- frappe employee:emp_027 (Bob Rossi).skills  (from 2026-01-05)
- employee:emp_027 (Bob Rossi) has_skill = java  <- frappe employee:emp_027 (Bob Rossi).skills  (from 2026-01-05)
- employee:emp_027 (Bob Rossi) located_in = Toronto  <- frappe employee:emp_027 (Bob Rossi).location  (from 2026-01-05)
- employee:emp_027 (Bob Rossi) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_027 (Bob Rossi).team_id  (from 2026-01-05)
- employee:emp_027 (Bob Rossi) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_027 (Bob Rossi).manager_id  (from 2026-01-05)
- work_item:ticket_033 due_on = 2027-03-06  <- jira work_item:ticket_033.due_on  (from 2027-02-28)
- work_item:ticket_033 in_component = component:comp_001 (Mobile Release)  <- jira work_item:ticket_033.component_id  (from 2027-02-28)
- work_item:ticket_033 owns_work_item = employee:emp_011 (Felix Fernandes)  <- jira work_item:ticket_033.owner_id  (from 2027-02-28)
- work_item:ticket_033 owns_work_item = employee:emp_027 (Bob Rossi)  <- corpus clause:clause_025  (from 2027-02-28)
- work_item:ticket_033 work_item_status = in_progress  <- jira work_item:ticket_033.status  (from 2027-02-28)

#### Fact base, cited entries observable only after now (other scenarios' plantings; not in this dated view; excluded from a released golden scenario, kept in a throwaway example)

- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)

#### Prose targets

##### clause_025 — runbook in doc_025, position 0
- accepted on attempt 1; request `e14e6807`, body `f3452448`
- required (answer_changing): work_item:ticket_033 owns_work_item = employee:emp_027 (Bob Rossi)  <- corpus clause:clause_025  (from 2027-02-28)
- propositions read: ticket_033 owns_work_item employee:emp_027 (Bob Rossi) [affirmed/asserted]

> Bob Rossi owns the ticket Mobile Release: close the audit findings for the new tenant.

### scenario_029 — tier adversarial, uncovered, modifiers already_resolved

- asked: leave leave_009, now 2027-03-15T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2027-03-14 … 2027-03-27

#### Key

- stable interval 2027-03-14 … 2027-03-18
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_017 (leave leave_009) -> outcome **uncovered**
    - must assess emp_004 (Jonas Nakamura): **non_viable** (skill)
    - must assess emp_001 (Hanna Patel): **non_viable** (component, skill)
    - must assess emp_015 (Arjun Schmidt): **non_viable** (component)
- constraint clause_010 applies to work_item:ticket_017
- distractor work_item:ticket_018: already_resolved

#### Outcome witness (dated view at 2027-03-15, the generator's own assessment over every employee)

- impact deadline on ticket_017: required 1; viable 0, unknown 0, non-viable 28 -> **uncovered**, agrees with the key
    - need: clause:clause_010 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - need: work_item:ticket_017 in_component = component:comp_004 (Billing) <- jira
    - viable: none
    - emp_001 (Hanna Patel): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_004 (Jonas Nakamura): non-viable, skill (employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_005 (Omar Jansen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_007 (Jonas Novak) [the leaver]: non-viable, availability, skill (employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing) <- jira; employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'} <- frappe)
    - emp_008 (Liam Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes): non-viable, skill (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_012 (Nadia Sharma): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_013 (Mert Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, skill (employee:emp_016 (Zeynep Schmidt) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_017 (Omar Demir): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, skill (employee:emp_021 (Kerem Visser) member_of_component = component:comp_004 (Billing) <- jira)
    - emp_022 (Arjun Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_025 (Yusuf Byrne): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component, skill (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2027-03-15, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_017
    - need window: 2027-03-19 … 2027-03-23 (the investigated leave's span)
    - artifact's component: work_item:ticket_017 in_component = component:comp_004 (Billing) <- jira
    - constraint clause_010 names work_item:ticket_017; clause:clause_010 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]} <- corpus
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak) [the leaver]: components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [2027-03-19 … 2027-03-23]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes): components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_009: emp_007 (Jonas Novak) 2027-03-19 … 2027-03-23, annual, approved (observable from 2027-03-14)
- work item ticket_017 "Billing: cut over to the new gateway for the new tenant": owner emp_007 (Jonas Novak), in_progress, component comp_004 (Billing), opened 2027-03-14, due 2027-03-22, resolved — (observable from 2027-03-14)
- work item ticket_018 "Billing: cut over to the new gateway for the new tenant, phase one": owner emp_007 (Jonas Novak), done, component comp_004 (Billing), opened 2027-03-14, due 2027-03-20, resolved 2027-03-14 (observable from 2027-03-14)
- document doc_010 "Release policy: Billing: cut over to the new gateway for the new tenant": policy, effective from 2027-03-14 (observable from 2027-03-14)
    - section clause_010: The Billing: cut over to the new gateway for the new tenant release needs an engineer with Google Cloud experience.

#### Authored facts

- clause:clause_010 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_010  (from 2027-03-14)

#### Fact base, cited entries (in the dated view)

- clause:clause_010 requires = {'count': 1, 'criteria': [{'kind': 'skill', 'skill': 'gcp'}]}  <- corpus clause:clause_010  (from 2027-03-14)
- employee:emp_001 (Hanna Patel) employed_as = employee  <- frappe employee:emp_001 (Hanna Patel).employment_type  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = elasticsearch  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = graphql  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = java  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = react  <- frappe employee:emp_001 (Hanna Patel).skills  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) has_skill = typescript  <- corpus clause:clause_017  (from 2026-07-12)
- employee:emp_001 (Hanna Patel) located_in = Toronto  <- frappe employee:emp_001 (Hanna Patel).location  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_001 (Hanna Patel).team_id  (from 2026-01-05)
- employee:emp_001 (Hanna Patel) on_leave = {'start': '2026-07-04', 'end': '2026-07-08'}  <- frappe leave:leave_011  (from 2026-06-26)
- employee:emp_001 (Hanna Patel) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_001 (Hanna Patel).manager_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) employed_as = employee  <- frappe employee:emp_007 (Jonas Novak).employment_type  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = android  <- jira comment:comment_003  (from 2026-10-12)
- employee:emp_007 (Jonas Novak) has_skill = grafana  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = graphql  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = java  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) has_skill = react  <- frappe employee:emp_007 (Jonas Novak).skills  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) located_in = Toronto  <- frappe employee:emp_007 (Jonas Novak).location  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_007 (Jonas Novak).team_id  (from 2026-01-05)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-03-29', 'end': '2026-04-02'}  <- frappe leave:leave_018  (from 2026-03-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_026  (from 2026-04-23)
- employee:emp_007 (Jonas Novak) on_leave = {'start': '2027-03-19', 'end': '2027-03-23'}  <- frappe leave:leave_009  (from 2027-03-14)
- employee:emp_007 (Jonas Novak) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_007 (Jonas Novak).manager_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) employed_as = employee  <- frappe employee:emp_015 (Arjun Schmidt).employment_type  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) has_skill = GAP  <- frappe employee:emp_015 (Arjun Schmidt).skills  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) located_in = Amsterdam  <- frappe employee:emp_015 (Arjun Schmidt).location  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) member_of_team = team:team_004 (Identity)  <- frappe employee:emp_015 (Arjun Schmidt).team_id  (from 2026-01-05)
- employee:emp_015 (Arjun Schmidt) on_leave = {'start': '2026-04-15', 'end': '2026-04-19'}  <- frappe leave:leave_019  (from 2026-04-09)
- employee:emp_015 (Arjun Schmidt) reports_to = employee:emp_026 (Ines Yilmaz)  <- frappe employee:emp_015 (Arjun Schmidt).manager_id  (from 2026-01-05)
- work_item:ticket_017 due_on = 2027-03-22  <- jira work_item:ticket_017.due_on  (from 2027-03-14)
- work_item:ticket_017 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_017.component_id  (from 2027-03-14)
- work_item:ticket_017 owns_work_item = employee:emp_007 (Jonas Novak)  <- jira work_item:ticket_017.owner_id  (from 2027-03-14)
- work_item:ticket_017 work_item_status = in_progress  <- jira work_item:ticket_017.status  (from 2027-03-14)
- work_item:ticket_018 due_on = 2027-03-20  <- jira work_item:ticket_018.due_on  (from 2027-03-14)
- work_item:ticket_018 in_component = component:comp_004 (Billing)  <- jira work_item:ticket_018.component_id  (from 2027-03-14)
- work_item:ticket_018 owns_work_item = employee:emp_007 (Jonas Novak)  <- jira work_item:ticket_018.owner_id  (from 2027-03-14)
- work_item:ticket_018 work_item_status = done  <- jira work_item:ticket_018.status  (from 2027-03-14)

### scenario_030 — tier adversarial, stale_source_conflict, modifiers none

- asked: leave leave_036, now 2027-04-01T09:00:00+03:00 [Europe/Istanbul], reference timezone Europe/Istanbul, window 2027-03-30 … 2027-04-12

#### Key

- stable interval 2027-03-30 … 2027-04-03
- required sources: corpus, frappe, jira
- impact deadline on work_item:ticket_034 (leave leave_036) -> outcome **assign**
    - must assess emp_004 (Jonas Nakamura): **viable** (no reason)
    - must assess emp_008 (Liam Haddad): **non_viable** (component)
- expected conflict on work_item:ticket_034 owns_work_item: resolves to employee:emp_011 (Felix Fernandes) by system_of_record_wins

#### Outcome witness (dated view at 2027-04-01, the generator's own assessment over every employee)

- impact deadline on ticket_034: required 1; viable 4, unknown 0, non-viable 24 -> **assign**, agrees with the key
    - need: work_item:ticket_034 in_component = component:comp_002 (Payments API) <- jira
    - viable: emp_004 (Jonas Nakamura), emp_007 (Jonas Novak), emp_012 (Nadia Sharma), emp_025 (Yusuf Byrne)
    - emp_001 (Hanna Patel): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_002 (Yusuf Costa): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_003 (Nadia Fernandes): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_005 (Omar Jansen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_006 (Jonas Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_008 (Liam Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_009 (Priya Moreau): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_010 (Bob Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_011 (Felix Fernandes) [the leaver]: non-viable, availability (employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API) <- jira; employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'} <- frappe)
    - emp_013 (Mert Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_014 (Kerem Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_015 (Arjun Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_016 (Zeynep Schmidt): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_017 (Omar Demir): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_018 (Yusuf Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_019 (Felix Muller): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_020 (Yusuf Chen): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_021 (Kerem Visser): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_022 (Arjun Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_023 (Priya Haddad): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_024 (Yusuf Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_026 (Ines Yilmaz): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_027 (Bob Rossi): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - emp_028 (Chloe Okafor): non-viable, component (no excluding fact from the rule: known false on the record, see the criterion universe)
    - must-assess verdicts: every authored verdict derived

#### Criterion universe (dated view at 2027-04-01, every employee's facts the criteria read, no rule applied)

- impact deadline on ticket_034
    - need window: 2027-04-04 … 2027-04-07 (the investigated leave's span)
    - artifact's component: work_item:ticket_034 in_component = component:comp_002 (Payments API) <- jira
    - emp_001 (Hanna Patel): components []; skills [elasticsearch (frappe), graphql (frappe), java (frappe), react (frappe), typescript (corpus clause_017, from 2026-07-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_002 (Yusuf Costa): components []; skills [elasticsearch (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_003 (Nadia Fernandes): components []; skills [kafka (frappe), terraform (frappe), elasticsearch (corpus clause_019, from 2026-07-27)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_004 (Jonas Nakamura): components [comp_002 (Payments API), comp_003 (Notifications), comp_004 (Billing)]; skills [android (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_005 (Omar Jansen): components [comp_005 (Event Ingestion)]; skills [dbt (frappe), go (frappe), java (frappe), kafka (frappe), python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_006 (Jonas Moreau): components [comp_003 (Notifications)]; skills [aws (frappe), java (frappe), python (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_007 (Jonas Novak): components [comp_002 (Payments API), comp_004 (Billing)]; skills [grafana (frappe), graphql (frappe), java (frappe), react (frappe), android (jira comment_003, from 2026-10-12)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_008 (Liam Haddad): components []; skills [android (frappe), go (frappe), kafka (frappe), postgresql (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_009 (Priya Moreau): components [comp_005 (Event Ingestion)]; skills [android (frappe), python (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_010 (Bob Yilmaz): components []; skills [airflow (frappe), android (frappe), java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_011 (Felix Fernandes) [the leaver]: components [comp_001 (Mobile Release), comp_002 (Payments API), comp_004 (Billing)]; skills [android (frappe), grafana (frappe), java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [2027-04-04 … 2027-04-07]; events on the window's days [none]; employed_as employee
    - emp_012 (Nadia Sharma): components [comp_002 (Payments API)]; skills [android (frappe), kubernetes (frappe), react (frappe), postgresql (jira comment_002, from 2026-09-26)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_013 (Mert Yilmaz): components [comp_005 (Event Ingestion)]; skills [react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_014 (Kerem Haddad): components [comp_003 (Notifications)]; skills [react (frappe), terraform (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_015 (Arjun Schmidt): components [comp_001 (Mobile Release), comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_016 (Zeynep Schmidt): components [comp_004 (Billing)]; skills [spark (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_017 (Omar Demir): components []; skills [android (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_018 (Yusuf Muller): components []; skills [android (frappe), graphql (frappe), ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_019 (Felix Muller): components [comp_001 (Mobile Release)]; skills [airflow (frappe), elasticsearch (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_020 (Yusuf Chen): components []; skills [ios (frappe), java (frappe), kafka (frappe), react (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_021 (Kerem Visser): components [comp_003 (Notifications), comp_004 (Billing)]; skills [java (frappe), kafka (frappe), postgresql (frappe), react (jira comment_001, from 2026-08-11)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_022 (Arjun Haddad): components [comp_005 (Event Ingestion)]; skills [java (frappe), kafka (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_023 (Priya Haddad): components []; skills [python (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_024 (Yusuf Okafor): components []; skills [android (frappe), elasticsearch (frappe), redis (frappe), typescript (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_025 (Yusuf Byrne): components [comp_002 (Payments API)]; skills [java (frappe), kafka (frappe), kubernetes (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as contractor
    - emp_026 (Ines Yilmaz): components [comp_005 (Event Ingestion)]; skills [ios (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_027 (Bob Rossi): components []; skills [elasticsearch (frappe), java (frappe)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - emp_028 (Chloe Okafor): components [comp_003 (Notifications)]; skills [skills record absent (GAP)]; leaves over the window [none]; events on the window's days [none]; employed_as employee
    - 28 employees listed

#### Plantings

- leave leave_036: emp_011 (Felix Fernandes) 2027-04-04 … 2027-04-07, annual, approved (observable from 2027-03-30)
- work item ticket_034 "Payments API: migrate the retry queue for the mobile clients": owner emp_011 (Felix Fernandes), in_progress, component comp_002 (Payments API), opened 2027-03-30, due 2027-04-05, resolved — (observable from 2027-03-30)
- document doc_026 "Release runbook: Payments API: migrate the retry queue for the mobile clients": runbook, effective from 2027-03-30 (observable from 2027-03-30)
    - section clause_026: Liam Haddad owns the ticket Payments API: migrate the retry queue for the mobile clients.

#### Authored facts

- work_item:ticket_034 owns_work_item = employee:emp_008 (Liam Haddad)  <- corpus clause:clause_026  (from 2027-03-30)

#### Fact base, cited entries (in the dated view)

- employee:emp_004 (Jonas Nakamura) employed_as = employee  <- frappe employee:emp_004 (Jonas Nakamura).employment_type  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = android  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) has_skill = java  <- frappe employee:emp_004 (Jonas Nakamura).skills  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) located_in = Lisbon  <- frappe employee:emp_004 (Jonas Nakamura).location  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_003 (Notifications)  <- jira component:comp_003 (Notifications).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) member_of_team = team:team_005 (Mobile)  <- frappe employee:emp_004 (Jonas Nakamura).team_id  (from 2026-01-05)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-01-28', 'end': '2026-02-01'}  <- frappe leave:leave_016  (from 2026-01-21)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-02-15', 'end': '2026-02-17'}  <- frappe leave:leave_017  (from 2026-02-07)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-02', 'end': '2026-09-05'}  <- frappe leave:leave_001  (from 2026-08-27)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-09-16', 'end': '2026-09-17'}  <- frappe leave:leave_002  (from 2026-09-11)
- employee:emp_004 (Jonas Nakamura) on_leave = {'start': '2026-12-31', 'end': '2027-01-02'}  <- frappe leave:leave_008  (from 2026-12-26)
- employee:emp_004 (Jonas Nakamura) reports_to = employee:emp_002 (Yusuf Costa)  <- frappe employee:emp_004 (Jonas Nakamura).manager_id  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) employed_as = employee  <- frappe employee:emp_008 (Liam Haddad).employment_type  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) has_skill = android  <- frappe employee:emp_008 (Liam Haddad).skills  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) has_skill = go  <- frappe employee:emp_008 (Liam Haddad).skills  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) has_skill = kafka  <- frappe employee:emp_008 (Liam Haddad).skills  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) has_skill = postgresql  <- frappe employee:emp_008 (Liam Haddad).skills  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) located_in = Toronto  <- frappe employee:emp_008 (Liam Haddad).location  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_008 (Liam Haddad).team_id  (from 2026-01-05)
- employee:emp_008 (Liam Haddad) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_008 (Liam Haddad).manager_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) employed_as = employee  <- frappe employee:emp_011 (Felix Fernandes).employment_type  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = android  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = grafana  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = java  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kafka  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) has_skill = kubernetes  <- frappe employee:emp_011 (Felix Fernandes).skills  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) located_in = Istanbul  <- frappe employee:emp_011 (Felix Fernandes).location  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_001 (Mobile Release)  <- jira component:comp_001 (Mobile Release).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_002 (Payments API)  <- jira component:comp_002 (Payments API).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_component = component:comp_004 (Billing)  <- jira component:comp_004 (Billing).member_ids  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) member_of_team = team:team_002 (Growth)  <- frappe employee:emp_011 (Felix Fernandes).team_id  (from 2026-01-05)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-05-01', 'end': '2026-05-04'}  <- frappe leave:leave_027  (from 2026-04-23)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-11-16', 'end': '2026-11-19'}  <- frappe leave:leave_003  (from 2026-11-11)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2026-12-17', 'end': '2026-12-19'}  <- frappe leave:leave_007  (from 2026-12-12)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-03-06', 'end': '2027-03-07'}  <- frappe leave:leave_034  (from 2027-02-28)
- employee:emp_011 (Felix Fernandes) on_leave = {'start': '2027-04-04', 'end': '2027-04-07'}  <- frappe leave:leave_036  (from 2027-03-30)
- employee:emp_011 (Felix Fernandes) reports_to = employee:emp_006 (Jonas Moreau)  <- frappe employee:emp_011 (Felix Fernandes).manager_id  (from 2026-01-05)
- work_item:ticket_034 due_on = 2027-04-05  <- jira work_item:ticket_034.due_on  (from 2027-03-30)
- work_item:ticket_034 in_component = component:comp_002 (Payments API)  <- jira work_item:ticket_034.component_id  (from 2027-03-30)
- work_item:ticket_034 owns_work_item = employee:emp_008 (Liam Haddad)  <- corpus clause:clause_026  (from 2027-03-30)
- work_item:ticket_034 owns_work_item = employee:emp_011 (Felix Fernandes)  <- jira work_item:ticket_034.owner_id  (from 2027-03-30)
- work_item:ticket_034 work_item_status = in_progress  <- jira work_item:ticket_034.status  (from 2027-03-30)

#### Prose targets

##### clause_026 — runbook in doc_026, position 0
- accepted on attempt 1; request `60bf4846`, body `b9cfcfee`
- required (answer_changing): work_item:ticket_034 owns_work_item = employee:emp_008 (Liam Haddad)  <- corpus clause:clause_026  (from 2027-03-30)
- propositions read: ticket_034 owns_work_item employee:emp_008 (Liam Haddad) [affirmed/asserted]

> Liam Haddad owns the ticket Payments API: migrate the retry queue for the mobile clients.
