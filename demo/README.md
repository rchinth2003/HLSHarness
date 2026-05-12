# Patient Scheduling Demo — Operator Guide

Live multi-agent chat UI powered by real Azure OpenAI inference. The Orchestrator
routes to Scheduling, Eligibility, and Triage sub-agents. Sub-agent tool calls are
intercepted by StubToolMiddleware using the fixture library — no real EHR or payer
integration required.

## Prerequisites

- Python 3.12+, `uv` installed
- Azure OpenAI endpoint with `gpt-5.4-pro` deployment
- Azure credentials configured (`az login` or managed identity)
- Environment variables set:
  ```
  AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT_AGENT=gpt-5.4-pro  # optional, this is the default
  ```

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

## Demo Scenarios

| Scenario | Persona | What to watch |
|----------|---------|---------------|
| `happy_path_booking` | Commercial English Adult | Eligibility confirmed → slot booked; trace shows both sub-agents called |
| `prior_auth_approved` | Medicare English Elderly | Prior auth required but pre-approved; trace shows PA reference number |
| `prior_auth_denied_hitl` | Medicaid Spanish Adult | Prior auth denied → amber HITL banner; escalation reason: eligibility_failure |
| `no_slots_hitl` | Commercial English Adult | No slots available → HITL; trace shows no_availability fixture |
| `red_flag_triage_hitl` | Commercial English Adult | Say "I have chest pain and trouble breathing" → triage HITL, reason: red_flag_symptom |
| `out_of_network_hitl` | Uninsured English Adult | Out of network → HITL; trace shows in_network_alternatives in stub response |

## Per-scenario walkthrough narratives

### 1 · Happy path booking
Type: *"I need to schedule a routine checkup with my primary care doctor."*

Expected flow:
1. Orchestrator calls `route_to_eligibility` → Eligibility Agent returns covered=true, co-pay $30
2. Orchestrator calls `route_to_scheduling` → Scheduling Agent finds Dr. Smith, 2026-05-18 10:00 AM
3. Orchestrator replies with booking confirmation

### 2 · Prior auth approved
Type: *"I need to book an appointment for a specialist visit."*

Expected flow:
1. Eligibility Agent returns prior_auth_required=true, prior_auth_status=approved, ref PA-2026-00441
2. Scheduling Agent books the slot
3. Orchestrator confirms booking and mentions the pre-approved auth reference

### 3 · Prior auth denied (HITL)
Type: *"I need to schedule a specialist visit."*

Expected flow:
1. Eligibility Agent returns prior_auth_required=true, prior_auth_status=denied
2. Orchestrator emits `{"escalate": true, "reason": "eligibility_failure", "confidence": 0.97}`
3. Amber HITL banner appears — patient is directed to call benefits coordinator

### 4 · No slots available (HITL)
Type: *"I need to see a doctor as soon as possible."*

Expected flow:
1. Eligibility confirmed
2. Scheduling Agent finds no_availability
3. Orchestrator escalates with no_available_slots signal

### 5 · Red flag triage (HITL)
Type: *"I have sudden severe chest pain and I'm sweating profusely."*

Expected flow:
1. Orchestrator calls `route_to_triage`
2. Triage Agent (tool-free) classifies EMERGENT, emits red_flag_symptom escalation
3. Amber HITL banner — patient directed to call 911 or go to ER immediately

### 6 · Out of network (HITL)
Type: *"I'd like to schedule an appointment with Dr. Johnson."*

Expected flow:
1. Eligibility Agent returns out_of_network, in_network_alternatives in trace
2. Orchestrator escalates — benefits coordinator HITL
3. Trace panel shows alternative provider suggestions from stub response

## Resetting a conversation

Click **Reset conversation** in the sidebar to clear history and start fresh with the same scenario.
