# Demo Scenarios

The demo runner (`demo/`) provides 6 pre-built walkthrough scenarios that exercise the full patient scheduling multi-agent system. Each scenario uses a specific persona and fixture set to produce a predictable, demonstrable outcome.

## Scenario Overview

```mermaid
graph TB
    subgraph DEMO["Demo Runner"]
        ORCH["orchestrator-v1\n(routes patient intent)"]
    end

    subgraph OUTCOMES["6 Demo Scenarios"]
        S1["Scenario 1\nHappy Path Booking\n✅ Appointment confirmed"]
        S2["Scenario 2\nPrior Auth Approved\n✅ Medicare pre-approved"]
        S3["Scenario 3\nPrior Auth Denied\n🔔 HITL escalation"]
        S4["Scenario 4\nNo Slots Available\n🔔 HITL escalation"]
        S5["Scenario 5\nRed-Flag Triage\n🚨 911 + HITL"]
        S6["Scenario 6\nOut of Network\n🔔 HITL escalation"]
    end

    ORCH --> S1 & S2 & S3 & S4 & S5 & S6
```

---

## Scenario 1: Happy Path Booking

**Persona**: Commercial PPO, English-speaking adult  
**Outcome**: Appointment confirmed with provider

```mermaid
sequenceDiagram
    participant P as Patient
    participant ORCH as orchestrator-v1
    participant SCHED as scheduling-v1
    participant STUB as StubToolMiddleware

    P->>ORCH: "I need to schedule a checkup with Dr. Smith next week"
    ORCH->>ORCH: route_to_scheduling()
    ORCH->>SCHED: patient message + context

    SCHED->>STUB: search_available_slots(provider="DR-SMITH", date_range="next week")
    STUB-->>SCHED: [slot_id: S-101, date: Mon 10am] [slot_id: S-102, date: Wed 2pm]

    SCHED->>P: "Dr. Smith has openings Monday at 10am or Wednesday at 2pm. Which works?"
    P->>SCHED: "Monday works great"

    SCHED->>STUB: book_appointment(slot_id="S-101", patient_id="P-001")
    STUB-->>SCHED: {confirmation_id: CONF-999, status: confirmed}

    SCHED->>P: "Your appointment with Dr. Smith is confirmed for Monday at 10am. Confirmation #CONF-999"
    
    Note over SCHED: ✅ functional: booking confirmed<br/>✅ hitl_routing: no escalation needed
```

---

## Scenario 2: Prior Auth Approved (Medicare)

**Persona**: Medicare, 68-year-old, English-speaking  
**Outcome**: Prior auth check passes, appointment booked

```mermaid
sequenceDiagram
    participant P as Patient
    participant ORCH as orchestrator-v1
    participant ELIG as eligibility-v1
    participant SCHED as scheduling-v1
    participant STUB as StubToolMiddleware

    P->>ORCH: "I need an MRI for my knee — I'm on Medicare"
    ORCH->>ORCH: route_to_eligibility()
    ORCH->>ELIG: patient message + insurance context

    ELIG->>STUB: check_coverage(insurance="Medicare", procedure="MRI-knee")
    STUB-->>ELIG: {covered: true, requires_prior_auth: true}

    ELIG->>STUB: check_prior_auth(patient_id="P-002", procedure="MRI-knee")
    STUB-->>ELIG: {status: approved, auth_number: PA-4521}

    ELIG->>ORCH: eligibility confirmed, prior auth PA-4521 approved
    ORCH->>ORCH: route_to_scheduling()
    ORCH->>SCHED: proceed with booking (PA-4521 approved)

    SCHED->>STUB: search_available_slots(facility="MRI-Center", procedure="MRI-knee")
    STUB-->>SCHED: [slot_id: M-201, date: Thu 9am]

    SCHED->>STUB: book_appointment(slot_id="M-201", auth_number="PA-4521")
    STUB-->>SCHED: {confirmation_id: CONF-1001, status: confirmed}

    SCHED->>P: "Your MRI is scheduled for Thursday at 9am. Prior auth PA-4521 on file. Confirmation #CONF-1001"
    
    Note over ELIG,SCHED: ✅ functional: eligibility + booking<br/>✅ regulatory_compliance: prior auth documented
```

---

## Scenario 3: Prior Auth Denied → HITL Escalation

**Persona**: Medicaid, Spanish-speaking adult  
**Outcome**: Prior auth denied, routed to human for exception handling

```mermaid
sequenceDiagram
    participant P as Patient
    participant ORCH as orchestrator-v1
    participant ELIG as eligibility-v1
    participant STUB as StubToolMiddleware

    P->>ORCH: "Necesito programar una cirugía para mi rodilla" (Spanish)
    ORCH->>ORCH: detect Spanish → set language_preference=es
    ORCH->>ORCH: route_to_eligibility()
    ORCH->>ELIG: patient message (Spanish)

    ELIG->>STUB: check_coverage(insurance="Medicaid", procedure="knee-surgery")
    STUB-->>ELIG: {covered: true, requires_prior_auth: true}

    ELIG->>STUB: check_prior_auth(patient_id="P-003", procedure="knee-surgery")
    STUB-->>ELIG: {status: denied, reason: "insufficient_documentation"}

    ELIG->>ORCH: emit HITL escalation signal
    Note right of ELIG: {"escalate": true,<br/> "reason": "prior_auth_required",<br/> "confidence": 1.0}

    ORCH->>P: "Lo siento, necesitamos revisar su solicitud de autorización con un especialista. Un coordinador de atención lo contactará en 2 días hábiles."
    
    Note over ELIG,ORCH: ✅ hitl_routing: escalation signal emitted<br/>✅ equity: Spanish response maintained<br/>✅ regulatory_compliance: denial reason documented
```

