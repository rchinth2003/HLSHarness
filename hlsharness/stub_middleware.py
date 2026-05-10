"""StubToolMiddleware — intercepts MAF tool calls with scripted responses.

Used by EvalController to run MAF agents against deterministic scripted
tool responses per test case, without hitting real backends.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware

# Set by EvalController before each agent.run(); cleared after via token.reset().
_stub_responses: ContextVar[dict[str, Any] | None] = ContextVar("_stub_responses", default=None)


class UnknownToolError(Exception):
    """Raised when the agent calls a tool with no scripted response in the active case."""


@dataclass
class ToolCallEntry:
    """A single intercepted tool invocation recorded by StubToolMiddleware."""

    tool_name: str
    arguments: dict[str, Any]
    response: Any


class StubToolMiddleware(FunctionMiddleware):
    """Intercepts every MAF tool call; returns scripted response from _stub_responses.

    EvalController sets ``_stub_responses`` to ``case.tool_responses`` before
    calling ``agent.run()``, then reads ``middleware.trajectory`` after.
    The middleware never calls the real tool function — it short-circuits by
    setting ``context.result`` and returning without calling ``call_next()``.

    Raises ``UnknownToolError`` if the agent calls a tool not present in the
    active scripted responses dict, mirroring the legacy ``ToolSimulator`` behaviour.
    """

    def __init__(self) -> None:
        self.trajectory: list[ToolCallEntry] = []

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Any,
    ) -> None:
        responses = _stub_responses.get() or {}
        tool_name = context.function.name

        if tool_name not in responses:
            raise UnknownToolError(
                f"Agent called '{tool_name}' but no scripted response exists for it. "
                f"Available: {sorted(responses.keys())}"
            )

        context.result = responses[tool_name]
        self.trajectory.append(
            ToolCallEntry(
                tool_name=tool_name,
                arguments=dict(context.arguments or {}),
                response=context.result,
            )
        )
        # Do NOT call call_next() — real function is never executed.
