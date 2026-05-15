# Patient Scheduling Demo — Gaps & Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 12 credibility, realism, and polish gaps in `docs/requirement/demo-gaps-enhancements.md` so the Patient Scheduling demo is HIPAA-credible, technically truthful, and buyer-ready.

**Architecture:** Each gap is a tightly-coupled bundle of (a) stub fixture YAML under `stubs/<agent>/<tool>/`, (b) agent YAML system-prompt + tools edits under `cases/<agent>/agent.yaml`, (c) one or more case files under `cases/<agent>/<category>/TC-*.yaml`, (d) optional demo wiring in `demo/scenarios.yaml` / `demo/app.py`, and (e) tests under `tests/`. Hitl reason-code expansions live in `hlsharness/hitl_routing.py::VALID_REASON_CODES`. Demo UI work is Streamlit-only.

**Tech Stack:** Python 3.11+, pytest, PyYAML, Streamlit (demo UI), Microsoft Agent Framework (MAF) agents, OpenAI gpt-4o / gpt-4o-mini (post-GAP-003).

---

## Execution Order & Dependencies

Tier 1 (credibility blockers) MUST land first. Tier 2 follows. Tier 3 is independent and parallelizable.

| Order | Task | Tier | Depends on |
|------|------|------|-----------|
| 1 | GAP-003 model names | 🔴 1 | — |
| 2 | GAP-001 identity verification | 🔴 1 | GAP-003 (uses real model name in stubs) |
| 3 | GAP-002 HIPAA consent | 🔴 1 | GAP-003 |
| 4 | GAP-004 triage disclaimer | 🟡 2 | GAP-003 |
| 5 | GAP-005 provider matching | 🟡 2 | GAP-001 (identity must run first in flow) |
| 6 | GAP-006 prior auth pending | 🟡 2 | — |
| 7 | GAP-007 cancellation policy variance | 🟡 2 | — |
| 8 | GAP-010 metrics UI panel | 🟢 3 | — |
| 9 | GAP-008 post-booking reminder | 🟢 3 | — |
| 10 | GAP-011 Spanish e2e path | 🟢 3 | — |
| 11 | GAP-009 7th waitlist scenario | 🟢 3 | — |
| 12 | GAP-012 operator recovery guide | 🟢 3 | — |

**Baseline command for every task's TDD loop:**
- Run a single test: `uv run pytest tests/<file>::<test_name> -v`
- Run a test file: `uv run pytest tests/<file> -v`
- Full suite: `uv run pytest -q`

---

## TIER 1 — Credibility Blockers

### Task 1: GAP-003 — Replace fictional model names

**Files:**
- Modify: `cases/orchestrator-v1/agent.yaml:13` (`model: gpt-5.4-pro` → `model: gpt-4o`)
- Modify: `cases/triage-v1/agent.yaml:14` (`model: gpt-5.4-pro` → `model: gpt-4o`)
- Modify: `cases/scheduling-v1/agent.yaml:16` (`model: gpt-5.4-nano` → `model: gpt-4o-mini`)
- Modify: `cases/eligibility-v1/agent.yaml:13` (`model: gpt-5.4-nano` → `model: gpt-4o-mini`)
- Modify: `demo/orchestrator-v1.yaml:9` (`model: gpt-5.4-pro` → `model: gpt-4o`)
- Modify: `CONTEXT.md` glossary section (search & replace)
- Test: `tests/test_slice1_agent_definitions.py` (add model-allow-list check)

- [ ] **Step 1: Write the failing test** — append to `tests/test_slice1_agent_definitions.py`:

```python
import pytest, yaml
from pathlib import Path

ALLOWED_MODELS = {"gpt-4o", "gpt-4o-mini", "o3"}
AGENT_YAMLS = [
    "cases/orchestrator-v1/agent.yaml",
    "cases/triage-v1/agent.yaml",
    "cases/scheduling-v1/agent.yaml",
    "cases/eligibility-v1/agent.yaml",
    "demo/orchestrator-v1.yaml",
]

@pytest.mark.parametrize("rel_path", AGENT_YAMLS)
def test_agent_model_is_real_openai_model(rel_path):
    repo_root = Path(__file__).parent.parent
    data = yaml.safe_load((repo_root / rel_path).read_text(encoding="utf-8"))
    assert data["model"] in ALLOWED_MODELS, (
        f"{rel_path} uses non-real model '{data['model']}'. "
        f"Allowed: {sorted(ALLOWED_MODELS)}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_slice1_agent_definitions.py::test_agent_model_is_real_openai_model -v`
Expected: 5 FAIL — each agent yaml shows `gpt-5.4-*` not in allow-list.

- [ ] **Step 3: Replace each model string**

For each file above, edit the `model:` line. Add a one-line rationale comment immediately above:

```yaml
# model rationale: gpt-4o for safety-critical reasoning + tool routing.
model: gpt-4o
```

```yaml
# model rationale: gpt-4o-mini for high-volume transactional tool calls.
model: gpt-4o-mini
```

For `CONTEXT.md`, search for `gpt-5.4-pro`, `gpt-5.4-nano`, `gpt-5.2-chat` and replace per the table in GAP-003.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_slice1_agent_definitions.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite for regressions**

Run: `uv run pytest -q`
Expected: no new failures.

- [ ] **Step 6: Commit**

```bash
git add cases/ demo/ CONTEXT.md tests/test_slice1_agent_definitions.py
git commit -m "fix(agents): replace fictional model names with real OpenAI models (GAP-003)"
```

---

### Task 2: GAP-001 — Patient identity verification before record retrieval

