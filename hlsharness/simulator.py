"""ToolSimulator — intercepts agent tool calls and returns scripted responses.

The simulator is the harness's substitute for real backends (Epic FHIR, eligibility
APIs, etc.). It makes agent runs deterministic: the same test case always produces
the same tool responses, regardless of backend availability.
"""

from __future__ import annotations

from .adapter import ToolCall


class UnknownToolError(Exception):
    """Raised when the agent calls a tool not declared in the test case's tool_responses."""


class ToolSimulator:
    """Intercepts tool calls from an AgentAdapter and returns scripted responses.

    Pass an instance to ``AgentAdapter.run()`` instead of real service clients.
    After the run completes, read ``trajectory`` to inspect every call the agent made.

    Parameters
    ----------
    tool_responses:
        Mapping of tool name → scripted response dict, sourced from the test case
        YAML ``tool_responses`` section. A tool may be called multiple times; the
        same scripted response is returned each time (stateless replay).

    Examples
    --------
    >>> sim = ToolSimulator({"search_available_slots": {"slots": []}})
    >>> result = sim.call("search_available_slots", {"patient_id": "P1"})
    >>> result
    {'slots': []}
    >>> sim.trajectory[0].tool_name
    'search_available_slots'
    """

    def __init__(self, tool_responses: dict[str, dict[str, object]]) -> None:
        self._responses = tool_responses
        self._trajectory: list[ToolCall] = []
        self._turn: int = 0

    def call(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Intercept a tool call and return the scripted response.

        Records the call in ``trajectory`` before returning.

        Parameters
        ----------
        tool_name:
            The tool the agent wants to invoke.
        arguments:
            Arguments the agent passed to the tool.

        Returns
        -------
        dict
            The scripted response from the test case YAML.

        Raises
        ------
        UnknownToolError
            If ``tool_name`` is not present in the ``tool_responses`` provided
            at construction time. This catches adapters calling tools their test
            case didn't script a response for.
        """
        if tool_name not in self._responses:
            raise UnknownToolError(
                f"Agent called '{tool_name}' but no scripted response exists for it. "
                f"Available tools: {list(self._responses.keys())}"
            )
        response = self._responses[tool_name]
        self._trajectory.append(
            ToolCall(
                turn=self._turn,
                tool_name=tool_name,
                arguments=arguments,
                response=response,
            )
        )
        return response

    def advance_turn(self) -> None:
        """Increment the turn counter.

        Call this between conversation turns so the trajectory records which
        turn each tool call occurred in.
        """
        self._turn += 1

    @property
    def trajectory(self) -> list[ToolCall]:
        """Ordered record of every tool call made during the agent run."""
        return list(self._trajectory)
