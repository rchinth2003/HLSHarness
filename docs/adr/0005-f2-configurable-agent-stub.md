# ADR-0005: F2 — Configurable Per-Agent Stub in Solution Eval

**Status:** Accepted  
**Date:** 2026-05-11

## Context

In L2 solution eval, multiple agents run together. The question is: what gets stubbed?

Two options were considered:

- **F1 (all-live):** Only external tools are stubbed via `StubToolMiddleware`. All agents run live against each other. Tests real end-to-end composition. Cannot isolate impact — if billing-v1 changed, you cannot hold referral-v1 static to test billing-v1 in isolation within the composed solution.
- **F2 (configurable per-agent stub, this decision):** Each agent in `solution.yaml` declares `stub: true | false`. Agents with `stub: true` return scripted fixture responses instead of running live. Agents with `stub: false` run live. The default is `stub: false` (all-live), making F1 behavior the default and F2 an opt-in.

The Architect's core use case is impact analysis: "I changed billing-v1 — what moved?" With F1, the Architect cannot surgically isolate billing-v1 against its peers. With F2, they set `stub: true` on all peer agents and run solution eval — only billing-v1 runs live, its behavior is isolated within the composed solution context.

## Decision

Adopt **F2**: each agent entry in `solution.yaml` carries an optional `stub` boolean (defaults to `false`).

```yaml
agents:
  - name: scheduling-v1
    stub: false        # runs live
  - name: billing-v1
    stub: false        # the agent under test
  - name: referral-v1
    stub: true         # held static with fixture responses
```

`SolutionController` reads the `stub` flag when instantiating each agent. Stubbed agents use the same `StubToolMiddleware` + fixture library mechanism as L1 eval — no new stub infrastructure is required.

Upfront validation (`CaseValidationError`) checks that every agent with `stub: true` has fixture coverage in the `stubs/{agent}/` library before the eval loop starts.

## Consequences

- `solution.yaml` gains one optional boolean field per agent entry. Backward-compatible default.
- No new stub mechanism — `StubToolMiddleware` and the fixture library already provide this capability at L1. F2 reuses it at L2.
- An Architect can now answer: "I changed billing-v1. Here is how the solution-level score moved with only billing-v1 live and all peers held static."
- **Trade-off accepted:** a fully-stubbed solution (`stub: true` on all agents) is technically valid YAML but produces no signal about inter-agent behavior. Upfront validation does not reject this configuration — it is the Architect's responsibility to leave at least one agent live. A warning may be added in a future slice.