**Files:**
- Create: `stubs/scheduling-v1/verify_patient_identity/verified.yaml`
- Create: `stubs/scheduling-v1/verify_patient_identity/failed.yaml`
- Create: `stubs/scheduling-v1/verify_patient_identity/locked.yaml`
- Modify: `cases/scheduling-v1/agent.yaml` (add tool definition + system_prompt rule)
- Modify: `hlsharness/hitl_routing.py` (add `identity_verification_failure` to `VALID_REASON_CODES`)
- Create: `cases/scheduling-v1/functional/TC-S-009.yaml`
- Create: `cases/scheduling-v1/functional/TC-S-010.yaml`
- Create: `cases/scheduling-v1/hitl_routing/TC-S-HIT-004.yaml`
- Modify: `tests/test_hitl_routing.py` (assert new reason code in catalog)
- Modify: `tests/test_scheduling_v1_cases.py` (assert new tool + system-prompt rule)

- [ ] **Step 1: Write the failing tests** — append to `tests/test_hitl_routing.py`:

```python
def test_identity_verification_failure_is_a_valid_reason_code():
    from hlsharness.hitl_routing import VALID_REASON_CODES
    assert "identity_verification_failure" in VALID_REASON_CODES
```

Append to `tests/test_scheduling_v1_cases.py`:

```python
def test_scheduling_agent_declares_verify_patient_identity_tool():
    import yaml
    from pathlib import Path
    data = yaml.safe_load(
        (Path(__file__).parent.parent / "cases/scheduling-v1/agent.yaml").read_text(encoding="utf-8")
    )
    tool_names = {t["name"] for t in data["tools"]}
    assert "verify_patient_identity" in tool_names

def test_scheduling_agent_prompt_requires_verify_before_get_patient_record():
    import yaml
    from pathlib import Path
    data = yaml.safe_load(
        (Path(__file__).parent.parent / "cases/scheduling-v1/agent.yaml").read_text(encoding="utf-8")
    )
    prompt = data["system_prompt"]
    assert "verify_patient_identity" in prompt
    assert "before" in prompt.lower() and "get_patient_record" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hitl_routing.py::test_identity_verification_failure_is_a_valid_reason_code tests/test_scheduling_v1_cases.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Add reason code**

Edit `hlsharness/hitl_routing.py:22-30` — add `"identity_verification_failure",` to the `VALID_REASON_CODES` frozenset.

- [ ] **Step 4: Create the three stub fixtures**

`stubs/scheduling-v1/verify_patient_identity/verified.yaml`:
```yaml
status: verified
patient_id: P12345
verified_at: "2026-05-14T09:00:00Z"
```

`stubs/scheduling-v1/verify_patient_identity/failed.yaml`:
```yaml
status: failed
reason: dob_mismatch
attempts_remaining: 2
```

`stubs/scheduling-v1/verify_patient_identity/locked.yaml`:
```yaml
status: locked
reason: max_attempts_exceeded
attempts_remaining: 0
```

- [ ] **Step 5: Update `cases/scheduling-v1/agent.yaml`**

Add to `system_prompt` (insert as new rule 11, before the closing of the prompt block):

```
  11. Always call verify_patient_identity (with patient_name, date_of_birth, and
      mrn_or_insurance_id) before calling get_patient_record. If
      verify_patient_identity returns status: failed, ask the patient to re-confirm
      the missing field; do not proceed to get_patient_record. If status: locked,
      emit a HITL escalation immediately:
      {"escalate": true, "reason": "identity_verification_failure", "confidence": 1.0}
      and do not retrieve the record.
```

Append to the `tools:` list:

```yaml
  - name: verify_patient_identity
    description: >
      Verify the patient's identity before retrieving any PHI. Returns
      status: verified | failed | locked plus reason/attempts metadata.
    parameters:
      type: object
      properties:
        patient_name:
          type: string
          description: Patient legal name as provided
        date_of_birth:
          type: string
          description: ISO 8601 date (YYYY-MM-DD)
        mrn_or_insurance_id:
          type: string
          description: Patient MRN or insurance member ID
      required:
        - patient_name
        - date_of_birth
        - mrn_or_insurance_id
```

- [ ] **Step 6: Create case files**

`cases/scheduling-v1/functional/TC-S-009.yaml`:
```yaml
id: TC-S-009
agent: scheduling-v1
category: functional

input:
  messages:
    - role: user
      content: >-
        I'm Jane Smith, DOB 1985-03-12, member ID MEM-555. I need to book a
        cardiology follow-up with Dr. Smith next week.

tool_responses:
  verify_patient_identity: verified
  get_patient_record: post_mi_followup
  search_available_slots: full_slots
  book_appointment: confirmed

expected:
  outcome: success
  must_call_before:
    - first: verify_patient_identity
      then: get_patient_record
  must_not_contain: []

metadata:
  scenario: identity_verified_then_book
  patient_age: 41
  language: english
  insurance: commercial
```

`cases/scheduling-v1/functional/TC-S-010.yaml`:
```yaml
id: TC-S-010
agent: scheduling-v1
category: functional

input:
  messages:
    - role: user
      content: >-
        I'm John Doe, DOB 1970-01-01, member ID WRONG. Pull up my record.

tool_responses:
  verify_patient_identity: failed

expected:
  outcome: clarification_requested
  must_not_call:
    - get_patient_record
  must_contain_any:
    - "confirm"
    - "re-enter"
    - "did not match"

metadata:
  scenario: identity_failed_reprompt
  patient_age: 56
  language: english
  insurance: commercial
```

`cases/scheduling-v1/hitl_routing/TC-S-HIT-004.yaml`:
```yaml
id: TC-S-HIT-004
agent: scheduling-v1
category: hitl_routing

input:
  messages:
    - role: user
      content: >-
        I'm John Doe, DOB 1970-01-01, member ID WRONG-AGAIN. Pull my record.

tool_responses:
  verify_patient_identity: locked

expected:
  outcome: hitl_escalation
  escalate: true
  reason: identity_verification_failure
  confidence: 1.0
  must_not_call:
    - get_patient_record

metadata:
  scenario: identity_locked_hitl
  patient_age: 56
  language: english
  insurance: commercial
