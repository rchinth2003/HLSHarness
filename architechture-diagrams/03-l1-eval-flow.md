# L1 Single-Agent Evaluation Flow

L1 evaluation runs a single agent (`--agent scheduling-v1`) against all its test cases, scores each case, aggregates category summaries, and writes `results.json`.

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant USER as User<br/>(CLI)
    participant MAIN as __main__.py<br/>hls-eval
    participant EC as EvalController
    participant CL as CaseLoader
    participant BUILD as build_maf_agent()
    participant MAF as MAF Agent
    participant STUB as StubToolMiddleware
    participant AOAI_A as Azure OpenAI<br/>(gpt-5.4-nano / agent)
    participant JUDGE as Judge
    participant AOAI_J as Azure OpenAI<br/>(gpt-5.4-pro / judge)
    participant RS as RunStore<br/>(SQLite)
    participant FS as File System<br/>(results.json)

    USER->>MAIN: hls-eval --agent scheduling-v1 --cases cases/scheduling-v1/

    MAIN->>CL: load_cases(cases_dir, agent="scheduling-v1")
    CL->>CL: glob *.yaml case files
    CL->>CL: parse YAML → TestCase[]
    CL->>CL: validate tool names against agent.yaml
    CL-->>MAIN: TestCase[n]

    MAIN->>EC: EvalController(agent="scheduling-v1", cases)

    loop For each TestCase
        EC->>BUILD: build_maf_agent("cases/scheduling-v1/agent.yaml")
        BUILD->>BUILD: parse agent.yaml → MafAgentYaml
        BUILD->>BUILD: create OpenAIChatClient(Azure, DefaultAzureCredential)
        BUILD->>BUILD: attach StubToolMiddleware
        BUILD-->>EC: MAF Agent

        EC->>STUB: set_tool_responses(case.tool_responses) via ContextVar

        EC->>MAF: agent.run(case.input.messages)

        MAF->>AOAI_A: chat.completions.create(system_prompt, messages)
        AOAI_A-->>MAF: tool_call: search_available_slots({provider_id, date_range})

        MAF->>STUB: call_tool("search_available_slots", args)
        STUB->>STUB: lookup fixture from ContextVar
        STUB->>STUB: record ToolCall(turn, name, args, response) in trajectory
        STUB-->>MAF: fixture response (slot list)

        MAF->>AOAI_A: chat.completions.create(tool_result appended)
        AOAI_A-->>MAF: tool_call: book_appointment({slot_id, patient_id})

        MAF->>STUB: call_tool("book_appointment", args)
        STUB->>STUB: record ToolCall in trajectory
        STUB-->>MAF: fixture response (confirmation_id)

        MAF->>AOAI_A: chat.completions.create(tool_result appended)
        AOAI_A-->>MAF: final text response to patient

        MAF-->>EC: AgentResponse(text, trajectory[])

        EC->>JUDGE: score(case.category, case, agent_response)
        JUDGE->>AOAI_J: category rubric prompt + trajectory
        AOAI_J-->>JUDGE: {"score": 0.92, "rationale": "..."}
        JUDGE-->>EC: JudgeResult(score=0.92, passed=true)

        EC->>EC: append CaseResult(case_id, score, trajectory, latency_ms, ...)
    end

    EC->>EC: aggregate CategorySummary[] (pass_rate per category)
    EC->>EC: determine overall passed (all thresholds met?)
    EC->>EC: build EvalResults

    EC->>RS: persist(EvalResults)
    RS->>RS: INSERT run into SQLite

    EC->>FS: write results.json
    EC-->>MAIN: EvalResults(passed=True/False)

    MAIN-->>USER: exit code 0 (passed) or 1 (failed threshold)
```

## Inputs & Outputs

### Inputs
| Input | Location | Format |
|-------|----------|--------|
| Test cases | `cases/{agent}/**/*.yaml` | YAML → `TestCase` |
| Agent definition | `cases/{agent}/agent.yaml` | MAF YAML |
| Tool fixtures | `stubs/{agent}/{tool}/{scenario}.yaml` | YAML dict |
| Personas | `personas/{id}.yaml` | YAML → `Persona` |
| Thresholds | `cases/{agent}/agent.yaml` `x-harness.thresholds` | Per-category floats |

### Outputs
| Output | Location | Format |
|--------|----------|--------|
| Per-case results | `results.json` | JSON array of `CaseResult` |
| Category summaries | `results.json` | JSON array of `CategorySummary` |
| Run history | `.hls_runs.db` | SQLite row |
| Exit code | process | 0=pass, 1=fail, 2=config error, 3=regression |

## EvalController Internal State Machine

```mermaid
stateDiagram-v2
    [*] --> LoadCases
    LoadCases --> ValidateCases : cases loaded
    ValidateCases --> BuildAgent : validation OK
    ValidateCases --> ConfigError : unknown tool / missing persona
    BuildAgent --> RunCase : agent built
    RunCase --> ScoreCase : agent response received
    ScoreCase --> RunCase : more cases remaining
    ScoreCase --> Aggregate : all cases done
    Aggregate --> Persist : summaries computed
    Persist --> [*] : results.json + SQLite written
    ConfigError --> [*] : exit code 2
```
