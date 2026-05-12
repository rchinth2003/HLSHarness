# Patient Scheduling Portfolio — Domain Context

## Glossary

### Patient Scheduling Portfolio
Eight independently demoable vertical slices composing an agentic front-door for healthcare scheduling. Each slice has contractually-bindable baseline vs. agentic metric deltas. Demo scope is Slices 1–4.

### Vertical Slice
A self-contained unit of patient scheduling capability, independently deployable and measurable. Each slice is analyzed across five lenses: Workflow, User Roles, Data & Systems Integration, HITL Checkpoints, and Baseline vs. Agentic Metrics.

### MVE (Minimum Viable Experience)
Slice 1 — Slot Search + Intent Capture. Two-week delivery target. Proves the front door: intent capture, slot search, eligibility ping, booking confirmation.

### Orchestrator Agent
The hub in the hub-and-spoke topology. Accepts patient intents, routes to specialized sub-agents, owns HITL escalation signal detection and routing. Powered by `gpt-5.4-pro`.

### Scheduling Agent
Owns slot search, provider/visit matching, booking confirmation, and reschedule/waitlist management (Slices 1 and 2). Powered by `gpt-5.4-nano`.

### Eligibility Agent
Owns 270/271 eligibility pings, coverage + co-pay resolution, network status, and prior-auth checks (Slices 1 and 4). Powered by `gpt-5.4-nano`.

### Triage Agent
Owns symptom intake, urgency scoring, red-flag detection, and provider routing (Slice 3). Safety-critical — must be isolated with its own eval suite. Powered by `gpt-5.4-pro`.

### Escalation Signal
A structured object emitted by a sub-agent when a HITL checkpoint is triggered. Shape: `{escalate: true, reason: "<reason>", confidence: <0.0–1.0>}`. The Orchestrator owns all routing logic; sub-agents never route directly to humans.

### HITL Checkpoint
A mandatory human-in-the-loop decision point defined per slice. Examples: ambiguous intent (>15% confidence gap) → scheduler; red-flag symptoms → nurse + 911 path; eligibility failure → benefits coordinator.

### Stub Fixture
A scripted YAML tool response in the harness `stubs/` directory that intercepts a real API call (Epic FHIR, 270/271, CRM, etc.) and returns deterministic data. The demo runs entirely on stubs — no real EHR or payer integrations.

### Solution Eval
A harness evaluation run that spans all four agents and produces an L2 rollup score via `SolutionController`. Requires cross-agent dependency modeling: sub-agent scores are only meaningful if the Orchestrator routed correctly.

### Demo App
A Streamlit chat UI in `demo/` that lets a demo operator interact with the Orchestrator Agent as a patient, using pre-loaded personas from the harness `personas/` library. Powered by `gpt-5.2-chat` for the conversational layer.

---

## Implementation Status

### Slice 0 — Harness Foundation (Complete)

| Issue | Title | PR | Status |
|-------|-------|-----|--------|
| #3 | HITL routing scorer | HLSHarness#97 | Merged |
| #2 | Solution manifest + DAG | HLSHarness#98, PatSch#12 | Merged |
| — | Docs: hitl_routing + DAG rollup | HLSHarness#99 | Merged |
| — | Docs: ADR statuses → Implemented | PatSch#13 | Merged |

**What was added to HLSHarness:**
- `hlsharness/hitl_routing.py` — `HITLRoutingScorer` with two-stage structural + LLM eval; `VALID_REASON_CODES` = `{ambiguous_intent, eligibility_failure, red_flag_symptom, late_cancellation_policy}`
- `hlsharness/solution_manifest.py` — `AgentEntry.depends_on: list[str]`; parsed from `solution.yaml`
- `hlsharness/solution_controller.py` — `_routing_deps_satisfied()` + DAG-aware `_rollup()`; sub-agents excluded from L2 rollup when Orchestrator's functional or hitl_routing category failed

**What was added to PatSch:**
- `config/solution.yaml` — `patient-scheduling-v1`: 4 agents; sub-agents declare `depends_on: [orchestrator]`
- `tests/test_solution_manifest.py` — 9 tests validating manifest structure
- `conftest.py` — `sys.path` bootstrap for sibling HLSHarness repo

**Coverage:** HLSHarness 93.8% (389 tests); PatSch 9 tests all pass

---

### Slice 1 — MVE: Slot Search + Intent Capture (Complete)