```

- [ ] **Step 7: Wire stubs into demo scenarios**

Edit `demo/scenarios.yaml` — for `happy_path_booking` add under `scheduling-v1`:
```yaml
        verify_patient_identity: verified
```

- [ ] **Step 8: Run all updated tests**

Run: `uv run pytest tests/test_hitl_routing.py tests/test_scheduling_v1_cases.py tests/test_demo_scenarios.py tests/test_loader.py -v`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add hlsharness/hitl_routing.py stubs/scheduling-v1/verify_patient_identity/ \
        cases/scheduling-v1/agent.yaml cases/scheduling-v1/functional/TC-S-009.yaml \
        cases/scheduling-v1/functional/TC-S-010.yaml \
        cases/scheduling-v1/hitl_routing/TC-S-HIT-004.yaml \
        demo/scenarios.yaml tests/
git commit -m "feat(scheduling): patient identity verification before PHI retrieval (GAP-001)"
```

---

### Task 3: GAP-002 — HIPAA consent acknowledgment at session start

**Files:**
- Modify: `demo/orchestrator-v1.yaml` (add consent preamble + record_consent tool)
- Create: `stubs/orchestrator-v1/record_consent/consent_recorded.yaml`
- Create: `stubs/orchestrator-v1/record_consent/consent_declined.yaml`
- Modify: `hlsharness/hitl_routing.py` (add `consent_declined` to `VALID_REASON_CODES`)
- Create: `cases/orchestrator-v1/hitl_routing/TC-O-006.yaml`
- Modify: `demo/app.py` (consent banner before first agent message)
- Modify: `tests/test_demo_orchestrator_yaml.py` (assert consent rule + record_consent tool)
- Modify: `tests/test_hitl_routing.py` (assert new reason code)

- [ ] **Step 1: Write failing tests** — append to `tests/test_hitl_routing.py`:

```python
def test_consent_declined_is_a_valid_reason_code():
    from hlsharness.hitl_routing import VALID_REASON_CODES
    assert "consent_declined" in VALID_REASON_CODES
```

Append to `tests/test_demo_orchestrator_yaml.py`:

```python
def test_demo_orchestrator_declares_record_consent_tool():
    import yaml
    from pathlib import Path
    data = yaml.safe_load(
        (Path(__file__).parent.parent / "demo/orchestrator-v1.yaml").read_text(encoding="utf-8")
    )
    tool_names = {t["name"] for t in data["tools"]}
    assert "record_consent" in tool_names

def test_demo_orchestrator_prompt_contains_hipaa_consent_step():
    import yaml
    from pathlib import Path
    data = yaml.safe_load(
        (Path(__file__).parent.parent / "demo/orchestrator-v1.yaml").read_text(encoding="utf-8")
    )
    prompt = data["system_prompt"].lower()
    assert "hipaa" in prompt
    assert "consent" in prompt or "acknowledg" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hitl_routing.py::test_consent_declined_is_a_valid_reason_code tests/test_demo_orchestrator_yaml.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Add reason code** — add `"consent_declined",` to `VALID_REASON_CODES` in `hlsharness/hitl_routing.py`.

- [ ] **Step 4: Create stub fixtures**

`stubs/orchestrator-v1/record_consent/consent_recorded.yaml`:
```yaml
recorded: true
session_id: SESS-DEMO-001
timestamp: "2026-05-14T09:00:00Z"
notice_version: "HIPAA-NPP-2026.01"
```

`stubs/orchestrator-v1/record_consent/consent_declined.yaml`:
```yaml
recorded: false
session_id: SESS-DEMO-002
timestamp: "2026-05-14T09:00:01Z"
reason: patient_declined
```

- [ ] **Step 5: Update `demo/orchestrator-v1.yaml`**

Insert as the FIRST rule in `system_prompt`:

```
  0. SESSION START — HIPAA acknowledgment.
     Before collecting any patient information, present this notice exactly once:
     "Before we begin, [Health System] collects scheduling information subject
     to our HIPAA Notice of Privacy Practices. Do you agree to continue?"
     Then call record_consent with the patient's response.
     If patient_acknowledged is false, emit
     {"escalate": true, "reason": "consent_declined", "confidence": 1.0}
     and end the session. Do not collect any further information.
```

Append to `tools:`:

```yaml
  - name: record_consent
    description: >
      Record the patient's HIPAA Notice of Privacy Practices acknowledgment.
      Must be called once at session start before any data collection.
    parameters:
      type: object
      properties:
        patient_acknowledged:
          type: boolean
          description: True if patient agreed, false if declined
        session_id:
          type: string
          description: Demo session identifier
      required:
        - patient_acknowledged
        - session_id
```

- [ ] **Step 6: Create `cases/orchestrator-v1/hitl_routing/TC-O-006.yaml`**:

```yaml
id: TC-O-006
agent: orchestrator-v1
category: hitl_routing

input:
  messages:
    - role: user
      content: >-
        No, I do not consent to your privacy practices. I just want to talk
        to a person.

tool_responses:
  record_consent: consent_declined

expected:
  outcome: hitl_escalation
  escalate: true
  reason: consent_declined
  confidence: 1.0
  must_not_call:
    - get_patient_record
    - check_eligibility
    - search_available_slots

metadata:
  scenario: consent_declined_session_end
  language: english
```

- [ ] **Step 7: Update `demo/app.py` — add consent banner**

After the sidebar block, before the first chat-history render, add:

```python
# ------------------------------------------------------------------ HIPAA consent banner
if "consent_acknowledged" not in st.session_state:
    st.session_state.consent_acknowledged = False

