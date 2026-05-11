# ADR-0003: L3 Evaluation Model — Per-Agent Isolation (L1) and Solution-Level Rollup (L2)

**Status:** Accepted  
**Date:** 2026-05-11

## Context

As Architects onboard multi-agent HLS solutions — orchestrator-routed (B1) and peer-agent (B2) topologies — the existing single-agent `EvalController` cannot answer the question: "Does the composed solution stay within behavioral thresholds when agents interact?"

Two evaluation levels are required:

- **L1 (per-agent isolation):** Each agent is evaluated independently. All dependencies — including peer agents and external tools — are stubbed via `StubToolMiddleware`. Localises behavioral regressions to a specific agent.
- **L2 (solution-level rollup):** All agents in the solution run together. Only external tools are stubbed. Tests real orchestration behavior: routing logic, cross-agent trajectory, and emergent failure modes that only appear when agents compose.

Without both levels, L1 alone misses orchestration bugs (a correct agent can behave incorrectly when routed to unexpectedly), and L2 alone cannot localise which agent caused a solution-level regression.

Three alternatives were considered:

1. **L1 only** — run each agent independently, never test composition. Fast, but misses orchestration bugs.
2. **L2 only** — run the solution together, aggregate scores. Can detect regressions but cannot attribute them.
3. **L3 (L1 + L2, this decision)** — run both. A regression visible at L2 but not at L1 implies the bug is in orchestration logic, not an individual agent. An L1 regression that also appears at L2 attributes the root cause.

## Decision

Adopt the **L3 evaluation model**: every solution eval run produces both per-agent `EvalResults` (L1) and a solution-level `SolutionResult` (L2).

`SolutionController` orchestrates L2 by delegating L1 to the existing `EvalController` — no duplication of single-agent eval logic. A new `solution.yaml` manifest declares the agents in the solution, their topology, and solution-level category thresholds.

Both B1 (orchestrator agent routes to sub-agents via tool calls) and B2 (peer agents, no single root) topologies are supported. The manifest does not require declaring an orchestrator — topology is inferred by `SolutionInterpreter` during onboarding.

## Consequences

- `SolutionController` added as a new module; `EvalController` is unchanged.
- `SolutionResult` added to `results.py`; `EvalResults` is unchanged.
- CI exit code 1 (absolute threshold fail) applies to both L1 and L2 results. A solution passes only if all agents pass L1 and the solution passes L2.
- Impact analysis becomes actionable: if billing-v1 changes, an Architect can run L3 to see which L1 agents regressed and whether the L2 solution score moved.
- **Trade-off accepted:** L3 runs take longer than L1 alone — every agent runs its full case suite, plus the solution runs cases again end-to-end. Accepted because solution eval is a pre-promotion gate, not a hot-loop operation.
