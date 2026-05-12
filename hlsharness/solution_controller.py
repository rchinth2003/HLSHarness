"""SolutionController — orchestrates L2 multi-agent solution evaluation.

Delegates L1 per-agent eval to ``EvalController`` (one per declared agent),
then rolls up the per-agent ``EvalResults`` into a solution-level
``SolutionResult``.

L2 rollup algorithm
-------------------
For each category present across any L1 result, aggregate total cases and
passed cases across all agents, compute the aggregate pass rate, and apply
solution-level thresholds from the manifest (merged over the harness defaults).

Stub mode
---------
Agents declared ``stub: true`` in the solution manifest are run through the
same ``EvalController`` flow as live agents.  ``StubToolMiddleware`` already
intercepts all tool calls using scripted YAML fixtures — ``stub: true`` is
primarily a documentation and validation signal (the manifest validator checks
that fixture files exist for those agents before the eval loop starts).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hlsharness.controller import DEFAULT_THRESHOLDS, EvalController
from hlsharness.judge import Scorer
from hlsharness.results import CategorySummary, EvalResults, SolutionResult
from hlsharness.solution_manifest import AgentEntry, SolutionManifest

_ROUTING_CATEGORIES: frozenset[str] = frozenset({"functional", "hitl_routing"})


class SolutionController:
    """Orchestrates L2 evaluation for a declared multi-agent solution.

    Parameters
    ----------
    manifest:
        A loaded and validated ``SolutionManifest`` describing the agents
        and solution-level thresholds.
    judge:
        Any object satisfying the ``Scorer`` protocol. Shared across all
        L1 ``EvalController`` instances.
    cases_path:
        Root of the ``cases/`` directory tree (``cases/{agent}/`` per agent).
    stubs_path:
        Root of the ``stubs/`` directory tree. Defaults to
        ``cases_path.parent / "stubs"``.
    azure_endpoint:
        Azure OpenAI endpoint URL. Forwarded to each ``EvalController``.
    azure_deployment:
        Azure OpenAI deployment name. Forwarded to each ``EvalController``.
    """

    def __init__(
        self,
        manifest: SolutionManifest,
        judge: Scorer,
        cases_path: Path,
        stubs_path: Path | None = None,
        *,
        azure_endpoint: str | None = None,
        azure_deployment: str | None = None,
        run_store: Any | None = None,
    ) -> None:
        self._manifest = manifest
        self._judge = judge
        self._cases_path = cases_path
        self._stubs_path = stubs_path
        self._azure_endpoint = azure_endpoint
        self._azure_deployment = azure_deployment
        self._run_store = run_store

    def run(self, categories: list[str] | None = None) -> SolutionResult:
        """Run L1 eval for each declared agent and return an L2 ``SolutionResult``.

        Parameters
        ----------
        categories:
            If provided, each ``EvalController`` will only evaluate cases in
            these categories.  Passing ``None`` evaluates all categories found
            for each agent.

        Returns
        -------
        SolutionResult
            L2 result containing per-agent ``EvalResults`` and solution-level
            ``CategorySummary`` entries.
        """
        agent_results: list[EvalResults] = []

        for entry in self._manifest.agents:
            agent_yaml_path = self._cases_path / entry.name / "agent.yaml"
            ctrl = EvalController(
                agent_yaml_path=agent_yaml_path,
                judge=self._judge,
                cases_path=self._cases_path,
                stubs_path=self._stubs_path,
                azure_endpoint=self._azure_endpoint,
                azure_deployment=self._azure_deployment,
            )
            result = ctrl.run(categories=categories)
            agent_results.append(result)

        solution_categories = self._rollup(agent_results)

        solution_result = SolutionResult.create(
            solution=self._manifest.solution,
            agent_results=agent_results,
            solution_categories=solution_categories,
        )

        if self._run_store is not None:
            self._run_store.save(solution_result)

        return solution_result

    # ── internals ─────────────────────────────────────────────────────────────

    def _routing_deps_satisfied(
        self,
        entry: AgentEntry,
        results_by_agent: dict[str, EvalResults],
    ) -> bool:
        """Return True if every declared routing dependency passed its routing categories.

        An agent with no ``depends_on`` entries is unconditionally eligible.
        A dependency fails the gate if any of its functional or hitl_routing
        category summaries did not meet threshold in the L1 result.
        """
        for dep_name in entry.depends_on:
            dep = results_by_agent.get(dep_name)
            if dep is None:
                return False
            for cat in dep.categories:
                if cat.category in _ROUTING_CATEGORIES and not cat.met_threshold:
                    return False
        return True

    def _rollup(self, agent_results: list[EvalResults]) -> list[CategorySummary]:
        """Build solution-level category summaries from per-agent L1 results.

        Only agents whose routing dependencies passed (functional + hitl_routing
        categories met threshold) are credited in the rollup.  Agents with no
        ``depends_on`` entries are always included.

        Pass rate is computed as total passed / total cases across all eligible
        agents that participated in a given category (weighted by case count).
        """
        thresholds = {**DEFAULT_THRESHOLDS, **self._manifest.thresholds}
        results_by_agent: dict[str, EvalResults] = {r.agent: r for r in agent_results}

        eligible: list[EvalResults] = []
        for entry in self._manifest.agents:
            result = results_by_agent.get(entry.name)
            if result is None:
                continue
            if self._routing_deps_satisfied(entry, results_by_agent):
                eligible.append(result)

        seen: set[str] = set()
        ordered_cats: list[str] = []
        for result in eligible:
            for cat_summary in result.categories:
                if cat_summary.category not in seen:
                    seen.add(cat_summary.category)
                    ordered_cats.append(cat_summary.category)

        summaries: list[CategorySummary] = []
        for cat in sorted(ordered_cats):
            matching = [c for r in eligible for c in r.categories if c.category == cat]
            if not matching:
                continue
            total = sum(c.total for c in matching)
            passed_count = sum(c.passed_count for c in matching)
            pass_rate = passed_count / total if total > 0 else 0.0
            threshold = thresholds.get(cat, DEFAULT_THRESHOLDS.get(cat, 0.8))
            summaries.append(
                CategorySummary(
                    category=cat,
                    total=total,
                    passed_count=passed_count,
                    pass_rate=pass_rate,
                    threshold=threshold,
                    met_threshold=pass_rate >= threshold,
                )
            )
        return summaries