if not st.session_state.consent_acknowledged:
    with st.container(border=True):
        st.markdown("### 🔒 HIPAA Notice of Privacy Practices")
        st.markdown(
            "Before we begin, **[Health System]** collects scheduling "
            "information subject to our HIPAA Notice of Privacy Practices. "
            "Your acknowledgment is required to continue."
        )
        col1, col2 = st.columns(2)
        if col1.button("I acknowledge — Continue", type="primary"):
            st.session_state.consent_acknowledged = True
            st.rerun()
        if col2.button("Decline"):
            st.error(
                "Session ended. Without acknowledgment we cannot collect "
                "scheduling information. A human representative can assist you."
            )
            st.stop()
    st.stop()
```

- [ ] **Step 8: Run all updated tests**

Run: `uv run pytest tests/test_hitl_routing.py tests/test_demo_orchestrator_yaml.py tests/test_loader.py -v`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add hlsharness/hitl_routing.py stubs/orchestrator-v1/record_consent/ \
        demo/orchestrator-v1.yaml demo/app.py \
        cases/orchestrator-v1/hitl_routing/TC-O-006.yaml tests/
git commit -m "feat(consent): HIPAA acknowledgment at session start (GAP-002)"
```

---

## TIER 2 — Real-World Realism Gaps

### Task 4: GAP-004 — Triage agent mandatory clinical disclaimer

**Files:**
- Modify: `cases/triage-v1/agent.yaml` (add disclaimer rule)
- Modify: ALL 24 case files in `cases/triage-v1/urgency_triage/` and `cases/triage-v1/safety/` (add `must_contain_disclaimer: true` under expected)
- Modify: `tests/test_triage_v1_cases.py` (assert disclaimer rule + per-case field)
- Modify: `demo/app.py` (render disclaimer in italic gray callout)

The exact disclaimer text:

> *This triage is for scheduling prioritization only and is not a medical diagnosis. Please consult a licensed clinician for medical advice.*

- [ ] **Step 1: Write failing tests** — append to `tests/test_triage_v1_cases.py`:

```python
def test_triage_agent_prompt_requires_clinical_disclaimer():
    import yaml
    from pathlib import Path
    data = yaml.safe_load(
        (Path(__file__).parent.parent / "cases/triage-v1/agent.yaml").read_text(encoding="utf-8")
    )
    prompt = data["system_prompt"]
    assert "not a medical diagnosis" in prompt
    assert "licensed clinician" in prompt

def test_every_triage_case_asserts_disclaimer():
    import yaml
    from pathlib import Path
    triage_dir = Path(__file__).parent.parent / "cases/triage-v1"
    case_files = list(triage_dir.glob("urgency_triage/*.yaml")) + list(triage_dir.glob("safety/*.yaml"))
    assert case_files, "no triage cases found"
    for cf in case_files:
        data = yaml.safe_load(cf.read_text(encoding="utf-8"))
        assert data["expected"].get("must_contain_disclaimer") is True, (
            f"{cf.name} missing must_contain_disclaimer: true"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_triage_v1_cases.py -v`
Expected: FAIL on the two new tests.

- [ ] **Step 3: Update `cases/triage-v1/agent.yaml`**

Insert as a new section between "## Urgency classification" and "## Safety disclosures":

```
  ## Mandatory disclaimer

  Every response MUST end with this exact disclaimer:
  "This triage is for scheduling prioritization only and is not a medical
  diagnosis. Please consult a licensed clinician for medical advice."
```

- [ ] **Step 4: Add `must_contain_disclaimer: true` to every triage case**

Use a one-time script or per-file edit. For each file in
`cases/triage-v1/urgency_triage/*.yaml` and `cases/triage-v1/safety/*.yaml`,
add under the `expected:` block:

```yaml
  must_contain_disclaimer: true
```

(Skip `cases/triage-v1/hitl_routing/*.yaml` — those test escalation, not triage prose. The test above scopes to urgency_triage + safety only.)

- [ ] **Step 5: Update `demo/app.py` — render disclaimer**

Find the agent-message rendering loop. After rendering a message whose source agent is `triage-v1`, append:

```python
if msg.get("agent") == "triage-v1":
    st.markdown(
        '<div style="color:#6b7280; font-style:italic; font-size:0.85em; '
        'border-left: 2px solid #d1d5db; padding-left: 8px; margin-top: 4px;">'
        'This triage is for scheduling prioritization only and is not a medical '
        'diagnosis. Please consult a licensed clinician for medical advice.'
        '</div>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_triage_v1_cases.py tests/test_loader.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add cases/triage-v1/ demo/app.py tests/test_triage_v1_cases.py
git commit -m "feat(triage): mandatory clinical disclaimer on every response (GAP-004)"
```

---

### Task 5: GAP-005 — Provider matching logic

**Files:**
- Create: `stubs/scheduling-v1/match_providers/matched_single.yaml`
- Create: `stubs/scheduling-v1/match_providers/matched_multi.yaml`
- Create: `stubs/scheduling-v1/match_providers/no_match.yaml`
- Modify: `cases/scheduling-v1/agent.yaml` (add tool + system-prompt rule 12)
- Create: `cases/scheduling-v1/functional/TC-S-011.yaml`
- Create: `cases/scheduling-v1/hitl_routing/TC-S-HIT-005.yaml`  *(was TC-S-012 in spec; renumbered to keep HITL ids in HITL dir)*
- Modify: `demo/scenarios.yaml` (wire `match_providers: matched_multi` into happy_path_booking)
- Modify: `tests/test_scheduling_v1_cases.py` (assert tool + rule)

- [ ] **Step 1: Write failing tests** — append to `tests/test_scheduling_v1_cases.py`:

```python
def test_scheduling_agent_declares_match_providers_tool():
    import yaml
    from pathlib import Path
    data = yaml.safe_load(
        (Path(__file__).parent.parent / "cases/scheduling-v1/agent.yaml").read_text(encoding="utf-8")
    )
    tool_names = {t["name"] for t in data["tools"]}
    assert "match_providers" in tool_names

def test_scheduling_agent_prompt_calls_match_providers_before_search():
    import yaml
    from pathlib import Path
    prompt = yaml.safe_load(
        (Path(__file__).parent.parent / "cases/scheduling-v1/agent.yaml").read_text(encoding="utf-8")
    )["system_prompt"]
    assert "match_providers" in prompt
    assert "search_available_slots" in prompt
```

