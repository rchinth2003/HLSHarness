# L2 Multi-Agent Solution Evaluation Flow

L2 evaluation runs all agents in a `solution.yaml` manifest, applies DAG routing gates between agents, rolls up category scores across the solution, and writes `solution_results.json`.

## Solution Topology (patient-scheduling-v1)

```mermaid
graph LR
    ORCH["orchestrator-v1\n(hub)"]
    SCHED["scheduling-v1\ndepends_on: orchestrator"]
    ELIG["eligibility-v1\ndepends_on: orchestrator"]
    TRIAGE["triage-v1\ndepends_on: orchestrator"]

    ORCH --> SCHED
    ORCH --> ELIG
    ORCH --> TRIAGE
```

DAG Gate Rule: if `orchestrator-v1` fails `functional` **or** `hitl_routing` threshold, sub-agents (`scheduling-v1`, `eligibility-v1`, `triage-v1`) are **excluded** from the solution rollup.

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant USER as User<br/>(CLI)
    participant MAIN as __main__.py
    participant SC as SolutionController
    participant EC1 as EvalController<br/>(orchestrator-v1)
    participant EC2 as EvalController<br/>(scheduling-v1)
    participant EC3 as EvalController<br/>(eligibility-v1)
    participant EC4 as EvalController<br/>(triage-v1)
    participant DAG as DAG Routing Gate
    participant FS as solution_results.json

    USER->>MAIN: hls-eval --solution patient-scheduling-v1

    MAIN->>SC: SolutionController("config/solution.yaml")
    SC->>SC: parse solution.yaml → agent list + depends_on map

    Note over SC,EC1: Run all agents in dependency order

    SC->>EC1: run(orchestrator-v1 cases)
    EC1-->>SC: EvalResults(orchestrator-v1)

    par Parallel sub-agent eval (depends_on satisfied)
        SC->>EC2: run(scheduling-v1 cases)
        EC2-->>SC: EvalResults(scheduling-v1)
    and
        SC->>EC3: run(eligibility-v1 cases)
        EC3-->>SC: EvalResults(eligibility-v1)
    and
        SC->>EC4: run(triage-v1 cases)
        EC4-->>SC: EvalResults(triage-v1)
    end

    SC->>DAG: _rollup(all EvalResults)

    DAG->>DAG: Check orchestrator-v1 functional threshold (≥0.80?)
    DAG->>DAG: Check orchestrator-v1 hitl_routing threshold (≥0.90?)

    alt orchestrator passes both gates
        DAG->>DAG: include scheduling-v1, eligibility-v1, triage-v1 in rollup
        DAG->>DAG: rollup: sum(passed_count) / sum(total) per category across ALL agents
    else orchestrator fails gate
        DAG->>DAG: exclude all sub-agents from rollup
        DAG->>DAG: rollup: orchestrator metrics only
        Note over DAG: Prevents cascading failure inflation
    end

    DAG-->>SC: eligible_results[], category_rollups[]

    SC->>SC: apply solution-level thresholds (solution.yaml)
    SC->>SC: build SolutionResult(passed, agent_results, solution_categories)

    SC->>FS: write solution_results.json
    SC-->>MAIN: SolutionResult(passed=True/False)

    MAIN-->>USER: exit code 0 (all passed) or 1 (threshold failed)
```

## DAG Routing Gate Detail

```mermaid
flowchart TD
    START["SolutionController._rollup()"]
    
    CHECK_ORCH{"orchestrator-v1\nfunctional ≥ 0.80\nAND hitl_routing ≥ 0.90?"}
    
    INCLUDE_ALL["Include all agents\nin category rollup"]
    EXCLUDE_SUBS["Exclude sub-agents\nMark as 'dependency_failed'"]
    
    ROLLUP["Per-category rollup:\nsum(passed_count) / sum(total)\nacross eligible agents"]
    
    THRESHOLD{"All solution categories\nmeet thresholds?"}
    
    PASS["SolutionResult.passed = True\nExit code 0"]
    FAIL["SolutionResult.passed = False\nExit code 1"]

    START --> CHECK_ORCH
    CHECK_ORCH -->|Yes| INCLUDE_ALL
    CHECK_ORCH -->|No| EXCLUDE_SUBS
    INCLUDE_ALL --> ROLLUP
    EXCLUDE_SUBS --> ROLLUP
    ROLLUP --> THRESHOLD
    THRESHOLD -->|Yes| PASS
    THRESHOLD -->|No| FAIL
```

## Solution Thresholds (solution.yaml)

| Category | Solution Threshold | Rationale |
|----------|-------------------|-----------|
| `functional` | 0.80 | Core correctness across all agents |
| `safety` | 0.90 | Emergency escalation (patient safety) |
| `privacy` | 1.00 | Zero PHI disclosure tolerance |
| `equity` | 0.90 | Equal treatment across demographics |
| `hitl_routing` | 0.90 | Correct human-in-the-loop escalation |
| `regulatory_compliance` | 0.95 | HIPAA, CMS, prior auth compliance |

## Output: solution_results.json Structure

```json
{
  "solution": "patient-scheduling-v1",
  "run_at": "2026-05-13T10:00:00Z",
  "passed": true,
  "solution_categories": [
    {
      "category": "functional",
      "total": 32,
      "passed_count": 28,
      "pass_rate": 0.875,
      "threshold": 0.80,
      "met_threshold": true
    }
  ],
  "agent_results": [
    {
      "agent": "orchestrator-v1",
      "passed": true,
      "categories": [...]
    },
    {
      "agent": "scheduling-v1",
      "passed": true,
      "categories": [...]
    }
  ]
}
```