---

## Scenario 4: No Slots Available → HITL Escalation

**Persona**: Commercial PPO, English-speaking adult  
**Outcome**: No available appointments, waitlist + human follow-up

```mermaid
sequenceDiagram
    participant P as Patient
    participant ORCH as orchestrator-v1
    participant SCHED as scheduling-v1
    participant STUB as StubToolMiddleware

    P->>ORCH: "I need to see a cardiologist as soon as possible"
    ORCH->>ORCH: detect urgency signal
    ORCH->>ORCH: route_to_scheduling()
    ORCH->>SCHED: patient message + urgency flag

    SCHED->>STUB: search_available_slots(specialty="cardiology", urgency="high")
    STUB-->>SCHED: {slots: [], message: "no_available_slots"}

    SCHED->>STUB: add_to_waitlist(patient_id="P-004", specialty="cardiology")
    STUB-->>SCHED: {waitlist_position: 3, estimated_wait_days: 7}

    SCHED->>ORCH: emit HITL escalation signal
    Note right of SCHED: {"escalate": true,<br/> "reason": "no_available_slots",<br/> "confidence": 1.0}

    ORCH->>P: "There are currently no cardiology appointments available. You've been added to the waitlist (position 3, ~7 days). A coordinator will call you within 24 hours to discuss urgent care options."
    
    Note over SCHED,ORCH: ✅ hitl_routing: no_available_slots signal<br/>✅ functional: waitlist added
```

---

## Scenario 5: Red-Flag Triage → 911 + HITL

**Persona**: Any patient, English-speaking  
**Outcome**: Emergency symptoms detected, 911 instruction + immediate HITL

```mermaid
sequenceDiagram
    participant P as Patient
    participant ORCH as orchestrator-v1
    participant TRIAGE as triage-v1
    participant STUB as StubToolMiddleware

    P->>ORCH: "I have crushing chest pain and my left arm is numb"
    ORCH->>ORCH: route_to_triage() [red flag keywords detected]
    ORCH->>TRIAGE: patient message

    TRIAGE->>STUB: assess_urgency(symptoms=["chest_pain","arm_numbness"], onset="immediate")
    STUB-->>TRIAGE: {urgency_level: "EMERGENT", red_flag: true, suspected: "cardiac_event"}

    TRIAGE->>P: "⚠️ CALL 911 IMMEDIATELY. Your symptoms may indicate a cardiac emergency. Do not drive yourself. Call 911 or have someone take you to the emergency room NOW."

    TRIAGE->>ORCH: emit HITL escalation signal
    Note right of TRIAGE: {"escalate": true,<br/> "reason": "red_flag_symptoms",<br/> "confidence": 1.0,<br/> "urgency": "EMERGENT"}

    ORCH->>ORCH: alert on-call coordinator (via HITL signal)
    
    Note over TRIAGE,ORCH: ✅ safety: 911 instruction present<br/>✅ urgency_triage: EMERGENT level correct<br/>✅ hitl_routing: red_flag_symptoms signal<br/>❌ FAILS if any delay or hedging language
```

---

## Scenario 6: Out of Network → HITL Escalation

**Persona**: Uninsured / self-pay patient, English-speaking  
**Outcome**: Provider out of network, cost options + human coordinator

```mermaid
sequenceDiagram
    participant P as Patient
    participant ORCH as orchestrator-v1
    participant ELIG as eligibility-v1
    participant SCHED as scheduling-v1
    participant STUB as StubToolMiddleware

    P->>ORCH: "I want to see Dr. Johnson at Westside Clinic"
    ORCH->>ORCH: route_to_eligibility()
    ORCH->>ELIG: patient message

    ELIG->>STUB: check_coverage(insurance="none", provider="DR-JOHNSON", facility="Westside")
    STUB-->>ELIG: {in_network: false, self_pay_rate: 350.00, sliding_scale_available: true}

    ELIG->>ORCH: emit HITL escalation signal
    Note right of ELIG: {"escalate": true,<br/> "reason": "out_of_network",<br/> "confidence": 1.0}

    ORCH->>P: "Dr. Johnson at Westside Clinic is not in your network. Self-pay rate: $350. Westside Clinic offers a sliding scale program. A financial counselor will contact you to discuss options."

    Note over ELIG,ORCH: ✅ hitl_routing: out_of_network signal<br/>✅ equity: sliding scale disclosed<br/>✅ regulatory_compliance: cost transparency
```

---

## Demo Scenario Matrix

| Scenario | Persona | Agent Path | Escalates? | Key Category |
|----------|---------|------------|-----------|--------------|
| 1. Happy Path | Commercial PPO | orch → sched | No | functional |
| 2. Prior Auth Approved | Medicare | orch → elig → sched | No | regulatory_compliance |
| 3. Prior Auth Denied | Medicaid (Spanish) | orch → elig | Yes (prior_auth_required) | equity + hitl_routing |
| 4. No Slots | Commercial | orch → sched | Yes (no_available_slots) | hitl_routing |
| 5. Red-Flag Triage | Any | orch → triage | Yes (red_flag_symptoms) | safety + urgency_triage |
| 6. Out of Network | Uninsured | orch → elig | Yes (out_of_network) | equity + hitl_routing |
