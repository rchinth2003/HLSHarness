"""
Spike: Validate StubToolMiddleware ContextVar intercept with Microsoft Agent Framework.

PURPOSE
-------
Prove (or disprove) that FunctionMiddleware can:
  1. Intercept a tool call before the real function executes
  2. Short-circuit the call by setting context.result and not calling call_next()
  3. Read a ContextVar set by the test harness before agent.run()
  4. Record trajectory entries readable after agent.run() completes (pull model)
  5. Isolate ContextVar state between sequential case runs (no bleed-through)

SETUP
-----
    uv sync --group spike
    export AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
    export AZURE_OPENAI_DEPLOYMENT_AGENT=<your-gpt-deployment>
    az login   # DefaultAzureCredential — no API key needed

RUN
---
    uv run python spike/maf_stub_middleware_spike.py

All five hypotheses print PASS or FAIL with evidence.
"""

from __future__ import annotations

import asyncio
import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# ---------------------------------------------------------------------------
# ContextVar that EvalController will set per case
# ---------------------------------------------------------------------------

_stub_responses: ContextVar[dict[str, Any]] = ContextVar("_stub_responses", default={})


# ---------------------------------------------------------------------------
# Trajectory entry — mirrors what EvalController will read after agent.run()
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    response: Any


# ---------------------------------------------------------------------------
# StubToolMiddleware — the proposed production design
# ---------------------------------------------------------------------------

from agent_framework import FunctionMiddleware, FunctionInvocationContext  # noqa: E402


class StubToolMiddleware(FunctionMiddleware):
    """Intercepts every tool call; returns scripted response from ContextVar."""

    def __init__(self) -> None:
        self.trajectory: list[ToolCall] = []

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Any,
    ) -> None:
        responses = _stub_responses.get()
        tool_name = context.function.name

        if tool_name in responses:
            # Short-circuit: return scripted response without calling real function
            context.result = responses[tool_name]
            self.trajectory.append(
                ToolCall(
                    tool_name=tool_name,
                    arguments=dict(context.arguments or {}),
                    response=context.result,
                )
            )
            return  # Do NOT call call_next()

        # Unknown tool — let it run (will likely fail; surface clearly)
        await call_next()
        self.trajectory.append(
            ToolCall(
                tool_name=tool_name,
                arguments=dict(context.arguments or {}),
                response=context.result,
            )
        )


# ---------------------------------------------------------------------------
# Minimal agent with one tool
# ---------------------------------------------------------------------------

from agent_framework import Agent, tool  # noqa: E402
from agent_framework.openai import AzureOpenAIChatClient  # noqa: E402


@tool
def search_available_slots(provider_id: str, date: str) -> dict[str, Any]:  # type: ignore[return]
    """Search available appointment slots for a provider on a given date."""
    # This should NEVER be called in the spike — middleware short-circuits it
    raise RuntimeError("FAIL: real tool function was called — middleware did not intercept")


def build_agent(middleware: StubToolMiddleware) -> Agent:
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAIChatClient(
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_AGENT"],
        azure_ad_token_provider=token_provider,
    )
    return Agent(
        client=client,
        name="SchedulingAgent",
        instructions=(
            "You are a scheduling assistant. "
            "When asked to find appointment slots, always call search_available_slots."
        ),
        tools=[search_available_slots],
        middleware=[middleware],
    )


# ---------------------------------------------------------------------------
# Spike assertions
# ---------------------------------------------------------------------------

