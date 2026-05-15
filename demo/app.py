"""Patient Scheduling Demo — Streamlit chat UI.

Sidebar: scenario + persona picker.
Left panel: patient chat (multi-turn).
Right panel: live agent trace with collapsible per-turn TraceEvent list.
Amber banner for HITL escalation signals.

Launch:
    streamlit run demo/app.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st
import yaml
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(_REPO_ROOT / ".env")  # no-op if .env doesn't exist

from demo.runner import DemoRunner, TurnResult  # noqa: E402

# ------------------------------------------------------------------ page config

st.set_page_config(
    page_title="Patient Scheduling Demo",
    page_icon="🏥",
    layout="wide",
)

# ------------------------------------------------------------------ load scenarios


@st.cache_data
def _load_scenarios() -> list[dict]:
    scenarios_path = _REPO_ROOT / "demo" / "scenarios.yaml"
    with scenarios_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data["scenarios"]


@st.cache_data
def _load_persona(persona_id: str) -> dict:
    persona_path = _REPO_ROOT / "personas" / f"{persona_id}.yaml"
    with persona_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


scenarios = _load_scenarios()
scenario_names = [sc["name"] for sc in scenarios]
scenario_descriptions = {sc["name"]: sc.get("description", sc["name"]) for sc in scenarios}

# ------------------------------------------------------------------ sidebar

with st.sidebar:
    st.title("Patient Scheduling Demo")
    st.markdown("---")

    selected_name = st.selectbox(
        "Scenario",
        scenario_names,
        format_func=lambda n: scenario_descriptions.get(n, n),
    )
    selected_scenario = next(sc for sc in scenarios if sc["name"] == selected_name)
    persona_id = selected_scenario["persona_id"]
    persona = _load_persona(persona_id)

    st.markdown("**Persona**")
    st.json(persona, expanded=False)

    if st.button("Reset conversation", use_container_width=True):
        st.session_state.pop("runner", None)
        st.session_state.pop("messages", None)
        st.session_state.pop("trace_log", None)
        st.session_state.pop("consent_acknowledged", None)
        st.session_state.pop("consent_declined", None)
        st.rerun()

# ------------------------------------------------------------------ session state

_runner_key = f"runner_{selected_name}"

if "runner" not in st.session_state or st.session_state.get("_scenario") != selected_name:
    st.session_state["runner"] = DemoRunner(selected_name, repo_root=_REPO_ROOT)
    st.session_state["messages"]: list[dict] = []
    st.session_state["trace_log"]: list[TurnResult] = []
    st.session_state["_scenario"] = selected_name
    st.session_state["consent_acknowledged"] = False
    st.session_state["consent_declined"] = False

runner: DemoRunner = st.session_state["runner"]
messages: list[dict] = st.session_state["messages"]
trace_log: list[TurnResult] = st.session_state["trace_log"]

# ------------------------------------------------------------------ HIPAA consent banner

if "consent_acknowledged" not in st.session_state:
    st.session_state.consent_acknowledged = False

# Dual-gate design: UI blocks input until acknowledged; Rule 0 adds a second LLM-level gate
# for harness-level testing (TC-O-006) that bypasses the UI.
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
            st.session_state["consent_declined"] = True
            st.rerun()
    st.stop()

if st.session_state.get("consent_declined"):
    st.error(
        "Session ended. Without acknowledgment we cannot collect "
        "scheduling information. Use **Reset conversation** in the "
        "sidebar to start a new session."
    )
    st.stop()

# ------------------------------------------------------------------ layout

chat_col, trace_col = st.columns([3, 2])

# ------------------------------------------------------------------ chat panel

with chat_col:
    st.subheader("Patient Chat")

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Type a patient message…"):
        messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Orchestrator thinking…"):
                result: TurnResult = asyncio.run(runner.run_turn(prompt))

            trace_log.append(result)
            messages.append({"role": "assistant", "content": result.orchestrator_reply})
            st.markdown(result.orchestrator_reply)

            # Check if send_appointment_reminder was called in this turn
            reminder_sent = any(
                event.tool_name == "send_appointment_reminder" for event in result.trace_events
            )
            if reminder_sent:
                st.markdown("✉️ *Reminder sent to patient via SMS*")

            # Check if triage-v1 was called in this turn
            triage_called = any(event.sub_agent == "triage-v1" for event in result.trace_events)
            # Keep in sync with cases/triage-v1/agent.yaml mandatory disclaimer section
            DISCLAIMER_FRAGMENT = "not a medical diagnosis"
            if triage_called and DISCLAIMER_FRAGMENT.lower() not in result.orchestrator_reply.lower():
                st.markdown(
                    '<div style="color:#6b7280; font-style:italic; font-size:0.85em; '
                    'border-left: 2px solid #d1d5db; padding-left: 8px; margin-top: 4px;">'
                    'This triage is for scheduling prioritization only and is not a medical '
                    'diagnosis. Please consult a licensed clinician for medical advice.'
                    '</div>',
                    unsafe_allow_html=True,
                )

            if result.hitl_signal:
                st.warning(
                    f"**HITL Escalation** — reason: "
                    f"`{result.hitl_signal.get('reason', 'unknown')}`  "
                    f"confidence: `{result.hitl_signal.get('confidence', '?')}`",
                    icon="⚠️",
                )

# ------------------------------------------------------------------ trace panel

with trace_col:
    st.subheader("Agent Trace")

    if not trace_log:
        st.info("No turns yet — send a message to begin.")
    else:
        for turn_idx, turn_result in enumerate(trace_log, start=1):
            with st.expander(f"Turn {turn_idx}", expanded=(turn_idx == len(trace_log))):
                if turn_result.hitl_signal:
                    st.warning(
                        f"HITL: `{turn_result.hitl_signal.get('reason', 'unknown')}`",
                        icon="⚠️",
                    )

                if not turn_result.trace_events:
                    st.caption("No sub-agent calls this turn.")
                else:
                    for event in turn_result.trace_events:
                        st.markdown(f"**Sub-agent:** `{event.sub_agent}`")
                        if event.tool_name:
                            st.markdown(f"**Tool:** `{event.tool_name}`")
                        if event.fixture_name:
                            st.markdown(f"**Fixture:** `{event.fixture_name}`")
                        if event.stub_response is not None:
                            st.json(event.stub_response, expanded=False)
                        if event.hitl_signal:
                            st.warning(
                                f"Sub-agent HITL: `{event.hitl_signal.get('reason', 'unknown')}`",
                                icon="⚠️",
                            )
                        st.markdown("---")
