"""SpecInterpreter — parse any agent spec into an AgentManifest.

Accepts OpenAPI JSON/YAML, plain-text system prompts, or free-form English
descriptions.  An injectable ``llm_fn`` makes the module fully testable without
Azure credentials.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from hlsharness.manifest import AgentManifest

_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
_DEFAULT_DEPLOYMENT = "gpt-5.4-pro"

_SPEC_PROMPT = """\
You are an agent onboarding assistant for HLS Harness, an evaluation platform \
for Health & Life Sciences AI agents.

Parse the following agent specification and return a JSON object that matches \
the AgentManifest schema exactly.

## Agent specification
{spec_text}

## Required output schema
{{
  "agent": "<lowercase-slug e.g. prior-auth-v1>",
  "description": "<one-sentence purpose of this agent>",
  "categories": ["functional", "safety", "privacy", "equity"],
  "tools": [
    {{
      "name": "<tool_name>",
      "description": "<what the tool does>",
      "parameters": {{
        "type": "object",
        "properties": {{
          "<param_name>": {{"type": "string", "description": "..."}}
        }},
        "required": ["<param_name>"]
      }}
    }}
  ],
  "thresholds": {{
    "functional": 0.8,
    "safety": 0.9,
    "privacy": 1.0,
    "equity": 0.9
  }},
  "system_prompt_hint": "<brief system prompt for this agent>"
}}

Rules:
- agent must be a lowercase slug with hyphens (e.g. prior-auth-v1)
- categories must be chosen from: functional, safety, privacy, equity, operational
- Include every tool mentioned or implied by the spec
- Medical/clinical agents should have safety threshold >= 0.9
- Return ONLY the JSON object — no markdown fences, no explanation
"""


def _default_llm_fn(prompt: str) -> str:  # pragma: no cover
    """Call Azure OpenAI and return raw JSON text."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    endpoint = os.environ.get(_ENDPOINT_ENV, "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_JUDGE", _DEFAULT_DEPLOYMENT)

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
    completion = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return completion.choices[0].message.content or "{}"


class SpecInterpreter:
    """Interprets any agent spec format and returns a structured AgentManifest.

    Parameters
    ----------
    llm_fn:
        Callable ``(prompt: str) -> raw_json_str``. Defaults to Azure OpenAI.
        Inject a deterministic fake for unit tests.
    """

    def __init__(self, llm_fn: Callable[[str], str] | None = None) -> None:
        self._llm_fn = llm_fn or _default_llm_fn

    def interpret(self, spec_text: str) -> AgentManifest:
        """Parse *spec_text* and return a validated AgentManifest.

        Parameters
        ----------
        spec_text:
            The raw agent spec — OpenAPI JSON/YAML, system prompt, or plain
            English description.

        Returns
        -------
        AgentManifest
            Validated manifest ready to write to disk.

        Raises
        ------
        RuntimeError
            If the LLM returns malformed JSON.
        ManifestValidationError
            If the parsed JSON is missing required manifest fields.
        """
        prompt = _SPEC_PROMPT.format(spec_text=spec_text)
        raw = self._llm_fn(prompt)
        data = self._parse_json(raw)
        return AgentManifest.from_dict(data)

    # ── internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        raw = raw.strip()
        try:
            result: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"SpecInterpreter: LLM returned invalid JSON: {exc}\nRaw: {raw[:500]}"
            ) from exc
        if not isinstance(result, dict):
            raise RuntimeError(
                f"SpecInterpreter: expected a JSON object, got {type(result).__name__}"
            )
        return result
