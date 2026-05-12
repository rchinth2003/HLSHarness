# ADR 0001: MAF as Agent Framework

**Status:** Accepted — Implemented (Slice 0)  
**Date:** 2026-05-12

## Decision
Build all patient scheduling agents using Microsoft Agent Framework (MAF) with declarative `agent.yaml` definitions.

## Context
The HLSHarness eval platform is purpose-built for MAF. Agent definitions, tool dispatch interception (`StubToolMiddleware`), and the scorer pipeline are all coupled to MAF's protocol. Alternative frameworks (Claude SDK, LangChain, AutoGen) would require significant harness rework before a single eval could run.

## Alternatives Considered
- **Claude SDK / Anthropic API** — would require rewriting harness scorer dispatch and tool interception. Adds 1–2 weeks of harness work before MVE.
- **LangChain / AutoGen** — no native harness support; adapter pattern would need to be re-introduced (it was already deprecated in the harness).

## Consequences
- Agent LLM backend is Azure OpenAI via `DefaultAzureCredential` — no API keys in code.
- Agent definitions are YAML-first; tool schemas must be declared in `agent.yaml`.
- Claude or other models cannot be used as agent LLM without a MAF config change and harness adapter.