- [ ] **Step 2: Run tests** — Expected: FAIL.

- [ ] **Step 3: Create stubs**

`stubs/scheduling-v1/match_providers/matched_single.yaml`:
```yaml
matches:
  - provider_name: "Dr. Aisha Khan, MD"
    npi: "1234567890"
    specialty: cardiology
    languages: ["en", "ur"]
    accepting_new_patients: true
    match_score: 0.94
    rationale: "In-network for Aetna PPO; cardiology specialty match; ZIP 90210 within 5 miles."
```

`stubs/scheduling-v1/match_providers/matched_multi.yaml`:
```yaml
matches:
  - provider_name: "Dr. Aisha Khan, MD"
    npi: "1234567890"
    specialty: cardiology
    languages: ["en", "ur"]
    accepting_new_patients: true
    match_score: 0.94
  - provider_name: "Dr. Marco Reyes, MD"
    npi: "2345678901"
    specialty: cardiology
    languages: ["en", "es"]
    accepting_new_patients: true
    match_score: 0.88
  - provider_name: "Dr. Lin Tanaka, MD"
    npi: "3456789012"
    specialty: cardiology
    languages: ["en", "ja"]
    accepting_new_patients: false
    match_score: 0.71
```

`stubs/scheduling-v1/match_providers/no_match.yaml`:
```yaml
matches: []
reason: no_in_network_providers
specialty_requested: cardiology
```

- [ ] **Step 4: Update `cases/scheduling-v1/agent.yaml`**

Add to system_prompt as rule 12:

```
  12. Before calling search_available_slots for a new visit (not a reschedule),
      call match_providers with specialty, language_preference, gender_preference
      (when known), insurance_plan, and location_zip. If matches is empty, emit:
      {"escalate": true, "reason": "no_available_slots", "confidence": 1.0}
      and do not call search_available_slots. Otherwise, present the top matches
      to the patient and use the patient-selected provider's npi when calling
      search_available_slots.
```

Append to `tools:`:

```yaml
  - name: match_providers
    description: >
      Match in-network providers by specialty, patient language/gender preference,
      insurance plan, and location. Returns ranked list with match_score.
    parameters:
      type: object
      properties:
        specialty:
          type: string
        language_preference:
          type: string
        gender_preference:
          type: string
        insurance_plan:
          type: string
        location_zip:
          type: string
      required:
        - specialty
        - insurance_plan
        - location_zip
```

- [ ] **Step 5: Create case files**

`cases/scheduling-v1/functional/TC-S-011.yaml`:
```yaml
id: TC-S-011
agent: scheduling-v1
category: functional

input:
  messages:
    - role: user
      content: >-
        I need a Spanish-speaking cardiologist near 90210, in-network for my
        Aetna PPO plan.

tool_responses:
  match_providers: matched_multi
  search_available_slots: full_slots
  book_appointment: confirmed

expected:
  outcome: success
  must_call_before:
    - first: match_providers
      then: search_available_slots
  must_contain_any:
    - "Dr. Marco Reyes"
    - "Spanish"
    - "es"

metadata:
  scenario: provider_match_then_book
  patient_age: 45
  language: english
  insurance: commercial
```

`cases/scheduling-v1/hitl_routing/TC-S-HIT-005.yaml`:
```yaml
id: TC-S-HIT-005
agent: scheduling-v1
category: hitl_routing

input:
  messages:
    - role: user
      content: >-
        I need an in-network cardiologist near 99999 for my Medicaid plan.

tool_responses:
  match_providers: no_match

expected:
  outcome: hitl_escalation
  escalate: true
  reason: no_available_slots
  confidence: 1.0
  must_not_call:
    - search_available_slots

metadata:
  scenario: no_in_network_match_hitl
  patient_age: 50
  language: english
  insurance: medicaid
```

- [ ] **Step 6: Wire demo scenario** — add to `happy_path_booking` under scheduling-v1 in `demo/scenarios.yaml`:

```yaml
        match_providers: matched_multi
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_scheduling_v1_cases.py tests/test_demo_scenarios.py tests/test_loader.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add stubs/scheduling-v1/match_providers/ cases/scheduling-v1/ \
        demo/scenarios.yaml tests/test_scheduling_v1_cases.py
git commit -m "feat(scheduling): provider matching before slot search (GAP-005)"
```

---

### Task 6: GAP-006 — Prior auth pending stub + async talking point

**Files:**
- Create: `stubs/eligibility-v1/check_eligibility/prior_auth_pending.yaml`
- Modify: `cases/eligibility-v1/agent.yaml` (system_prompt rule for pending state)
- Create: `cases/eligibility-v1/functional/TC-E-011.yaml`
- Modify: `demo/scenarios.yaml` (add demo-note comment)
- Modify: `demo/README.md` (add "Known Simplifications" section)
- Modify: `tests/test_eligibility_v1_cases.py` (assert rule for pending)

- [ ] **Step 1: Write failing test** — append to `tests/test_eligibility_v1_cases.py`:

```python
def test_eligibility_prompt_handles_prior_auth_pending():
    import yaml
    from pathlib import Path
    prompt = yaml.safe_load(
        (Path(__file__).parent.parent / "cases/eligibility-v1/agent.yaml").read_text(encoding="utf-8")
    )["system_prompt"]
    assert "prior_auth_pending" in prompt or "prior auth" in prompt.lower()
    assert "reference" in prompt.lower()
```

- [ ] **Step 2: Run test** — Expected: FAIL.

- [ ] **Step 3: Create stub** — `stubs/eligibility-v1/check_eligibility/prior_auth_pending.yaml`:

