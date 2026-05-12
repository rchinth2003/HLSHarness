# ADR 0003: Orchestrator-Owned HITL Routing

**Status:** Accepted — Implemented (Slice 0)  
**Date:** 2026-05-12

## Decision
HITL escalation is orchestrator-owned. Sub-agents emit a structured escalation signal (`{escalate: true, reason, confidence}`); the Orchestrator owns all routing logic to human queues. Sub-agents never route directly to humans.

## Context
Every slice has mandatory HITL checkpoints (ambiguous intent, eligibility failure, red-flag triage, etc.). Three patterns were evaluated. The chosen pattern keeps sub-agents stateless and independently testable.

## Alternatives Considered
- **Tool-call-based pause** — each agent invokes `escalate_to_human` MAF tool, suspends conversation, waits for callback. More production-realistic but requires a new HITL simulation capability in the harness before MVE.
- **Dedicated HITL agent** — a fifth agent in the topology receives escalated cases. Most faithful to the doc's escalation roles (scheduler, nurse, benefits coordinator) but adds orchestration complexity and a 6th eval suite.

## Consequences
- Sub-agents are stateless — each can be evaled in isolation without simulating a human callback.
- The harness needs a new `hitl_routing` test category to validate that the Orchestrator correctly detects and routes escalation signals (identified as a blocking harness gap).
- **This gap was closed in Slice 0:** `HITLRoutingScorer` (`hlsharness/hitl_routing.py`) is now live in HLSHarness. It validates escalation signal structure and LLM-assessed routing correctness; `hitl_routing` is registered as a first-class evaluation category with a 0.90 default threshold.
- The `SafetyEscalator` scorer already validates red-flag signal generation — this ADR makes that scorer the primary Triage Agent safety gate.
- A dedicated HITL agent (Option C) remains viable for a post-demo production build.