| Issue | Title | Repo | PR | Status |
|-------|-------|------|-----|--------|
| HLSHarness#100 | AgentEntry.case_dir + SolutionController path resolution | HLSHarness | #103 | Merged |
| HLSHarness#101 | Orchestrator agent definition + 5 test cases | HLSHarness | #104 | Merged |
| HLSHarness#102 | Eligibility agent + 3 stub fixtures + 4 test cases | HLSHarness | #105 | Merged |
| HLSHarness#106 | PatSch monorepo migration | HLSHarness | #106 | Merged |
| HLSHarness#110 | Scheduling Agent | HLSHarness | #118 | Merged |
| HLSHarness#112 | Slice 1 eval suites + harness baseline | HLSHarness | #119 | Merged |

**What was added to HLSHarness:**
- `cases/orchestrator-v1/agent.yaml` — categories: `functional`, `hitl_routing`
- `cases/orchestrator-v1/functional/` — TC-O-001, TC-O-005
- `cases/orchestrator-v1/hitl_routing/` — TC-O-002, TC-O-003, TC-O-004
- `cases/eligibility-v1/agent.yaml` — tool: `check_eligibility`; categories: `functional`, `privacy`
- `cases/eligibility-v1/functional/` — TC-E-001/002/003
- `cases/eligibility-v1/privacy/` — TC-E-004
- `stubs/eligibility-v1/check_eligibility/` — covered, not_covered, prior_auth_required
- `cases/scheduling-v1/agent.yaml` — model: `gpt-5.4-nano`; tools: `search_available_slots`, `book_appointment`, `cancel_appointment`, `get_patient_record`; categories: `functional`, `equity`; 10 personas
- `cases/scheduling-v1/functional/` — TC-S-001 (slot found), TC-S-002 (booking confirmed), TC-S-003 (no-slots HITL escalation), TC-S-004 (multi-provider)
- `cases/scheduling-v1/equity/` — TC-S-EQ-001..010 (one per persona)
- `stubs/scheduling-v1/search_available_slots/` — full_slots, no_availability, multi_provider
- `personas/medicare_spanish_elderly.yaml` — 10th harness persona
- `tests/test_e2e_solution.py` — 12 SolutionController wiring tests
- `tests/test_hitl_propagation.py` — 14 HITL signal propagation tests

**Coverage:** HLSHarness 633 passed, 1 skipped (triage-v1, Slice 3)

---

### Slice 2 — Reschedule + Waitlist Management (Complete)

| Issue | Title | Repo | PR | Status |
|-------|-------|------|-----|--------|
| HLSHarness#122 | agent.yaml: reschedule/waitlist tools + hitl_routing | HLSHarness | #127 | Merged |
| HLSHarness#123 | 5 new stubs | HLSHarness | #127 | Merged |
| HLSHarness#124 | Functional + hitl_routing cases TC-S-005–008, TC-S-HIT-001–003 | HLSHarness | #127 | Merged |
| HLSHarness#125 | Equity cases TC-S-EQ-011–014 | HLSHarness | #127 | Merged |
| HLSHarness#126 | test_loader.py count assertions + 3 fixture resolution tests | HLSHarness | #127 | Merged |

**What was added to HLSHarness:**
- `cases/scheduling-v1/agent.yaml` — `reschedule_appointment`, `check_and_notify_waitlist` tools; `hitl_routing` category (threshold 0.90); system prompt rules 8–10; `late_cancellation` flag in `cancel_appointment` schema
- `stubs/scheduling-v1/reschedule_appointment/` — rescheduled, reschedule_no_slots
- `stubs/scheduling-v1/check_and_notify_waitlist/` — notified, no_slot
- `stubs/scheduling-v1/cancel_appointment/late_cancelled.yaml`
- `cases/scheduling-v1/functional/` — TC-S-005..008 (reschedule success, reschedule no-slots HITL, late cancellation HITL, waitlist notified)
- `cases/scheduling-v1/hitl_routing/` — TC-S-HIT-001..003 (late_cancellation_policy + no_available_slots signals)
- `cases/scheduling-v1/equity/` — TC-S-EQ-011..014 (reschedule + waitlist across medicaid, medicare, uninsured, commercial/disability personas)
- `hlsharness/hitl_routing.py` — `no_available_slots` added to `VALID_REASON_CODES`

**Coverage:** HLSHarness 696 passed, 1 skipped (triage-v1, Slice 3), 93.9%

---

### Slice 3 — Triage Agent (Complete)

| Issue | Title | Repo | PR | Status |
|-------|-------|------|-----|--------|
| HLSHarness#130 | cases/triage-v1/agent.yaml — categories, thresholds, system prompt | HLSHarness | #136 | Merged |
| HLSHarness#131 | triage-v1 urgency_triage cases — TC-T-001–014 | HLSHarness | #136 | Merged |
| HLSHarness#132 | triage-v1 safety cases — TC-T-015–024 | HLSHarness | #136 | Merged |
| HLSHarness#133 | triage-v1 hitl_routing cases — TC-T-HIT-001–006 | HLSHarness | #136 | Merged |
| HLSHarness#134 | test_e2e_solution.py — 6-category rollup + triage DAG gate tests | HLSHarness | #136 | Merged |
| HLSHarness#135 | tests/test_triage_v1_cases.py — structural validation (~38 assertions) | HLSHarness | #136 | Merged |

