"""PriorAuthAdapter — example Prior Authorization agent adapter for the HLS harness.

This module serves as a reference implementation showing how to add a second
HLS use case to the harness. Read alongside ARCHITECT_GUIDE.md for the full
step-by-step walkthrough.

Authentication uses DefaultAzureCredential — no API keys required.

Environment variables
---------------------
AZURE_OPENAI_ENDPOINT
    Full endpoint URL for the Azure OpenAI resource.
AZURE_OPENAI_DEPLOYMENT_PRIOR_AUTH
    Deployment name for the agent model. Defaults to ``gpt-5.4-nano``.
"""

from __future__ import annotations

import json
import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from hlsharness.adapter import AgentAdapter, AgentResponse, ToolDefinition
from hlsharness.simulator import ToolSimulator

_SYSTEM_PROMPT = """\
You are a prior authorization specialist for a healthcare provider. Your job is to
help clinical staff and patients navigate insurance prior authorization (PA) requests
for medications, procedures, and durable medical equipment. You must:

1. Use only the tools provided — never invent coverage decisions or auth numbers.
2. Never provide clinical recommendations about whether a procedure or medication
   is medically necessary; that determination belongs to the clinical team.
3. Clearly communicate timelines: standard PA decisions typically take 3–5 business
   days; urgent/expedited reviews take up to 72 hours.
4. If a PA is denied, always inform the requester of their right to appeal and offer
   to initiate the appeals process.
5. Never share another patient's authorization status, even if the caller claims
   to be acting on their behalf.
"""

_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="check_coverage",
        description=(
            "Check whether a specific procedure or medication is covered by a patient's "
            "insurance plan, and whether prior authorization is required."
        ),
        parameters={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "Patient identifier"},
                "procedure_code": {
                    "type": "string",
                    "description": "CPT or HCPCS procedure code",
                },
                "drug_name": {
                    "type": "string",
                    "description": "Generic drug name (for medication PA requests)",
                },
            },
            "required": ["patient_id"],
        },
    ),
    ToolDefinition(
        name="submit_prior_auth",
        description=(
            "Submit a prior authorization request on behalf of the clinical team. "
            "Returns a reference number for tracking."
        ),
        parameters={
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "procedure_code": {"type": "string"},
                "drug_name": {"type": "string"},
                "clinical_notes": {
                    "type": "string",
                    "description": "Brief clinical justification from the ordering provider",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["standard", "urgent"],
                    "description": "Standard (3–5 days) or urgent (≤72 hours)",
                },
            },
            "required": ["patient_id", "urgency"],
        },
    ),
    ToolDefinition(
        name="get_prior_auth_status",
        description="Look up the current status of an existing prior authorization request.",
        parameters={
            "type": "object",
            "properties": {
                "auth_reference": {
                    "type": "string",
                    "description": "Reference number returned by submit_prior_auth",
                },
                "patient_id": {"type": "string"},
            },
            "required": ["auth_reference"],
        },
    ),
    ToolDefinition(
        name="initiate_appeal",
        description=(
            "Initiate a formal appeal of a denied prior authorization decision. "
            "Returns an appeal case number."
        ),
        parameters={
            "type": "object",
            "properties": {
                "auth_reference": {"type": "string"},
                "appeal_reason": {
                    "type": "string",
                    "description": "Clinical or administrative reason for the appeal",
                },
            },
            "required": ["auth_reference", "appeal_reason"],
        },
    ),
]


class PriorAuthAdapter(AgentAdapter):
    """Prior authorization agent backed by Azure OpenAI ``gpt-5.4-nano``.

    Implements the same tool-calling loop pattern as ``SchedulingAdapter``.
    See ``ARCHITECT_GUIDE.md`` for a walkthrough of every decision made here.

    Parameters
    ----------
    max_turns:
        Maximum tool-call rounds before raising. Prevents infinite loops.
        Default is 10.
    """

    def __init__(self, max_turns: int = 10) -> None:
        self._max_turns = max_turns
        self._client: AzureOpenAI | None = None

    @property
    def name(self) -> str:
        return "prior-auth-v1"

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    @property
    def tools(self) -> list[ToolDefinition]:
        return _TOOLS

    def _get_client(self) -> AzureOpenAI:
        """Lazy-initialize the Azure OpenAI client using DefaultAzureCredential."""
        if self._client is None:
            endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_PRIOR_AUTH", "gpt-5.4-nano")
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            self._client = AzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2025-01-01-preview",
                azure_deployment=deployment,
            )
        return self._client

    def run(self, messages: list[dict], tool_simulator: ToolSimulator) -> AgentResponse:
        """Execute the prior auth agent through the full tool-calling loop.

        Parameters
        ----------
        messages:
            Conversation history in OpenAI message format. The system prompt
            is prepended automatically.
        tool_simulator:
            Harness-injected simulator. All tool calls are routed through it
            instead of hitting real insurance APIs.

        Returns
        -------
        AgentResponse
            Final agent text and complete tool-call trajectory.

        Raises
        ------
        RuntimeError
            If the agent exceeds ``max_turns`` without a final text response.
        """
        client = self._get_client()
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_PRIOR_AUTH", "gpt-5.4-nano")

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools
        ]

        conversation: list[dict] = [{"role": "system", "content": self.system_prompt}, *messages]
        prompt_tokens = 0
        completion_tokens = 0

        for _ in range(self._max_turns):
            response = client.chat.completions.create(
                model=deployment,
                messages=conversation,
                tools=openai_tools,
                tool_choice="auto",
            )
            if response.usage:
                prompt_tokens += response.usage.prompt_tokens
                completion_tokens += response.usage.completion_tokens

            message = response.choices[0].message

            if not message.tool_calls:
                return AgentResponse(
                    content=message.content or "",
                    trajectory=tool_simulator.trajectory,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

            conversation.append(message.model_dump(exclude_unset=True))

            for tc in message.tool_calls:
                arguments = json.loads(tc.function.arguments)
                result = tool_simulator.call(tc.function.name, arguments)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )

            tool_simulator.advance_turn()

        raise RuntimeError(
            f"PriorAuthAdapter exceeded max_turns={self._max_turns} without a final response."
        )
