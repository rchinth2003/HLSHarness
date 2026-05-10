"""Tests for StubToolMiddleware — no Azure credentials required.

Tests use fake FunctionInvocationContext objects to drive the middleware
directly, without a live MAF agent or LLM call.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from agent_framework import FunctionInvocationContext, FunctionTool  # type: ignore[import-untyped]

from hlsharness.stub_middleware import (
    StubToolMiddleware,
    ToolCallEntry,
    UnknownToolError,
    _stub_responses,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str) -> FunctionTool:
    """Create a minimal FunctionTool for use in FunctionInvocationContext."""

    async def _stub(**_kwargs: Any) -> Any:
        return {}

    return FunctionTool(name=name, description="test tool", func=_stub)


def _make_context(
    tool_name: str, arguments: dict[str, Any] | None = None
) -> FunctionInvocationContext:
    """Create a FunctionInvocationContext for the given tool name."""
    return FunctionInvocationContext(
        function=_make_tool(tool_name),
        arguments=arguments or {},
    )


async def _process(middleware: StubToolMiddleware, context: FunctionInvocationContext) -> None:
    """Drive middleware.process() with a no-op call_next."""
    await middleware.process(context, call_next=AsyncMock())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_scripted_response_returned():
    """Middleware sets context.result to the scripted response."""
    middleware = StubToolMiddleware()
    ctx = _make_context("search_available_slots", {"provider_id": "P1", "date": "2026-05-18"})
    scripted = {"slots": [{"id": "slot-001"}]}

    token = _stub_responses.set({"search_available_slots": scripted})
    try:
        asyncio.run(_process(middleware, ctx))
    finally:
        _stub_responses.reset(token)

    assert ctx.result == scripted


def test_unknown_tool_raises():
    """Middleware raises UnknownToolError when tool not in scripted responses."""
    middleware = StubToolMiddleware()
    ctx = _make_context("nonexistent_tool")

    token = _stub_responses.set({"search_available_slots": {}})
    try:
        with pytest.raises(UnknownToolError, match="nonexistent_tool"):
            asyncio.run(_process(middleware, ctx))
    finally:
        _stub_responses.reset(token)


def test_trajectory_recorded():
    """Middleware appends a ToolCallEntry to trajectory after interception."""
    middleware = StubToolMiddleware()
    args = {"provider_id": "P1", "date": "2026-05-18"}
    ctx = _make_context("search_available_slots", args)
    scripted = {"slots": []}

    token = _stub_responses.set({"search_available_slots": scripted})
    try:
        asyncio.run(_process(middleware, ctx))
    finally:
        _stub_responses.reset(token)

    assert len(middleware.trajectory) == 1
    entry = middleware.trajectory[0]
    assert isinstance(entry, ToolCallEntry)
    assert entry.tool_name == "search_available_slots"
    assert entry.response == scripted


def test_real_function_not_called():
    """call_next is never invoked when tool has a scripted response."""
    middleware = StubToolMiddleware()
    ctx = _make_context("search_available_slots")
    call_next = AsyncMock()

    token = _stub_responses.set({"search_available_slots": {}})
    try:
        asyncio.run(middleware.process(ctx, call_next))
    finally:
        _stub_responses.reset(token)

    call_next.assert_not_awaited()


def test_contextvar_isolation_between_sequential_runs():
    """ContextVar resets cleanly between case runs — no bleed-through."""
    middleware = StubToolMiddleware()

    # Case A: slots available
    case_a_response = {"slots": [{"id": "slot-A"}]}
    token_a = _stub_responses.set({"search_available_slots": case_a_response})
    ctx_a = _make_context("search_available_slots")
    asyncio.run(_process(middleware, ctx_a))
    _stub_responses.reset(token_a)

    middleware.trajectory.clear()

    # Case B: no slots — completely different response
    case_b_response = {"slots": []}
    token_b = _stub_responses.set({"search_available_slots": case_b_response})
    ctx_b = _make_context("search_available_slots")
    asyncio.run(_process(middleware, ctx_b))
    _stub_responses.reset(token_b)

    assert len(middleware.trajectory) == 1
    assert middleware.trajectory[0].response == case_b_response, (
        "Case B received case A response — ContextVar bleed-through detected"
    )


def test_multiple_tool_calls_recorded():
    """Multiple tool calls in one run are all appended to trajectory."""
    middleware = StubToolMiddleware()
    scripted = {
        "search_available_slots": {"slots": [{"id": "slot-001"}]},
        "book_appointment": {"confirmation_id": "CONF-001", "status": "confirmed"},
    }

    token = _stub_responses.set(scripted)
    try:
        ctx1 = _make_context("search_available_slots")
        ctx2 = _make_context("book_appointment", {"slot_id": "slot-001", "patient_id": "P1"})
        asyncio.run(_process(middleware, ctx1))
        asyncio.run(_process(middleware, ctx2))
    finally:
        _stub_responses.reset(token)

    assert len(middleware.trajectory) == 2
    assert middleware.trajectory[0].tool_name == "search_available_slots"
    assert middleware.trajectory[1].tool_name == "book_appointment"


def test_empty_scripted_responses_raises_on_any_call():
    """With no scripted responses, any tool call raises UnknownToolError."""
    middleware = StubToolMiddleware()
    ctx = _make_context("search_available_slots")

    token = _stub_responses.set({})
    try:
        with pytest.raises(UnknownToolError):
            asyncio.run(_process(middleware, ctx))
    finally:
        _stub_responses.reset(token)
