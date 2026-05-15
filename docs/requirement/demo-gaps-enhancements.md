# Patient Scheduling Agent Demo — Gaps & Enhancement Backlog

This document captures real-world gaps and misalignments identified in the demo context (`CONTEXT.md`). Each item is written as an actionable coding task for the demo agent.

---

## 🔴 High Priority — Credibility Blockers

### GAP-001: Patient Identity Verification Before Record Retrieval

**Problem:** The Scheduling Agent calls `get_patient_record` without any identity proofing step. In a real deployment, retrieving PHI requires patient verification first (DOB + MRN or insurance ID). A demo showing immediate record retrieval after a patient says their name will raise red flags with compliance-aware buyers.

**Required Changes:**
- Add a new stub tool: `verify_patient_identity`
  - Inputs: `patient_name`, `date_of_birth`, `mrn_or_insurance_id`
  - Stub responses to add under `stubs/scheduling-v1/verify_patient_identity/`:
    - `verified.yaml` — returns `{ status: "verified", patient_id: "P12345" }`
    - `failed.yaml` — returns `{ status: "failed", reason: "dob_mismatch" }`
    - `locked.yaml` — returns `{ status: "locked", reason: "max_attempts_exceeded" }`
- Update `cases/scheduling-v1/agent.yaml`:
  - Add `verify_patient_identity` to the tools list
  - Add system prompt rule: *"Always call `verify_patient_identity` before calling `get_patient_record`. If verification fails, do not proceed. If locked, escalate via HITL."*
- Add test cases:
  - `TC-S-009`: Verification success → record retrieved → slot search proceeds
  - `TC-S-010`: Verification failure → agent asks patient to re-confirm details
  - `TC-S-HIT-004`: Max attempts exceeded → HITL escalation with reason `identity_verification_failure`
- Add `identity_verification_failure` to `VALID_REASON_CODES` in `hlsharness/hitl_routing.py`
- Update demo scenario stubs to wire `verify_patient_identity` fixtures in `demo/scenarios.yaml`

---

### GAP-002: HIPAA Consent Acknowledgment at Session Start

**Problem:** There is no consent capture step before the agent begins collecting patient information. US healthcare regulations require patients to be informed of and acknowledge the HIPAA Notice of Privacy Practices before an interaction begins.

**Required Changes:**
- Add a consent preamble to the Orchestrator's system prompt that fires on session start:
  - The Orchestrator must present a brief HIPAA acknowledgment before collecting any patient data.
  - Example text (customize per health system): *"Before we begin, please note that [Health System] collects scheduling information subject to our HIPAA Notice of Privacy Practices. Do you agree to continue?"*
- Add a stub tool: `record_consent`
  - Inputs: `patient_acknowledged: bool`, `session_id: str`
  - Stub: `consent_recorded.yaml` — returns `{ recorded: true, timestamp: "2026-05-13T09:00:00Z" }`
- Add HITL gate: if patient declines consent, emit escalation signal `{ escalate: true, reason: "consent_declined", confidence: 1.0 }` and end session.
- Add test case `TC-O-006`: Patient declines consent → Orchestrator emits escalation, no PHI collected.
- Update `demo/app.py`: Show a consent banner at session start before the first agent message is sent.

---

### GAP-003: Fictional Model Names

**Problem:** The context references `gpt-5.4-pro`, `gpt-5.4-nano`, and `gpt-5.2-chat` which are not real OpenAI model names. Technical audiences will flag this as a fabrication.

**Required Changes:**
- Replace all model name references in agent YAML configs with real current model names:
  | Current (Placeholder) | Replace With |
  |---|---|
  | `gpt-5.4-pro` | `gpt-4o` (or `o3` for reasoning-heavy agents) |
  | `gpt-5.4-nano` | `gpt-4o-mini` |
  | `gpt-5.2-chat` | `gpt-4o` |
- Files to update:
  - `cases/orchestrator-v1/agent.yaml`
  - `cases/triage-v1/agent.yaml`
  - `cases/scheduling-v1/agent.yaml`
  - `cases/eligibility-v1/agent.yaml`
  - `demo/orchestrator-v1.yaml`
  - `CONTEXT.md` glossary section
- Add a `# model rationale` comment in each agent YAML explaining the model choice (e.g., safety-critical agents use `gpt-4o`, high-volume transactional agents use `gpt-4o-mini`).

---

## 🟡 Medium Priority — Real-World Realism Gaps

### GAP-004: Triage Agent — Mandatory Clinical Disclaimer in Output

**Problem:** The Triage Agent classifies symptoms as EMERGENT/URGENT/ROUTINE but does not explicitly surface a clinical disclaimer in its responses. Several US state regulations and FTC AI guidance require AI triage tools to disclaim they are not a substitute for clinical judgment.

**Required Changes:**
- Update `cases/triage-v1/agent.yaml` system prompt:
  - Add mandatory output rule: *"Every triage response MUST include the disclaimer: 'This triage is for scheduling prioritization only and is not a medical diagnosis. Please consult a licensed clinician for medical advice.'"*