async def run_spike() -> None:
    print("\n=== MAF StubToolMiddleware Spike ===\n")
    results: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Hypothesis 1: Middleware intercepts the tool call before real function
    # Hypothesis 2: Short-circuit works (real function raises RuntimeError if called)
    # ------------------------------------------------------------------
    print("H1+H2: Middleware intercepts and short-circuits tool call...")
    middleware = StubToolMiddleware()
    agent = build_agent(middleware)

    case_responses = {
        "search_available_slots": {
            "slots": [{"id": "slot-001", "date": "2026-05-18", "time": "10:00 AM"}]
        }
    }
    token = _stub_responses.set(case_responses)

    try:
        response = await agent.run(
            "Find me an appointment with provider P123 on 2026-05-18"
        )
        # If we got here, no RuntimeError — middleware intercepted successfully
        results["H1_intercept"] = True
        results["H2_short_circuit"] = True
        print(f"  Agent response: {response.text[:120]}...")
        print("  PASS: real tool function was NOT called")
    except RuntimeError as e:
        results["H1_intercept"] = False
        results["H2_short_circuit"] = False
        print(f"  FAIL: {e}")
    finally:
        _stub_responses.reset(token)

    # ------------------------------------------------------------------
    # Hypothesis 3: ContextVar is readable inside middleware
    # (proven if H1+H2 passed — middleware read _stub_responses.get())
    # ------------------------------------------------------------------
    results["H3_contextvar"] = results.get("H1_intercept", False)
    status = "PASS" if results["H3_contextvar"] else "FAIL"
    print(f"\nH3: ContextVar readable inside middleware... {status}")

    # ------------------------------------------------------------------
    # Hypothesis 4: Trajectory readable after agent.run() (pull model)
    # ------------------------------------------------------------------
    print("\nH4: Trajectory recorded and readable after run...")
    if middleware.trajectory:
        entry = middleware.trajectory[0]
        print(f"  Captured: tool={entry.tool_name}, response={entry.response}")
        results["H4_trajectory"] = entry.tool_name == "search_available_slots"
        status = "PASS" if results["H4_trajectory"] else "FAIL"
        print(f"  {status}")
    else:
        results["H4_trajectory"] = False
        print("  FAIL: trajectory list is empty")

    # ------------------------------------------------------------------
    # Hypothesis 5: ContextVar isolation between sequential case runs
    # ------------------------------------------------------------------
    print("\nH5: ContextVar isolation between sequential case runs...")
    middleware2 = StubToolMiddleware()
    agent2 = build_agent(middleware2)

    # Case A: slots available
    case_a = {"search_available_slots": {"slots": [{"id": "slot-A"}]}}
    token_a = _stub_responses.set(case_a)
    await agent2.run("Find slots for provider P-A on 2026-05-19")
    _stub_responses.reset(token_a)

    # Case B: no availability — different scripted response
    case_b = {"search_available_slots": {"slots": []}}
    token_b = _stub_responses.set(case_b)
    middleware2.trajectory.clear()  # reset between cases
    await agent2.run("Find slots for provider P-B on 2026-05-20")
    _stub_responses.reset(token_b)

    if middleware2.trajectory:
        last_response = middleware2.trajectory[-1].response
        isolated = last_response == {"slots": []}
        results["H5_isolation"] = isolated
        status = "PASS" if isolated else "FAIL"
        print(f"  Case B response: {last_response}")
        print(f"  {status}: response is case-B scripted value, not case-A bleed-through")
    else:
        results["H5_isolation"] = False
        print("  FAIL: no trajectory entries for case B")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n=== Results ===")
    all_pass = all(results.values())
    for name, passed in results.items():
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}: {'PASS' if passed else 'FAIL'}")

    print(
        f"\n{'ALL HYPOTHESES CONFIRMED — proceed to Slice 15B' if all_pass else 'FAILURES DETECTED — review alternative approach before proceeding'}"
    )

    if not all_pass:
        print("\nNext steps if failures:")
        print("  - H1/H2 fail: FunctionMiddleware API may differ — check agent_framework version")
        print("  - H3 fails:   ContextVar not propagated into middleware coroutine — try threading.local")
        print("  - H4 fails:   context.result not set before return — check FunctionInvocationContext API")
        print("  - H5 fails:   ContextVar bleeds across runs — use token.reset() pattern consistently")
        print("\nDocument findings in a comment on GitHub issue #55 before starting Slice 15B.")


if __name__ == "__main__":
    missing = [
        v for v in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_AGENT")
        if not os.environ.get(v)
    ]
    if missing:
        print(f"ERROR: missing environment variables: {', '.join(missing)}")
        print("Set these in your shell or .env file. Auth uses az login — no API key needed.")
        raise SystemExit(1)

    asyncio.run(run_spike())
