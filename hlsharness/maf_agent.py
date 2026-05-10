"""MafAgent — loads agent.yaml and builds a MAF Agent for local eval.

``agent.yaml`` at ``cases/{agent}/agent.yaml`` is the single source of truth
for an agent's MAF runtime config and eval metadata (via ``x-harness:`` block).
This module reads it, validates it, and produces a MAF ``Agent`` wired with
``StubToolMiddleware`` for deterministic, backend-free evaluation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from agent_framework import Agent, FunctionTool  # type: ignore[import-untyped]
from agent_framework.openai import OpenAIChatClient  # type: ignore[import-untyped]
from azure.identity import DefaultAzureCredential

from hlsharness.stub_middleware import StubToolMiddleware

_REQUIRED_FIELDS = {"name", "description", "system_prompt", "tools", "x-harness"}


class MafAgentYamlError(Exception):
    """Raised when an agent.yaml file fails schema validation."""


@dataclass
class MafToolDef:
    """A tool definition loaded from the agent.yaml ``tools:`` section."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class MafAgentYaml:
    """Parsed contents of a MAF ``agent.yaml`` file.

    Parameters
    ----------
    name:
        Agent identifier (e.g. ``"scheduling-v1"``). Must match the ``agent``
        field in test case YAMLs and the ``cases/{agent}/`` directory.
    description:
        Human-readable description of the agent's purpose.
    system_prompt:
        Instructions injected at the start of every conversation.
    tools:
        Tool definitions declared in this agent, used to build ``FunctionTool``
        instances and to validate ``tool_responses`` keys in test cases.
    x_harness:
        Raw ``x-harness:`` extension block dict. Keys: ``categories``,
        ``thresholds``, ``personas`` (placeholder for Slice 15C).
    """

    name: str
    description: str
    system_prompt: str
    tools: list[MafToolDef]
    x_harness: dict[str, Any]


def load_agent_yaml(path: Path) -> MafAgentYaml:
    """Load and validate a MAF agent YAML from *path*.

    Raises
    ------
    MafAgentYamlError
        If the file is missing required fields or contains invalid values.
    FileNotFoundError
        If *path* does not exist.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            data: Any = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise MafAgentYamlError(f"Malformed YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise MafAgentYamlError(f"{path}: expected a YAML mapping, got {type(data).__name__}")

    missing = _REQUIRED_FIELDS - data.keys()
    if missing:
        raise MafAgentYamlError(f"{path}: missing required fields: {sorted(missing)}")

    tools = _parse_tools(data["tools"], path)
    x_harness = data.get("x-harness", {})
    if not isinstance(x_harness, dict):
        raise MafAgentYamlError(f"{path}: 'x-harness' must be a mapping")

    return MafAgentYaml(
        name=data["name"],
        description=data["description"],
        system_prompt=data["system_prompt"],
        tools=tools,
        x_harness=x_harness,
    )


def build_maf_agent(
    agent_yaml: MafAgentYaml,
    middleware: StubToolMiddleware,
    *,
    endpoint: str | None = None,
    deployment: str | None = None,
) -> Agent:
    """Build a MAF ``Agent`` from a parsed ``MafAgentYaml``.

    Tool functions are stubs — they raise ``RuntimeError`` if called directly.
    ``StubToolMiddleware`` intercepts every tool call before the stub executes,
    so the stubs are never actually invoked during harness eval.

    Parameters
    ----------
    agent_yaml:
        Parsed agent YAML produced by ``load_agent_yaml()``.
    middleware:
        ``StubToolMiddleware`` instance shared with ``EvalController`` so the
        controller can read ``middleware.trajectory`` after each case run.
    endpoint:
        Azure OpenAI endpoint URL. Defaults to ``AZURE_OPENAI_ENDPOINT`` env var.
    deployment:
        Azure OpenAI deployment name. Defaults to ``AZURE_OPENAI_DEPLOYMENT_AGENT``
        env var.
    """
    resolved_endpoint = endpoint or os.environ["AZURE_OPENAI_ENDPOINT"]
    resolved_deployment = deployment or os.environ["AZURE_OPENAI_DEPLOYMENT_AGENT"]

    client = OpenAIChatClient(
        model=resolved_deployment,
        azure_endpoint=resolved_endpoint,
        credential=DefaultAzureCredential(),
    )

    function_tools = [_make_function_tool(t) for t in agent_yaml.tools]

    return Agent(
        client=client,
        name=agent_yaml.name,
        instructions=agent_yaml.system_prompt,
        tools=function_tools,
        middleware=[middleware],
    )


def _make_function_tool(tool_def: MafToolDef) -> FunctionTool:
    """Create a FunctionTool stub from a MafToolDef.

    The function body raises RuntimeError — StubToolMiddleware intercepts first.
    """

    async def _stub(**_kwargs: Any) -> Any:  # pragma: no cover
        raise RuntimeError(
            f"StubToolMiddleware did not intercept call to '{tool_def.name}' — "
            "this should never execute during harness evaluation."
        )

    return FunctionTool(
        name=tool_def.name,
        description=tool_def.description,
        input_model=tool_def.parameters or {},
        func=_stub,
    )


def _parse_tools(raw: Any, path: Path) -> list[MafToolDef]:
    if not isinstance(raw, list):
        raise MafAgentYamlError(f"{path}: 'tools' must be a list")
    tools: list[MafToolDef] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise MafAgentYamlError(f"{path}: tools[{i}] must be a mapping")
        if "name" not in item or not isinstance(item["name"], str):
            raise MafAgentYamlError(f"{path}: tools[{i}] missing required string field 'name'")
        if "description" not in item or not isinstance(item["description"], str):
            raise MafAgentYamlError(
                f"{path}: tools[{i}] missing required string field 'description'"
            )
        params = item.get("parameters", {})
        if not isinstance(params, dict):
            raise MafAgentYamlError(f"{path}: tools[{i}].parameters must be a mapping")
        tools.append(
            MafToolDef(name=item["name"], description=item["description"], parameters=params)
        )
    return tools