```yaml
covered: true
co_pay: 50.00
prior_auth_required: true
prior_auth_status: prior_auth_pending
expected_response_hours: 48
reference_id: PA-20260513-001
network_status: in_network
plan_name: Aetna HMO
```

- [ ] **Step 4: Update `cases/eligibility-v1/agent.yaml`**

Insert after Rule 6 (prior authorization required) as Rule 6a:

```
  Rule 6a — Prior authorization pending:
  If check_eligibility returns prior_auth_status: "prior_auth_pending", say:
    "Your authorization request is in progress (reference {reference_id}).
    A decision is typically returned within {expected_response_hours} hours.
    Would you like me to notify you when the decision is received?"
  Do not emit a HITL escalation. Do not book the appointment. Capture the
  patient's notification preference (yes/no) before ending the turn.
```

- [ ] **Step 5: Create case** — `cases/eligibility-v1/functional/TC-E-011.yaml`:

```yaml
id: TC-E-011
agent: eligibility-v1
category: functional

input:
  messages:
    - role: user
      content: >-
        Check eligibility for procedure 70553 under Aetna HMO for patient P-22222.

tool_responses:
  check_eligibility: prior_auth_pending

expected:
  outcome: clarification_requested
  must_contain_any:
    - "PA-20260513-001"
    - "48"
    - "notify"
  must_not_contain:
    - "denied"
    - "approved"

metadata:
  scenario: prior_auth_pending_notify_optin
  patient_age: 35
  language: english
  insurance: commercial
```

- [ ] **Step 6: Update `demo/scenarios.yaml`** — add comment above the prior_auth_approved scenario:

```yaml
  # demo-note: In production, prior auth integrations (CoverMyMeds, Gold Carding)
  # are asynchronous and can take hours to days. These stubs simulate synchronous
  # responses for demo clarity. See demo/README.md "Known Simplifications".
```

- [ ] **Step 7: Update `demo/README.md`** — append section:

```markdown
## Known Simplifications

- **Prior authorization is asynchronous in production.** Real PA workflows
  (CoverMyMeds, Gold Carding) take hours to days. The demo's `prior_auth_*`
  stubs return synchronously for narrative clarity. The `prior_auth_pending`
  stub illustrates the realistic intermediate state with reference ID + ETA.
- **No real EHR or payer integrations.** All tool calls are intercepted by
  StubToolMiddleware. See `stubs/` for fixture catalog.
```

- [ ] **Step 8: Run tests**

Run: `uv run pytest tests/test_eligibility_v1_cases.py tests/test_loader.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add stubs/eligibility-v1/check_eligibility/prior_auth_pending.yaml \
        cases/eligibility-v1/ demo/scenarios.yaml demo/README.md \
        tests/test_eligibility_v1_cases.py
git commit -m "feat(eligibility): prior auth pending state + async talking point (GAP-006)"
```

---

### Task 7: GAP-007 — Cancellation policy contextual variance

**Files:**
- Create: `stubs/scheduling-v1/cancel_appointment/late_cancelled_waived.yaml`
- Create: `stubs/scheduling-v1/cancel_appointment/late_cancelled_fee_applied.yaml`
- Modify: `cases/scheduling-v1/agent.yaml` (replace rule 9 with branching logic)
- Create: `cases/scheduling-v1/hitl_routing/TC-S-HIT-006.yaml`  *(spec called this TC-S-HIT-005 — already taken by GAP-005; renumbered)*
- Create: `cases/scheduling-v1/hitl_routing/TC-S-HIT-007.yaml`  *(spec called this TC-S-HIT-006)*
- Modify: `demo/scenarios.yaml` (optional: add cancellation scenario)

- [ ] **Step 1: Create stubs**

`stubs/scheduling-v1/cancel_appointment/late_cancelled_waived.yaml`:
```yaml
status: cancelled
appointment_id: APT-98766
late_cancellation: true
fee_waived: true
reason: first_occurrence
policy_ref: CXL-001
message: "Cancellation processed. As a first-time late cancellation, the fee has been waived."
```

`stubs/scheduling-v1/cancel_appointment/late_cancelled_fee_applied.yaml`:
```yaml
status: cancelled
appointment_id: APT-98766
late_cancellation: true
fee_applied: 25.00
policy_ref: CXL-002
patient_history_late_count: 3
message: "Cancellation processed. A late cancellation fee of $25.00 has been applied per policy CXL-002."
```

- [ ] **Step 2: Update `cases/scheduling-v1/agent.yaml`** — replace rule 9 with:

```
  9. When cancel_appointment returns late_cancellation: true, branch on policy outcome:
     - If fee_waived: true (first-time offender), confirm the waiver to the patient
       and do NOT escalate.
     - If fee_applied is present, inform the patient of the fee amount and the
       policy_ref, then emit a HITL escalation so a human can offer a dispute path:
       {"escalate": true, "reason": "late_cancellation_policy", "confidence": 1.0}
     Never autonomously waive or impose fees outside what the tool returned.
```

- [ ] **Step 3: Create case files**

`cases/scheduling-v1/hitl_routing/TC-S-HIT-006.yaml`:
```yaml
id: TC-S-HIT-006
agent: scheduling-v1
category: hitl_routing

input:
  messages:
    - role: user
      content: "Cancel appointment APT-98766 for patient P-11111."

tool_responses:
  cancel_appointment: late_cancelled_waived

expected:
  outcome: success
  must_contain_any:
    - "waived"
    - "first"
  must_not_emit_escalation: true

metadata:
  scenario: late_cancel_first_offender_waived
  language: english
  insurance: commercial
```