- Add eval assertion to existing triage test cases (`TC-T-001` through `TC-T-024`):
  - Add `must_contain_disclaimer: true` field to case expected output schema
  - Update `tests/test_triage_v1_cases.py` to assert disclaimer presence in all triage responses
- Update `demo/app.py` to render the disclaimer text in a distinct styled callout (e.g., italic gray text) below triage output in the chat panel.

---

### GAP-005: Provider Matching Logic

**Problem:** The Scheduling Agent returns available slots but the context does not describe provider matching criteria. Buyers will ask how the agent selects or ranks providers.

**Required Changes:**
- Add a new stub tool: `match_providers`
  - Inputs: `specialty`, `language_preference`, `gender_preference`, `insurance_plan`, `location_zip`
  - Stub responses under `stubs/scheduling-v1/match_providers/`:
    - `matched_single.yaml` — 1 provider match with rationale
    - `matched_multi.yaml` — 2-3 providers ranked by relevance score
    - `no_match.yaml` — no in-network providers, triggers HITL
  - Each response should include: `provider_name`, `npi`, `specialty`, `languages`, `accepting_new_patients`, `match_score`
- Update `cases/scheduling-v1/agent.yaml`:
  - Add `match_providers` to tools list
  - Add system prompt rule: *"Call `match_providers` before `search_available_slots` to ensure slots returned are for a clinically and logistically appropriate provider."*
- Add test cases:
  - `TC-S-011`: Multi-provider match → agent presents options → patient selects → slot search scoped to selection
  - `TC-S-012`: No in-network match → HITL escalation with reason `no_available_slots`
- Update demo scenarios in `demo/scenarios.yaml` to wire `match_providers` stubs.

---

### GAP-006: Prior Auth Async Realism — Talking Point + Stub Enhancement

**Problem:** The `prior_auth_approved` and `prior_auth_denied` stubs return synchronous responses, which misrepresents real prior auth workflows (CoverMyMeds, Gold Carding) that are asynchronous and can take days.

**Required Changes:**
- Add a third prior auth stub: `prior_auth_pending.yaml` under `stubs/eligibility-v1/check_eligibility/`
  - Response: `{ status: "prior_auth_pending", expected_response_hours: 48, reference_id: "PA-20260513-001" }`
- Update `cases/eligibility-v1/agent.yaml` system prompt:
  - Add rule: *"If prior_auth status is 'pending', inform the patient that authorization is in progress, provide the reference ID, and offer to notify them when a decision is received."*
- Add test case `TC-E-011`: Prior auth pending → agent communicates timeline → offers notification opt-in.
- Add a `# demo-note` comment in `demo/scenarios.yaml` for prior auth scenarios: *"In production, prior auth integrations are asynchronous (CoverMyMeds, Gold Carding). This stub simulates synchronous response for demo clarity."*
- Update `demo/README.md` operator guide to include this talking point under a "Known Simplifications" section.

---

### GAP-007: No-Show / Cancellation Policy Contextual Variance

**Problem:** The `late_cancelled.yaml` stub applies a single policy uniformly. Real health systems vary cancellation policy by provider type, payer, and patient history (e.g., first-time offenders may be waived).

**Required Changes:**
- Add new stubs under `stubs/scheduling-v1/cancel_appointment/`:
  - `late_cancelled_waived.yaml` — first-time offender, fee waived: `{ status: "cancelled", fee_waived: true, reason: "first_occurrence" }`
  - `late_cancelled_fee_applied.yaml` — repeat offender, fee applied: `{ status: "cancelled", fee_applied: 25.00, policy_ref: "CXL-002" }`
- Update `cases/scheduling-v1/agent.yaml` system prompt:
  - Add rule: *"When processing a late cancellation, check patient history. If first occurrence, apply waiver policy. If repeat, apply fee and inform patient."*
- Add test cases:
  - `TC-S-HIT-005`: First-time late cancel → fee waived → patient informed
  - `TC-S-HIT-006`: Repeat late cancel → fee applied → HITL for patient dispute path
- Update demo scenario in `demo/scenarios.yaml` to show the contextual policy branch.

---

## 🟢 Low Priority — Demo Polish & Buyer Experience

### GAP-008: Post-Booking Reminder / Pre-Visit Touchpoint

**Problem:** The demo covers scheduling and eligibility but nothing happens *after* a booking is confirmed. Buyers (especially those evaluating Luma Health, Klara, or Kyruus alternatives) will ask about the post-booking workflow.

**Required Changes:**
- Add a new stub tool: `send_appointment_reminder`
  - Inputs: `appointment_id`, `channel` (sms/email), `patient_contact`
  - Stub: `reminder_sent.yaml` — returns `{ status: "sent", channel: "sms", eta_minutes: 1 }`
- Wire this tool to fire automatically after `book_appointment` succeeds in the Scheduling Agent.
- Add to `demo/app.py`: After booking confirmation message, show a secondary UI note: *"✉️ Reminder sent to patient via SMS"*
- Add test case `TC-S-013`: Booking confirmed → reminder dispatched → agent confirms to patient.

