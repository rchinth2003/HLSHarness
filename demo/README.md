# Patient Scheduling Demo — Operator Guide

Live multi-agent chat UI powered by real Azure OpenAI inference. The Orchestrator
routes to Scheduling, Eligibility, and Triage sub-agents. Sub-agent tool calls are
intercepted by StubToolMiddleware using the fixture library — no real EHR or payer
integration required.

## Prerequisites

- Python 3.12+, `uv` installed
- Azure OpenAI endpoint with `gpt-5.4-pro` deployment
- Azure credentials configured (`az login` or managed identity)
- `.env` file at repo root (copy `.env.example` → `.env`, fill in endpoint)

## Launch

From the repo root:

```bash
uv run streamlit run demo/app.py
```

The app opens at `http://localhost:8501`.

## UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Sidebar                                                         │
│  • Scenario picker (dropdown)                                    │
│  • Persona card (JSON)                                           │
│  • Reset conversation button                                     │
├──────────────────────────────┬──────────────────────────────────┤
│  Patient Chat (left)         │  Agent Trace (right)             │
│  • Patient messages          │  • Per-turn collapsible expander │
│  • Orchestrator replies      │  • Sub-agent called              │
│  • Amber HITL banner         │  • Tool invoked                  │
│                              │  • Fixture name + stub response  │
│                              │  • Sub-agent HITL signal         │
└──────────────────────────────┴──────────────────────────────────┘
```

---

## Scenario 1 — Happy Path Booking

**Dropdown:** `happy_path_booking`  
**Persona:** Commercial PPO, English-speaking adult  
**Story:** Routine checkup, coverage confirmed, slot available, appointment booked end-to-end with no friction.

| Turn | Type this | What to watch |
|------|-----------|---------------|
| 1 | `I need to schedule a routine checkup with my primary care doctor.` | Orchestrator calls eligibility → scheduling. Trace shows `check_eligibility` (covered fixture, co-pay $30) then `search_available_slots` (full_slots fixture). |
| 2 | `What time is the appointment and who is the doctor?` | Orchestrator pulls from conversation history — no new sub-agent calls this turn. Trace shows empty. |
| 3 | `What will my co-pay be for this visit?` | Orchestrator recalls eligibility result from turn 1 — co-pay $30. No new routing needed. |

**What to highlight to the audience:**
- Turn 1 trace shows two sub-agents called in sequence — eligibility check gates the booking
- No HITL banner — clean happy path end-to-end
- Turns 2 and 3 demonstrate multi-turn memory: the orchestrator answers without re-calling sub-agents

---

## Scenario 2 — Prior Auth Required (Approved)

**Dropdown:** `prior_auth_approved`  
**Persona:** Medicare, English-speaking elderly patient  
**Story:** Specialist visit requires prior auth — but it was pre-approved. Booking proceeds after the orchestrator communicates the PA reference number.

| Turn | Type this | What to watch |
|------|-----------|---------------|
| 1 | `I need to book an appointment with a cardiologist.` | Trace shows `check_eligibility` returning `prior_auth_required: true`, `prior_auth_status: approved`, ref `PA-2026-00441`. No HITL banner — PA already cleared. |
| 2 | `What is the prior authorization number I'll need to give the specialist's office?` | Orchestrator recalls `PA-2026-00441` from turn 1 history. No new sub-agent call. |
| 3 | `Great. Please go ahead and book the appointment.` | Trace shows `search_available_slots` then `book_appointment` (confirmed fixture). Orchestrator confirms booking with appointment ID. |

**What to highlight:**
- Prior auth gate visible in trace JSON — `prior_auth_status: approved` in eligibility stub response
- Orchestrator communicates the PA reference to the patient without human intervention
- Compare with Scenario 3 to show the difference between approved vs denied PA outcomes

---

## Scenario 3 — Prior Auth Denied → HITL

**Dropdown:** `prior_auth_denied_hitl`  
**Persona:** Medicaid, Spanish-speaking adult  
**Story:** Prior auth required but denied. Orchestrator cannot proceed with booking and escalates to a benefits coordinator.

| Turn | Type this | What to watch |
|------|-----------|---------------|
| 1 | `I need to schedule a specialist visit for my knee.` | Trace shows `check_eligibility` returning `prior_auth_required: true`, `prior_auth_status: denied`. **Amber HITL banner** appears: `reason: eligibility_failure`, `confidence: 0.97`. |
| 2 | `Is there anything I can do to appeal the denial?` | Orchestrator explains escalation — patient needs to speak with a benefits coordinator. Amber banner remains visible in trace. |
| 3 | `Who do I contact and what's the phone number?` | Orchestrator provides benefits coordinator contact per the escalation protocol. No new sub-agent routing — orchestrator handles from context. |

**What to highlight:**
- Amber HITL banner is the key demo moment — point to it explicitly
- Trace JSON shows the raw `{escalate: true, reason: eligibility_failure}` signal from the eligibility sub-agent
- The orchestrator never routes directly to a human — it emits the signal and the platform (or operator) handles escalation routing
- This scenario uses the Medicaid persona — eligibility denial rates are higher in this population, which is the business motivation for the HITL checkpoint

---

## Scenario 4 — No Slots Available → HITL

