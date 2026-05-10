"""AgentAdapter contract — the pluggable interface every HLS agent must implement.

To add a new HLS use case, subclass AgentAdapter, implement all abstract members,
and place the class in hlsharness/adapters/. See ARCHITECT_GUIDE.md for a walkthrough.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hlsharness.simulator import ToolSimulator


@dataclass
class ToolDefinition:
    """Describes a single tool the agent may call during a conversation turn.

    Parameters
    ----------
    name:
        Identifier used by the LLM when issuing a tool call. Must be unique
        within an adapter's tool list.
    description:
        Natural-language description passed to the LLM in the system prompt.
        Write it from the LLM's perspective: what does this tool *do for me*?
    parameters:
        JSON Schema object describing the tool's input arguments. Follows the
        OpenAI function-calling schema (``type: object``, ``properties``, etc.).
    """

    name: str
    description: str
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass
class ToolCall:
    """A single tool invocation recorded during an agent run.

    Parameters
    ----------
    turn:
        Zero-based index of the conversation turn in which the call occurred.
    tool_name:
        Name of the tool that was called.
    arguments:
        Parsed arguments dict passed by the LLM.
    response:
        The scripted response returned by the ToolSimulator.
    """

    turn: int
    tool_name: str
    arguments: dict[str, object]
    response: dict[str, object]


@dataclass
class AgentResponse:
    """The result of a single end-to-end agent run through the ToolSimulator.

    Parameters
    ----------
    content:
        The agent's final text response to the patient.
    trajectory:
        Ordered list of every tool call made during the run, as captured by
        the ToolSimulator. Empty if the agent issued no tool calls.
    """

    content: str
    trajectory: list[ToolCall] = field(default_factory=list)


class AgentAdapter(ABC):
    """Abstract base class for all HLS agent adapters.

    Each HLS use case (scheduling, prior auth, referral, etc.) ships its own
    concrete subclass. The harness calls ``run()`` and knows nothing about the
    agent's internal prompting, model parameters, or retry logic.

    Subclasses must be stateless across calls — the harness may call ``run()``
    many times in parallel on the same adapter instance.

    Example
    -------
    See ``hlsharness/adapters/scheduling.py`` for a complete implementation and
    ``ARCHITECT_GUIDE.md`` for step-by-step instructions.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for this adapter (e.g. ``"scheduling-v1"``).

        Used as the directory key under ``cases/`` and in ``results.json``.
        Must be unique across all registered adapters.
        """

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt injected at the start of every conversation turn."""

    @property
    @abstractmethod
    def tools(self) -> list[ToolDefinition]:
        """Tools the agent may call, declared for both the LLM and the ToolSimulator.

        The harness uses this list to validate that test case ``tool_responses``
        only reference tools the adapter actually declares.
        """

    @abstractmethod
    def run(self, messages: list[dict[str, object]], tool_simulator: ToolSimulator) -> AgentResponse:
        """Execute a single multi-turn agent conversation.

        The adapter must route all tool calls through ``tool_simulator.call()``
        rather than hitting real backends. The simulator records the trajectory
        automatically.

        Parameters
        ----------
        messages:
            Conversation history in OpenAI message format (role + content).
        tool_simulator:
            Harness-injected simulator. Call ``tool_simulator.call(tool_name, args)``
            instead of invoking real external services.

        Returns
        -------
        AgentResponse
            Final text content and the full tool-call trajectory.
        """
