# HLSHarness — Architecture Guide

This folder contains architecture documentation and diagrams for the **HLS Harness** — a multi-agent evaluation harness for patient scheduling AI systems built on the Microsoft Agent Framework (MAF), backed by Azure OpenAI.

## Documents

| File | Description |
|------|-------------|
| [01-system-overview.md](01-system-overview.md) | High-level architecture diagram — all layers and components |
| [02-scoring-pipeline.md](02-scoring-pipeline.md) | Scoring pipeline internals — 3-stage rubric, all 7 categories |
| [03-l1-eval-flow.md](03-l1-eval-flow.md) | Sequence diagram — L1 single-agent evaluation run |
| [04-l2-solution-flow.md](04-l2-solution-flow.md) | Sequence diagram — L2 multi-agent solution evaluation |
| [05-onboarding-flow.md](05-onboarding-flow.md) | Sequence diagram — Agent onboarding workflow (spec → YAML → cases) |
| [06-demo-scenarios.md](06-demo-scenarios.md) | Sequence diagrams for all 6 demo scenarios |
| [07-auth-and-azure.md](07-auth-and-azure.md) | Authentication & Azure integration pattern |
| [08-data-models.md](08-data-models.md) | Data model reference with relationships |

## Quick Reference

```
hls-eval run       → L1 single-agent eval     → results.json
hls-eval solution  → L2 multi-agent eval      → solution_results.json
hls-eval onboard   → spec-to-agent workflow   → agent.yaml + cases/
streamlit run ...  → dashboard                → browser UI
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12, mypy strict, ruff |
| Agent Runtime | Microsoft Agent Framework (MAF) |
| LLM Backend | Azure OpenAI (gpt-5.4-pro judge, gpt-5.4-nano agent) |
| Auth | DefaultAzureCredential (no keys stored) |
| Config | YAML (agent.yaml, solution.yaml, cases/*.yaml) |
| Persistence | SQLite (RunStore), JSON (results) |
| UI | Streamlit dashboard |
| CI | GitHub Actions (format → lint → mypy → pytest) |