**Dropdown:** `no_slots_hitl`  
**Persona:** Commercial PPO, English-speaking adult  
**Story:** Coverage is confirmed but no appointment slots are available. Patient is placed on waitlist with a HITL escalation for coordinator follow-up.

| Turn | Type this | What to watch |
|------|-----------|---------------|
| 1 | `I need to see a doctor as soon as possible.` | Eligibility returns covered. Trace shows `search_available_slots` returning `no_availability` fixture. **Amber HITL banner**: `reason: no_available_slots`. |
| 2 | `How long is the typical wait?` | Orchestrator explains waitlist situation and expected timeframe. No new sub-agent calls. |
| 3 | `Please add me to the waitlist and notify me when a slot opens.` | Orchestrator confirms waitlist enrollment and explains notification process. The coordinator will follow up — HITL path is active. |

**What to highlight:**
- Two sub-agents called in turn 1: eligibility (covered) then scheduling (no_availability) — coverage confirmed but still can't book
- HITL escalates to a scheduling coordinator, not a clinician — this is an operational escalation, not a safety one
- Contrast with Scenario 5 where HITL is a clinical safety escalation

---

## Scenario 5 — Red Flag Triage → HITL

**Dropdown:** `red_flag_triage_hitl`  
**Persona:** Commercial PPO, English-speaking adult  
**Story:** Patient presents with escalating symptoms. Triage agent classifies EMERGENT and escalates to nurse + 911 path.

| Turn | Type this | What to watch |
|------|-----------|---------------|
| 1 | `I've been having some tightness in my chest for the past hour.` | Orchestrator routes to triage. Triage Agent (tool-free — no fixtures needed) assesses symptoms. Depending on phrasing, may classify URGENT and ask follow-up questions. |
| 2 | `It's getting worse and I'm having trouble breathing and my left arm is going numb.` | Triage escalates: **Amber HITL banner** with `reason: red_flag_symptom`, `confidence: 0.99`. Orchestrator directs patient to call 911 immediately. |
| 3 | `Should I call 911 or drive myself to the ER?` | Orchestrator reinforces emergency protocol — call 911, do not drive. Triage scope integrity block prevents any scheduling action while red flag is active. |

**What to highlight:**
- Turn 1 may not immediately trigger HITL — symptoms escalate across turns, which mirrors real patient behavior
- Triage is tool-free: the trace shows the sub-agent called but no tool invocations — classification is pure LLM reasoning
- `confidence: 0.99` — the highest confidence threshold in the system; safety escalation is not probabilistic
- Scope integrity: the triage agent will not proceed to booking even if the patient asks — point this out explicitly

---

## Scenario 6 — Out of Network → HITL

**Dropdown:** `out_of_network_hitl`  
**Persona:** Uninsured adult  
**Story:** Patient requests a specific provider who is out of network. Orchestrator presents in-network alternatives and escalates to benefits coordinator for cost counseling.

| Turn | Type this | What to watch |
|------|-----------|---------------|
| 1 | `I'd like to make an appointment with Dr. Johnson.` | Trace shows `check_eligibility` returning `in_network: false`. **Amber HITL banner**: `reason: eligibility_failure`. Trace JSON shows `in_network_alternatives` field with alternative providers. |
| 2 | `Are there any in-network doctors I could see instead?` | Orchestrator surfaces the in-network alternatives from the stub response (visible in trace panel). Lists alternative providers. |
| 3 | `What would it cost if I still want to see Dr. Johnson out of network?` | Orchestrator cannot provide a cost estimate without benefits coordinator involvement — HITL path reinforced. Explains the escalation. |

**What to highlight:**
- Trace panel is the story here — expand the Turn 1 trace and show the `in_network_alternatives` array in the raw stub JSON
- Uninsured persona means there's no coverage fallback — cost counseling requires a human coordinator
- The orchestrator doesn't invent a cost estimate; it recognizes the boundary of its authority and escalates

---

## Tips for Live Demos

- **Start with Scenario 1** to show the clean happy path — establishes baseline before showing escalations
- **Use Scenario 5 last** — it's the most dramatic and leaves a strong impression
- **Open the trace expander** on every turn — the raw fixture JSON is often the most convincing thing for technical audiences
- **Reset between scenarios** using the sidebar button — conversation history is per-scenario
- Click an expander header to collapse it and keep the panel readable as turns accumulate
- If the orchestrator asks a clarifying question instead of routing immediately, answer it naturally and continue — this is expected LLM behavior

## Live Demo Recovery Playbook

When the agent produces unexpected output during a live presentation, use these
recovery steps:

1. **Agent loops or doesn't terminate.** Click "Reset conversation" in the
   sidebar. Reload the same scenario.
2. **HITL banner fires unexpectedly.** Tell the audience: *"This is the
   system's safety net — in production this routes to a human agent in under
   30 seconds."* Then proceed to the next prepared scenario.
3. **Stub fixture not found.** Check that the `stub_map` in
   `demo/scenarios.yaml` matches fixture filenames in `stubs/<agent>/<tool>/`
   exactly (no `.yaml` suffix in the map).
4. **Triage classifies ROUTINE when EMERGENT was expected.** Switch to
   `red_flag_triage_hitl` (chest-pain persona, TC-T-001 reference) which is
   pre-validated for emergent classification.
5. **Spanish scenario shows garbled characters.** Fall back to
   `happy_path_booking` (English persona). File a UI issue; this is a known
   font/encoding edge case.

