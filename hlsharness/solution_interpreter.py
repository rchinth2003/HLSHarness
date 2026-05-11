"""SolutionInterpreter — auto-generate solution.yaml from N MAF Agent YAMLs.

Follows the same draft → Manifest Critique → Architect approval pattern as
``SpecInterpreter``.  Topology inference (orchestrator vs. peers) and threshold
computation (most conservative per category) are computed in Python; the LLM
generates only the Manifest Critique text.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import yaml

from hlsharness.maf_agent import MafAgentYaml, load_agent_yaml

_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
_DEFAULT_DEPLOYMENT = "gpt-5.4-pro"

_CRITIQUE_PROMPT = """\
You are a senior HLS agent evaluator reviewing a draft solution.yaml manifest \
for a multi-agent HLS solution.

## Agent summaries
{agent_summaries}

## Draft solution.yaml
{solution_yaml}

## Topology detection
{topology_note}

Write a Manifest Critique (3–6 bullet points) covering:
1. Whether the topology detection looks correct — if the orchestrator \
identification seems wrong or ambiguous, say so.
2. Any agents whose declared categories are not covered by the solution \
thresholds (missing threshold coverage).
3. Threshold inconsistencies — flag any threshold that is too lenient for a \
safety or regulatory category (e.g. safety below 0.9).
4. Any ambiguity in agent roles or gaps in category coverage across agents.
5. Suggested changes before committing this manifest.

Return plain text — no JSON, no markdown code fences.
"""


def _default_llm_fn(prompt: str) -> str:  # pragma: no cover
    """Call Azure OpenAI and return raw critique text."""
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
        temperature=0.2,
    )
    return completion.choices[0].message.content or ""


class SolutionInterpreter:
    """Generates ``solution.yaml`` from N existing MAF Agent YAMLs.

    Parameters
    ----------
    llm_fn:
        Callable ``(prompt: str) -> str``.  Defaults to Azure OpenAI.
        Inject a deterministic fake for unit tests.
    """

    def __init__(self, llm_fn: Callable[[str], str] | None = None) -> None:
        self._llm_fn = llm_fn or _default_llm_fn

    def interpret(
        self,
        agent_yaml_paths: list[Path],
        solution_name: str,
    ) -> tuple[str, str]:
        """Generate a draft ``solution.yaml`` and Manifest Critique.

        Parameters
        ----------
        agent_yaml_paths:
            Ordered list of paths to ``agent.yaml`` files.
        solution_name:
            Slug name for the solution written into the YAML.

        Returns
        -------
        tuple[str, str]
            ``(solution_yaml_text, critique_text)``.
        """
        agents = [load_agent_yaml(p) for p in agent_yaml_paths]
        thresholds = self._compute_thresholds(agents)
        orchestrator = self._infer_orchestrator(agents)
        solution_yaml_text = self._build_solution_yaml(
            solution_name, agents, thresholds, orchestrator
        )
        critique_text = self._build_critique(agents, solution_yaml_text, orchestrator)
        return solution_yaml_text, critique_text

    # ── internals ─────────────────────────────────────────────────────────────

    def _compute_thresholds(self, agents: list[MafAgentYaml]) -> dict[str, float]:
        """Return the most-conservative (minimum) threshold per category."""
        mins: dict[str, float] = {}
        for agent in agents:
            agent_thresholds: dict[str, float] = agent.x_harness.get("thresholds", {})
            for category, threshold in agent_thresholds.items():
                t = float(threshold)
                if category not in mins or t < mins[category]:
                    mins[category] = t
        return mins

    def _infer_orchestrator(self, agents: list[MafAgentYaml]) -> str | None:
        """Return the orchestrator agent name, or None for peer topology.

        Heuristic: an agent is an orchestrator if any of its tool names contain
        another agent's name slug (hyphens normalised to underscores).
        """
        agent_names = {a.name for a in agents}
        for agent in agents:
            for tool in agent.tools:
                tool_key = tool.name.replace("-", "_").lower()
                for other_name in agent_names:
                    if other_name == agent.name:
                        continue
                    slug = other_name.replace("-", "_").lower()
                    if slug in tool_key:
                        return agent.name
        return None

    def _build_solution_yaml(
        self,
        solution_name: str,
        agents: list[MafAgentYaml],
        thresholds: dict[str, float],
        orchestrator: str | None,
    ) -> str:
        """Emit solution.yaml text with a topology comment header."""
        if orchestrator:
            topology_comment = f"# topology: orchestrator ({orchestrator} routes to peers)\n"
        else:
            topology_comment = "# topology: peer (no single orchestrator)\n"

        doc: dict[str, object] = {
            "solution": solution_name,
            "agents": [{"name": a.name, "stub": False} for a in agents],
        }
        if thresholds:
            doc["thresholds"] = {k: thresholds[k] for k in sorted(thresholds)}
        yaml_body: str = yaml.dump(doc, allow_unicode=True, sort_keys=False)
        return topology_comment + yaml_body

    def _build_critique(
        self,
        agents: list[MafAgentYaml],
        solution_yaml_text: str,
        orchestrator: str | None,
    ) -> str:
        topology_note = (
            f"Orchestrator topology: '{orchestrator}' identified as orchestrator."
            if orchestrator
            else "Peer topology: no orchestrator agent identified."
        )
        agent_summaries = "\n".join(
            f"- {a.name}: categories={a.x_harness.get('categories', [])}, "
            f"thresholds={a.x_harness.get('thresholds', {})}, "
            f"tools={[t.name for t in a.tools]}"
            for a in agents
        )
        prompt = _CRITIQUE_PROMPT.format(
            agent_summaries=agent_summaries,
            solution_yaml=solution_yaml_text,
            topology_note=topology_note,
        )
        return self._llm_fn(prompt)
