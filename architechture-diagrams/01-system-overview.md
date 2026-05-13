# System Architecture Overview

HLSHarness is a **CLI evaluation harness** for patient scheduling multi-agent systems. It runs agents in a sandboxed environment with stubbed tool responses, scores outputs against category-specific rubrics using a judge LLM, and produces structured pass/fail reports.

## Architecture Layers

```mermaid
graph TB
    subgraph USER["User Layer"]
        CLI["hls-eval CLI\n(__main__.py)"]
        DASH["Streamlit Dashboard\n(dashboard/app.py)"]
    end

    subgraph ORCH["Orchestration Layer"]
        EC["EvalController\n(L1 single-agent)"]
        SC["SolutionController\n(L2 multi-agent)"]
        DAG["DAG Routing Gate\n(depends_on resolution)"]
    end

    subgraph AGENT["Agent Runtime Layer"]
        MAF["MAF Agent\n(from agent.yaml)"]
        STUB["StubToolMiddleware\n(intercepts tool calls)"]
        AOAI_AGENT["Azure OpenAI\ngpt-5.4-nano (agent)"]
    end

    subgraph SCORE["Scoring Layer"]
        JUDGE["Judge\n(category registry)"]
        FS["FunctionalScorer"]
        SS["SafetyEscalator"]
        PS["PrivacyGuard\n+ PHI regex"]
        ES["EquityAnalyzer"]
        US["UrgencyTriageScorer"]
        RS["RegulatoryComplianceScorer"]
        HS["HITLRoutingScorer\n+ signal schema"]
        AOAI_JUDGE["Azure OpenAI\ngpt-5.4-pro (judge)"]
    end

    subgraph DATA["Data Layer"]
        CL["CaseLoader\n(YAML → TestCase)"]
        CG["CaseGenerator\n(LLM-powered)"]
        RS_DB["RunStore\n(SQLite)"]
        PL["PersonaLoader"]
        FIXTURES["Stub Fixtures\n(stubs/{agent}/{tool}/)"]
        CASES["Test Cases\n(cases/{agent}/)"]
        PERSONAS["Personas\n(personas/)"]
    end

    subgraph PERSIST["Persistence Layer"]
        RJSON["results.json"]
        SRJSON["solution_results.json"]
        SQLITE[".hls_runs.db\n(SQLite)"]
    end

    subgraph AZURE["Azure Services"]
        AAD["Azure AD\n(DefaultAzureCredential)"]
        AOAI_SVC["Azure OpenAI Service"]
    end

    CLI --> EC
    CLI --> SC
    CLI --> CG
    DASH --> RJSON
    DASH --> SRJSON
    DASH --> SQLITE

    SC --> EC
    SC --> DAG
    EC --> MAF
    EC --> JUDGE
    EC --> CL

    MAF --> STUB
    STUB --> AOAI_AGENT
    AOAI_AGENT --> AOAI_SVC

    JUDGE --> FS
    JUDGE --> SS
    JUDGE --> PS
    JUDGE --> ES
    JUDGE --> US
    JUDGE --> RS
    JUDGE --> HS
    FS & SS & PS & ES & US & RS & HS --> AOAI_JUDGE
    AOAI_JUDGE --> AOAI_SVC

    CL --> CASES
    CL --> FIXTURES
    CL --> PL
    PL --> PERSONAS
    CG --> AOAI_SVC

    EC --> RS_DB
    EC --> RJSON
    SC --> SRJSON
    RS_DB --> SQLITE

    AOAI_SVC --> AAD
```

## Component Responsibilities

| Component | File(s) | Responsibility |
|-----------|---------|----------------|
| `EvalController` | `hlsharness/controller.py` | Run L1 eval for one agent: load cases → run agent → score → persist |
| `SolutionController` | `hlsharness/solution_controller.py` | Run L2 eval: iterate agents, apply DAG gate, rollup categories |
| `MAF Agent` | `cases/{agent}/agent.yaml` | Declarative agent definition (model, system prompt, tools) |
| `StubToolMiddleware` | `hlsharness/stub_middleware.py` | Intercept MAF tool calls → return fixtures → record trajectory |
| `Judge` | `hlsharness/judge.py` | Category-keyed scoring registry; lazy-initialize scorer instances |
| `BaseScorer` | `hlsharness/base_scorer.py` | 3-stage pipeline: veto → pre-check → LLM rubric |
| `CaseLoader` | `hlsharness/loader.py` | Parse YAML test case files into `TestCase` dataclasses |
| `CaseGenerator` | `hlsharness/generator.py` | LLM-powered generation of new test cases from agent.yaml |
| `PersonaLoader` | `hlsharness/persona_loader.py` | Load demographic persona profiles (equity testing) |
| `RunStore` | `hlsharness/run_store.py` | SQLite persistence of run history and baseline tracking |

## Key Architectural Decisions

### MAF YAML as Single Source of Truth
Each agent is defined in a `cases/{agent}/agent.yaml` file containing `name`, `description`, `system_prompt`, `tools`, and `x-harness` configuration. The harness reads this file to build the MAF agent and to validate that test cases reference only declared tools.

### Middleware Intercept (Zero Agent Code Changes)
`StubToolMiddleware` intercepts all MAF tool calls via `ContextVar`, substituting real tool execution with YAML fixtures. The agent code is unchanged and unaware of the stub layer.

### DAG Routing Gate (ADR 0003)
In L2 solution eval, agents declare `depends_on` in `solution.yaml`. The `SolutionController` excludes sub-agents from the rollup if their orchestrator's `functional` + `hitl_routing` categories fail threshold. This prevents cascading failures from inflating solution pass rates.

### No API Keys
All Azure OpenAI calls use `DefaultAzureCredential` + `get_bearer_token_provider()`. Token refresh is handled automatically. No secrets are stored in code, config, or CI environment variables beyond `AZURE_OPENAI_ENDPOINT`.