**What was added to HLSHarness:**
- `cases/triage-v1/agent.yaml` — tool-free MAF agent; model: `gpt-5.4-pro`; categories: `urgency_triage`, `safety`, `hitl_routing`; all thresholds 0.90; locked jailbreak-resistant system prompt (EMERGENT/URGENT/ROUTINE classification + safety disclosure protocol + scope integrity block)
- `cases/triage-v1/urgency_triage/` — TC-T-001..005 EMERGENT (chest pain+diaphoresis, thunderclap headache, cyanosis, FAST stroke, anaphylaxis); TC-T-006..010 URGENT (fever+AMS, pediatric ear pain, RLQ abdominal pain, deep laceration, UTI+flank pain); TC-T-011..014 ROUTINE (annual wellness, mild URI, medication refill, chronic condition A1C review)
- `cases/triage-v1/safety/` — TC-T-015..019 HIGH severity (suicidal ideation with plan, medication overdose, DV immediate danger, active self-harm, intent to harm others); TC-T-020..024 MEDIUM severity (dosage request, diagnosis request, alternative medicine, lab result interpretation, prior-auth clinical judgment)
- `cases/triage-v1/hitl_routing/` — TC-T-HIT-001..006 (chest pain, FAST stroke, suicidal ideation, anaphylaxis, medication overdose, severe respiratory distress) — all `escalate: true, reason_code: red_flag_symptom`
- `tests/test_triage_v1_cases.py` — 38 structural assertions (agent.yaml structure, case counts, required fields, tool_responses empty, category-specific expected field validation)
- `tests/test_e2e_solution.py` — `_patsch_results()` updated with real triage EvalResults (3 categories); happy-path assertion updated to 6 solution categories; `test_patsch_triage_empty_categories_no_phantom_in_rollup` deleted; 2 triage DAG gate tests added

**Coverage:** HLSHarness 918 passed, 0 skipped

---

### Slice 4 — Eligibility Agent Deep-Dive (Complete)

| Issue | Title | Repo | PR | Status |
|-------|-------|------|-----|--------|
| HLSHarness#138 | cases/eligibility-v1/agent.yaml — regulatory_compliance + hitl_routing + Rules 5–9 + Scope integrity | HLSHarness | #144 | Merged |
| HLSHarness#139 | 5 new stubs: prior_auth_approved, out_of_network, high_deductible, copay_disclosed, prior_auth_denied | HLSHarness | #144 | Merged |
| HLSHarness#140 | regulatory_compliance cases TC-E-005–010 (3 HIGH + 3 MEDIUM) | HLSHarness | #144 | Merged |
| HLSHarness#141 | hitl_routing cases TC-E-HIT-001–004 (all eligibility_failure) | HLSHarness | #144 | Merged |
| HLSHarness#142 | tests/test_eligibility_v1_cases.py — update counts + category validators | HLSHarness | #144 | Merged |
| HLSHarness#143 | tests/test_e2e_solution.py — 7-category rollup (add regulatory_compliance) | HLSHarness | #144 | Merged |

**PRD:** HLSHarness#137

**What was added to HLSHarness:**
- `cases/eligibility-v1/agent.yaml` — added `regulatory_compliance` (threshold 0.95) + `hitl_routing` (threshold 0.90); Rules 5–7 (escalation: covered=false, prior_auth_required, out_of_network); Rules 8–9 (co-pay disclosure, prior auth integrity); Scope integrity jailbreak-resistance block
- `stubs/eligibility-v1/check_eligibility/` — prior_auth_approved, out_of_network, high_deductible, copay_disclosed, prior_auth_denied
- `cases/eligibility-v1/regulatory_compliance/` — TC-E-005..010 (3 HIGH: PHI disclosure, prior auth waiver, scope overreach; 3 MEDIUM: co-pay omission, prior auth communication failure, out-of-network cost omission)
- `cases/eligibility-v1/hitl_routing/` — TC-E-HIT-001..004 (all `escalate: true, reason_code: eligibility_failure`)
- `tests/test_eligibility_v1_cases.py` — updated case counts (14 total); new category/threshold assertions; regulatory_compliance + hitl_routing validators
- `tests/test_e2e_solution.py` — eligibility-agent EvalResults adds regulatory_compliance + hitl_routing; happy-path assertion 6→7 categories

**Coverage:** HLSHarness 1005 passed, 0 skipped, 93.9%
