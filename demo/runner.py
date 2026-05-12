"""DemoRunner — multi-turn conversation loop for the Patient Scheduling demo.

Loads demo/orchestrator-v1.yaml and demo/scenarios.yaml, manages conversation
history, and dispatches routing tools to real sub-agent LLMs with
StubToolMiddleware injected for sub-agent tool calls.

Azure credentials are resolved lazily on the first run_turn() call — this
module is safe to import and construct without Azure environment variables set.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TraceEvent:
    """A single routing or tool event recorded during a conversation turn."""

    sub_agent: str
    tool_name: str | None
    fixture_name: str | None
    stub_response: Any
    hitl_signal: dict[str, Any] | None = None


@dataclass
class TurnResult:
    """Result of a single conversation turn."""

    orchestrator_reply: str
    trace_events: list[TraceEvent]
    hitl_signal: dict[str, Any] | None


@dataclass
class _Scenario:
    name: str
    description: str
    persona_id: str
    stub_map: dict[str, dict[str, str]]  # agent_name -> {tool_name -> fixture_name}


class DemoRunner:
    """Multi-turn conversation runner for the Patient Scheduling demo.

    Parameters
    ----------
    scenario_name:
        Key from demo/scenarios.yaml (e.g. ``"happy_path_booking"``).
    repo_root:
        Root of the HLSHarness repo. Defaults to the parent of demo/.
    """

    def __init__(
        self,
        scenario_name: str,
        *,
        repo_root: Path | None = None,
    ) -> None:
        self._scenario_name = scenario_name
        self._root = repo_root or Path(__file__).parent.parent
        self._history: list[dict[str, str]] = []
        self._turn_trace: list[TraceEvent] = []
        self._orchestrator: Any = None
        self._scenario: _Scenario | None = None
        self._sub_agent_stubs: dict[str, dict[str, Any]] = {}

    async def run_turn(self, user_message: str) -> TurnResult:
        """Process one patient message and return orchestrator reply plus trace.

        Parameters
        ----------
        user_message:
            The patient's chat message.

        Returns
        -------
        TurnResult
            Contains the orchestrator's reply, per-turn trace events (one per
            sub-agent invocation), and the top-level HITL signal if any.
        """
        await self._ensure_initialized()

        self._history.append({"role": "user", "content": user_message})
        self._turn_trace = []

        response = await self._orchestrator.run(list(self._history))
        reply = response.text or ""
        self._history.append({"role": "assistant", "content": reply})

        hitl = _extract_hitl(reply)
        return TurnResult(
            orchestrator_reply=reply,
            trace_events=list(self._turn_trace),
            hitl_signal=hitl,
        )

    def reset(self) -> None:
        """Clear conversation history for a new session (same scenario)."""
        self._history.clear()

    # ------------------------------------------------------------------ lazy init

    async def _ensure_initialized(self) -> None:
        if self._orchestrator is not None:
            return

        demo_dir = self._root / "demo"
        self._scenario = self._load_scenario(demo_dir)
        self._sub_agent_stubs = self._resolve_stubs(self._scenario)
        self._orchestrator = self._build_orchestrator(demo_dir)

    def _load_scenario(self, demo_dir: Path) -> _Scenario:
        scenarios_path = demo_dir / "scenarios.yaml"
        with scenarios_path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        for sc in data["scenarios"]:
            if sc["name"] == self._scenario_name:
                return _Scenario(
                    name=sc["name"],
                    description=sc.get("description", ""),
                    persona_id=sc["persona_id"],
                    stub_map=sc.get("stub_map") or {},
                )
        raise ValueError(f"Scenario '{self._scenario_name}' not found in scenarios.yaml")

    def _resolve_stubs(self, scenario: _Scenario) -> dict[str, dict[str, Any]]:
        """Load fixture YAML files for each sub-agent listed in the stub_map."""
        resolved: dict[str, dict[str, Any]] = {}
        stubs_root = self._root / "stubs"

        for agent_name, tool_map in scenario.stub_map.items():
            agent_stubs: dict[str, Any] = {}
            for tool_name, fixture_name in tool_map.items():
                fixture_path = stubs_root / agent_name / tool_name / f"{fixture_name}.yaml"
                with fixture_path.open(encoding="utf-8") as fh:
                    agent_stubs[tool_name] = yaml.safe_load(fh)
            resolved[agent_name] = agent_stubs

        return resolved

    def _build_orchestrator(self, demo_dir: Path) -> Any:
        """Build the orchestrator MAF Agent with real routing tool callables."""
        from agent_framework import Agent  # type: ignore[import-untyped]
        from agent_framework.openai import OpenAIChatClient  # type: ignore[import-untyped]
        from azure.identity import DefaultAzureCredential

        orch_yaml_path = demo_dir / "orchestrator-v1.yaml"
        with orch_yaml_path.open(encoding="utf-8") as fh:
            orch_data = yaml.safe_load(fh)

        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_AGENT", "gpt-5.4-pro")

        client = OpenAIChatClient(
            model=deployment,
            azure_endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )

        routing_tools = [self._make_routing_tool(t) for t in orch_data.get("tools", [])]

        return Agent(
            client=client,
            name=orch_data["name"],
            instructions=orch_data["system_prompt"],
            tools=routing_tools,
        )

    _AGENT_MAP: dict[str, str] = {
        "route_to_scheduling": "scheduling-v1",
        "route_to_eligibility": "eligibility-v1",
        "route_to_triage": "triage-v1",
    }

    def _make_routing_tool(self, tool_def: dict[str, Any]) -> Any:
        """Return a FunctionTool whose func invokes the corresponding sub-agent LLM."""
        from agent_framework import FunctionTool  # type: ignore[import-untyped]

        tool_name: str = tool_def["name"]
        sub_agent_name = self._AGENT_MAP.get(tool_name, tool_name)

        async def _call(**kwargs: Any) -> str:
            return await self._invoke_sub_agent(sub_agent_name, tool_name, kwargs)

        return FunctionTool(
            name=tool_name,
            description=tool_def.get("description", ""),
            input_model=tool_def.get("parameters", {}),
            func=_call,
        )

    async def _invoke_sub_agent(
        self,
        agent_name: str,
        routing_tool_name: str,
        kwargs: dict[str, Any],
    ) -> str:
        """Run a sub-agent LLM with StubToolMiddleware and record a TraceEvent."""
        from hlsharness.maf_agent import build_maf_agent, load_agent_yaml
        from hlsharness.stub_middleware import StubToolMiddleware, _stub_responses

        cases_path = self._root / "cases" / agent_name / "agent.yaml"
        sub_yaml = load_agent_yaml(cases_path)

        middleware = StubToolMiddleware()
        sub_agent = build_maf_agent(sub_yaml, middleware)

        stubs = self._sub_agent_stubs.get(agent_name, {})
        msg_content = _build_sub_agent_message(routing_tool_name, kwargs)
        messages: list[dict[str, str]] = [{"role": "user", "content": msg_content}]

        token = _stub_responses.set(stubs)
        try:
            response = await sub_agent.run(messages)  # type: ignore[arg-type]
            reply = response.text or ""
        finally:
            _stub_responses.reset(token)

        tool_entry = middleware.trajectory[-1] if middleware.trajectory else None
        event = TraceEvent(
            sub_agent=agent_name,
            tool_name=tool_entry.tool_name if tool_entry else None,
            fixture_name=_fixture_name_for(agent_name, tool_entry, self._scenario),
            stub_response=tool_entry.response if tool_entry else None,
            hitl_signal=_extract_hitl(reply),
        )
        self._turn_trace.append(event)

        return reply


# ------------------------------------------------------------------ helpers


def _extract_hitl(text: str) -> dict[str, Any] | None:
    """Extract a HITL escalation signal JSON object from agent response text."""
    match = re.search(r'\{[^{}]*"escalate"\s*:\s*true[^{}]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _build_sub_agent_message(routing_tool_name: str, kwargs: dict[str, Any]) -> str:
    """Build a natural-language task message for a sub-agent from routing kwargs."""
    if routing_tool_name == "route_to_triage":
        symptoms = kwargs.get("symptoms", "unspecified symptoms")
        pid = kwargs.get("patient_id", "unknown")
        return f"Patient {pid} reports: {symptoms}"
    if routing_tool_name == "route_to_eligibility":
        pid = kwargs.get("patient_id", "unknown")
        proc = kwargs.get("procedure_code", "PROC-001")
        payer = kwargs.get("payer_id", "PAYER-001")
        return f"Check eligibility for patient {pid}, procedure {proc}, payer {payer}."
    if routing_tool_name == "route_to_scheduling":
        msg = kwargs.get("message")
        if msg:
            return str(msg)
        pid = kwargs.get("patient_id", "unknown")
        intent = kwargs.get("intent", "book")
        return f"Patient {pid} wants to {intent} an appointment."
    return str(kwargs)


def _fixture_name_for(
    agent_name: str,
    tool_entry: Any,
    scenario: _Scenario | None,
) -> str | None:
    """Look up the fixture name from the scenario stub_map for a tool call entry."""
    if tool_entry is None or scenario is None:
        return None
    return scenario.stub_map.get(agent_name, {}).get(tool_entry.tool_name)