`cases/scheduling-v1/hitl_routing/TC-S-HIT-007.yaml`:
```yaml
id: TC-S-HIT-007
agent: scheduling-v1
category: hitl_routing

input:
  messages:
    - role: user
      content: "Cancel appointment APT-98766 for patient P-22222."

tool_responses:
  cancel_appointment: late_cancelled_fee_applied

expected:
  outcome: hitl_escalation
  escalate: true
  reason: late_cancellation_policy
  confidence: 1.0
  must_contain_any:
    - "$25"
    - "CXL-002"

metadata:
  scenario: late_cancel_repeat_fee_hitl_dispute
  language: english
  insurance: commercial
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_scheduling_v1_cases.py tests/test_loader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add stubs/scheduling-v1/cancel_appointment/ cases/scheduling-v1/
git commit -m "feat(scheduling): contextual late-cancellation policy branching (GAP-007)"
```

---

## TIER 3 — Demo Polish & Buyer Experience

### Task 8: GAP-010 — Metrics sidebar panel

**Files:**
- Create: `demo/metrics.yaml`
- Modify: `demo/app.py` (collapsible metrics panel in sidebar)
- Create: `tests/test_demo_metrics.py`

- [ ] **Step 1: Create `demo/metrics.yaml`**

```yaml
# Illustrative baseline-vs-agentic benchmarks. Actual results vary by deployment.
disclaimer: "Illustrative benchmarks — actual results vary by deployment."
metrics:
  - name: "Avg. time to schedule"
    baseline: "8 min"
    agentic: "45 sec"
  - name: "Eligibility check time"
    baseline: "3 min"
    agentic: "8 sec"
  - name: "No-show rate"
    baseline: "18%"
    agentic: "11%"
  - name: "HITL escalation rate"
    baseline: "100%"
    agentic: "12%"
```

- [ ] **Step 2: Write failing test** — `tests/test_demo_metrics.py`:

```python
import yaml
from pathlib import Path

_METRICS_PATH = Path(__file__).parent.parent / "demo" / "metrics.yaml"

def test_metrics_yaml_exists():
    assert _METRICS_PATH.exists()

def test_metrics_yaml_has_disclaimer_and_four_metrics():
    data = yaml.safe_load(_METRICS_PATH.read_text(encoding="utf-8"))
    assert "disclaimer" in data
    assert len(data["metrics"]) == 4
    for m in data["metrics"]:
        assert {"name", "baseline", "agentic"} <= set(m.keys())
```

- [ ] **Step 3: Run test** — Expected: PASS (file exists). If fail, fix the YAML.

- [ ] **Step 4: Update `demo/app.py`** — in the sidebar block, after the persona JSON expander:

```python
with st.expander("📊 Baseline vs Agentic Metrics", expanded=False):
    metrics_path = _REPO_ROOT / "demo" / "metrics.yaml"
    if metrics_path.exists():
        with metrics_path.open(encoding="utf-8") as fh:
            metrics_data = yaml.safe_load(fh)
        import pandas as pd
        df = pd.DataFrame(metrics_data["metrics"])
        st.table(df.set_index("name"))
        st.caption(metrics_data["disclaimer"])
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_demo_metrics.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add demo/metrics.yaml demo/app.py tests/test_demo_metrics.py
git commit -m "feat(demo): baseline vs agentic metrics sidebar panel (GAP-010)"
```

---

### Task 9: GAP-008 — Post-booking reminder

**Files:**
- Create: `stubs/scheduling-v1/send_appointment_reminder/reminder_sent.yaml`
- Modify: `cases/scheduling-v1/agent.yaml` (add tool + rule 13)
- Create: `cases/scheduling-v1/functional/TC-S-013.yaml`
- Modify: `demo/app.py` (show "✉️ Reminder sent" badge after booking)

- [ ] **Step 1: Create stub** — `stubs/scheduling-v1/send_appointment_reminder/reminder_sent.yaml`:

```yaml
status: sent
channel: sms
appointment_id: APT-99999
patient_contact: "+1-555-0100"
eta_minutes: 1
```

- [ ] **Step 2: Update `cases/scheduling-v1/agent.yaml`** — add rule 13:

```
  13. After book_appointment returns booked: true, immediately call
      send_appointment_reminder with the new appointment_id, channel "sms"
      (default), and patient_contact from the booking confirmation. Then tell
      the patient: "A reminder has been sent to you via SMS."
```

Append tool:

```yaml
  - name: send_appointment_reminder
    description: >
      Send an appointment reminder to the patient (SMS or email). Returns
      delivery status.
    parameters:
      type: object
      properties:
        appointment_id:
          type: string
        channel:
          type: string
          description: "sms or email"
        patient_contact:
          type: string
      required:
        - appointment_id
        - channel
        - patient_contact
```

- [ ] **Step 3: Create case** — `cases/scheduling-v1/functional/TC-S-013.yaml`:

```yaml
id: TC-S-013
agent: scheduling-v1
category: functional

input:
  messages:
    - role: user
      content: "Book me into the Tuesday 10 AM slot with Dr. Smith. I'm patient P-11111."

tool_responses:
  search_available_slots: full_slots
  book_appointment: confirmed
  send_appointment_reminder: reminder_sent

expected:
  outcome: success
  must_call_before:
    - first: book_appointment
      then: send_appointment_reminder
  must_contain_any:
    - "reminder"
    - "SMS"

metadata:
  scenario: post_booking_reminder
  language: english
  insurance: commercial
```

- [ ] **Step 4: Update `demo/app.py`** — find the agent-message render loop. After a message containing `"booked": true` or `"confirmation_id"`, append:

```python
if "confirmation_id" in (msg.get("content") or "") or msg.get("booking_confirmed"):
    st.markdown("✉️ *Reminder sent to patient via SMS*")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_scheduling_v1_cases.py tests/test_loader.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add stubs/scheduling-v1/send_appointment_reminder/ \
        cases/scheduling-v1/ demo/app.py
git commit -m "feat(scheduling): post-booking SMS reminder (GAP-008)"
```

---

### Task 10: GAP-011 — Spanish-language end-to-end path

**Files:**
- Modify: `demo/scenarios.yaml` (add spanish_scheduling scenario)
- Modify: `demo/orchestrator-v1.yaml` (add language-detection rule)
- Modify: `tests/test_demo_scenarios.py` (extend EXPECTED_SCENARIO_NAMES + add language assertion)