---

### GAP-009: Add 7th Demo Scenario — Waitlist Status Check (Async Continuity)

**Problem:** The 6 current demo scenarios all represent linear single-session flows. There is no scenario showing a patient *returning* to check on a previous interaction (e.g., waitlist status), which is a common real-world pattern.

**Required Changes:**
- Add to `demo/scenarios.yaml`:
  ```yaml
  - name: "Waitlist Status Check — Returning Patient"
    persona_id: medicaid_urban_adult
    description: >
      Patient booked on waitlist in a prior session and returns to check status.
      Agent retrieves waitlist position and notifies if a slot has opened.
    stub_map:
      scheduling: check_and_notify_waitlist/notified
      eligibility: check_eligibility/covered
  ```
- Update `demo/README.md` with narrative for this scenario.
- Update `tests/test_demo_scenarios.py` count assertion from 6 → 7 scenarios.

---

### GAP-010: Metrics Display in Demo UI

**Problem:** The context mentions "contractually-bindable baseline vs. agentic metric deltas" but these are not surfaced in the demo UI. Buyers respond strongly to before/after metrics.

**Required Changes:**
- Add a metrics sidebar panel to `demo/app.py`:
  - Display static baseline vs. agentic comparison metrics, e.g.:
    | Metric | Baseline | Agentic |
    |---|---|---|
    | Avg. time to schedule | 8 min | 45 sec |
    | Eligibility check time | 3 min | 8 sec |
    | No-show rate | 18% | 11% |
    | HITL escalation rate | 100% | 12% |
  - Source these from a new config file: `demo/metrics.yaml`
- Metrics panel should be collapsible and clearly labeled *"Illustrative benchmarks — actual results vary by deployment."*

---

### GAP-011: Spanish-Language End-to-End Path Validation

**Problem:** The `medicare_spanish_elderly.yaml` persona exists in the harness but it is unclear if the demo UI correctly renders Spanish-language responses end-to-end.

**Required Changes:**
- Add an explicit demo scenario in `demo/scenarios.yaml` that sets the language context to Spanish:
  ```yaml
  - name: "Spanish-Language Scheduling — Medicare Elderly"
    persona_id: medicare_spanish_elderly
    language: es
    stub_map:
      scheduling: search_available_slots/full_slots
      eligibility: check_eligibility/covered
  ```
- Update Orchestrator system prompt in `demo/orchestrator-v1.yaml`:
  - Add rule: *"Detect patient language from first message. Respond in the same language throughout the session."*
- Test the Streamlit UI for Spanish character rendering (UTF-8 support, font rendering).
- Add assertion in `tests/test_demo_scenarios.py`: scenario with `language: es` must have `medicare_spanish_elderly` persona.

---

### GAP-012: Operator "When It Goes Wrong" Guide

**Problem:** The `demo/README.md` has a per-scenario narrative but no guidance for demo operators when the agent produces unexpected output during a live presentation.

**Required Changes:**
- Add a new section to `demo/README.md`: **"Live Demo Recovery Playbook"**
  - Document the top 5 likely failure modes and recovery steps:
    1. **Agent loops / doesn't terminate** → Use sidebar Reset button, reload scenario
    2. **HITL banner fires unexpectedly** → Explain to audience: *"This is the system's safety net — in production this routes to a human agent in under 30 seconds"*
    3. **Stub fixture not found** → Check `stub_map` in `scenarios.yaml` matches fixture filenames exactly
    4. **Triage classifies ROUTINE when EMERGENT expected** → Switch to a pre-validated scenario (TC-T-001 chest pain persona)
    5. **Spanish scenario shows garbled characters** → Fall back to English persona, flag as known UI issue
- Add a `demo/TROUBLESHOOTING.md` with the same content for quick reference.

---

## Implementation Order (Recommended)

| Priority | Gap | Effort | Demo Impact |
|---|---|---|---|
| 🔴 1 | GAP-003: Fix model names | XS | Prevents credibility loss |
| 🔴 2 | GAP-001: Identity verification | M | Required for PHI realism |
| 🔴 3 | GAP-002: Consent acknowledgment | S | HIPAA front-door completeness |
| 🟡 4 | GAP-004: Triage disclaimer | S | Regulatory safety |
| 🟡 5 | GAP-005: Provider matching | M | Differentiating capability |
| 🟡 6 | GAP-006: Prior auth pending stub | S | Async realism + talking point |
| 🟡 7 | GAP-007: Cancellation policy variance | S | Policy contextual intelligence |
| 🟢 8 | GAP-010: Metrics UI panel | S | Buyer persuasion |
| 🟢 9 | GAP-008: Post-booking reminder | S | End-to-end completeness |
| 🟢 10 | GAP-011: Spanish e2e path | S | Equity story |
| 🟢 11 | GAP-009: 7th waitlist scenario | XS | Async continuity |
| 🟢 12 | GAP-012: Operator recovery guide | XS | Demo resilience |

---

*Generated: 2026-05-13 | Source: CONTEXT.md review against real-world US healthcare scheduling requirements*