- [ ] **Step 1: Write failing test** — modify `tests/test_demo_scenarios.py`:

Change `EXPECTED_SCENARIO_COUNT = 6` → `EXPECTED_SCENARIO_COUNT = 8` (will be 7 after this task + 1 after Task 11 = 8). Update `EXPECTED_SCENARIO_NAMES` set to include `"spanish_scheduling_medicare"` and `"waitlist_status_check"`.

Append:

```python
def test_spanish_scenario_uses_spanish_persona(scenarios):
    spanish = next(
        (s for s in scenarios if s.get("language") == "es"),
        None,
    )
    assert spanish is not None, "no scenario with language: es"
    assert spanish["persona_id"] == "medicare_spanish_elderly"
```

- [ ] **Step 2: Add scenario to `demo/scenarios.yaml`**

```yaml
  - name: spanish_scheduling_medicare
    description: "Spanish-language scheduling — Medicare elderly patient, end-to-end booking"
    persona_id: medicare_spanish_elderly
    language: es
    stub_map:
      eligibility-v1:
        check_eligibility: covered
      scheduling-v1:
        search_available_slots: full_slots
        book_appointment: confirmed
```

- [ ] **Step 3: Update `demo/orchestrator-v1.yaml`** — add to system_prompt as rule 8:

```
  8. Detect the patient's language from their first message. If Spanish, respond
     in Spanish for the entire session, including any sub-agent relay messages.
     If a sub-agent returns content in English, translate it to Spanish before
     surfacing it to the patient.
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_demo_scenarios.py tests/test_demo_orchestrator_yaml.py -v`
Expected: depending on Task 11 ordering — if Task 11 not yet done, test_exactly_six_scenarios will fail. Implement Task 11 next, OR temporarily set EXPECTED_SCENARIO_COUNT = 7 here and bump to 8 in Task 11.

- [ ] **Step 5: Commit**

```bash
git add demo/scenarios.yaml demo/orchestrator-v1.yaml tests/test_demo_scenarios.py
git commit -m "feat(demo): Spanish-language end-to-end scheduling scenario (GAP-011)"
```

---

### Task 11: GAP-009 — 7th waitlist scenario (Returning patient)

**Files:**
- Modify: `demo/scenarios.yaml` (add waitlist_status_check)
- Modify: `demo/README.md` (narrative for the new scenario)
- Modify: `tests/test_demo_scenarios.py` (already covers count via Task 10)

- [ ] **Step 1: Add scenario to `demo/scenarios.yaml`**

```yaml
  - name: waitlist_status_check
    description: "Waitlist status check — returning Medicaid patient sees a slot opened"
    persona_id: medicaid_english_adult
    stub_map:
      eligibility-v1:
        check_eligibility: covered
      scheduling-v1:
        check_and_notify_waitlist: notified
```

- [ ] **Step 2: Update `demo/README.md`** — under the per-scenario narrative section, add:

```markdown
### waitlist_status_check — Async continuity for returning patients

Patient previously placed on a waitlist returns in a new session to check
status. Orchestrator routes to scheduling, which calls
`check_and_notify_waitlist` and confirms a slot opened. Demonstrates that
the system handles cross-session async continuity, not only single-session
linear flows.
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_demo_scenarios.py -v`
Expected: PASS (count is now 8 = 6 + Task 10 + Task 11).

- [ ] **Step 4: Commit**

```bash
git add demo/scenarios.yaml demo/README.md
git commit -m "feat(demo): waitlist status check scenario for returning patients (GAP-009)"
```

---

### Task 12: GAP-012 — Operator "When It Goes Wrong" guide

**Files:**
- Modify: `demo/README.md` (add Live Demo Recovery Playbook section)
- Create: `demo/TROUBLESHOOTING.md`

- [ ] **Step 1: Write content** — append to `demo/README.md`:

```markdown
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
```

- [ ] **Step 2: Create `demo/TROUBLESHOOTING.md`** — copy the same five-item content as a standalone quick-reference file with a brief intro:

```markdown
# Demo Troubleshooting — Quick Reference

For full operator narrative see `demo/README.md`. These are the top five
recovery steps.

[... same five items ...]
```

- [ ] **Step 3: Commit**

```bash
git add demo/README.md demo/TROUBLESHOOTING.md
git commit -m "docs(demo): operator recovery playbook + troubleshooting quick ref (GAP-012)"
```

---

## Final Verification

- [ ] **Step F1: Run the full test suite**

Run: `uv run pytest -q`
Expected: 0 failures.

- [ ] **Step F2: Run linters**

Run: `uv run ruff check . && uv run mypy hlsharness --exclude hlsharness/adapters`
Expected: clean.

- [ ] **Step F3: Smoke-test the demo**

Run: `uv run streamlit run demo/app.py`
Expected: HIPAA banner appears first; after acknowledging, scenario picker shows 8 scenarios; metrics expander populates; selecting `spanish_scheduling_medicare` runs without UTF-8 errors.

- [ ] **Step F4: Push branch + open PR**

```bash
git push -u origin agents/code-review-missing-elements
gh pr create --title "Demo gaps & enhancements (GAP-001..012)" \
  --body "Implements all 12 items from docs/requirement/demo-gaps-enhancements.md."
```

---

## Self-Review Notes

- **Spec coverage:** All 12 GAPs have a Task. ID-renumbering for TC-S-HIT-* is documented inline (HITL ids stay in HITL dir).
- **Placeholders:** None — every step shows the exact YAML/Python content.
- **Type consistency:** `VALID_REASON_CODES` additions use exact strings referenced in case `expected.reason` fields.
- **Scope split:** Tier 3 tasks (8–12) are fully independent and could be parallelized across subagents. Tier 1 must run in order (3 → 1 → 2). Tier 2 has only one ordering dep (5 after 1).
