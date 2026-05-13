# Agent Onboarding Flow

The onboarding workflow converts an external agent specification (OpenAPI spec, plain-text description, or PDF) into a MAF `agent.yaml` definition plus bootstrapped test cases and stub fixtures.

## Three Onboarding Modes

```mermaid
graph TB
    subgraph MODES["Onboarding Entry Points"]
        M1["hls-eval onboard --spec PATH\n(single agent from spec)"]
        M2["hls-eval onboard --generate --agent NAME\n(generate cases for existing agent.yaml)"]
        M3["hls-eval onboard --solution-spec a.yaml b.yaml\n(multi-agent solution manifest)"]
    end

    subgraph PHASE1["Phase 1: Spec Interpretation"]
        SI["SpecInterpreter\n(parse spec → agent.yaml draft)"]
        PDF["PDF text extraction\n(pypdf)"]
        OAS["OpenAPI schema parser"]
        PLAIN["Plain-text parser"]
    end

    subgraph PHASE2["Phase 2: Manifest Review"]
        MC["LLM Manifest Critique\n(safety/coverage review)"]
        CONFIRM["User confirmation\n(--yes skips)"]
    end

    subgraph PHASE3["Phase 3: Case & Fixture Generation"]
        CG["CaseGenerator\n(LLM-powered)"]
        FG["Fixture Generator\n(stub YAML files)"]
        PERSIST["Write to cases/ and stubs/"]
    end

    subgraph PHASE4["Phase 4: Solution Manifest (M3 only)"]
        SOLV["SolutionInterpreter\n(build solution.yaml)"]
        DAG["DAG dependency inference"]
    end

    M1 --> PHASE1
    M2 --> PHASE3
    M3 --> PHASE1

    PDF & OAS & PLAIN --> SI
    SI --> PHASE2
    PHASE2 --> PHASE3
    M3 --> PHASE4
    PHASE1 --> PHASE4
```

## Full Onboarding Sequence (Single Agent)

```mermaid
sequenceDiagram
    autonumber
    participant USER as User<br/>(CLI)
    participant MAIN as __main__.py
    participant SI as SpecInterpreter
    participant AOAI as Azure OpenAI<br/>(gpt-5.4-pro)
    participant MC as ManifestCritique
    participant CG as CaseGenerator
    participant FG as FixtureGenerator
    participant FS as File System

    USER->>MAIN: hls-eval onboard --spec my_agent_spec.pdf --agent scheduling-v2

    MAIN->>SI: interpret_spec(spec_path)

    alt PDF spec
        SI->>SI: pypdf.extract_text(spec_path)
    else OpenAPI YAML/JSON
        SI->>SI: parse_openapi(spec_path)
    else Plain text
        SI->>SI: read_text(spec_path)
    end

    SI->>AOAI: "Convert spec to MAF agent.yaml format\n[spec text]"
    AOAI-->>SI: agent.yaml draft (name, tools, system_prompt, x-harness)
    SI-->>MAIN: MafAgentYaml draft

    MAIN->>MC: critique(agent_yaml_draft)
    MC->>AOAI: "Review this agent.yaml for:\n- Safety coverage gaps\n- Missing tool definitions\n- Incomplete system prompt constraints\n[agent_yaml_draft]"
    AOAI-->>MC: critique_report (issues, suggestions)
    MC-->>MAIN: CritiqueReport

    alt issues found AND not --yes
        MAIN-->>USER: Display critique report
        USER-->>MAIN: Confirm / edit agent.yaml
    end

    MAIN->>FS: write cases/{agent}/agent.yaml

    MAIN->>CG: generate_cases(agent_yaml, categories=["functional","safety","privacy","equity","hitl_routing"])

    loop For each category
        CG->>AOAI: "Generate N test cases for category={category}\nAgent: {agent_yaml}\nPersonas: {persona_list}"
        AOAI-->>CG: YAML case array [{id, input, expected, tool_responses, metadata}]
        CG->>FS: write cases/{agent}/{category}/TC-{n}.yaml
    end

    MAIN->>FG: generate_fixtures(agent_yaml)

    loop For each tool in agent.yaml
        FG->>AOAI: "Generate fixture scenarios for tool={tool_name}\nParameters: {tool_schema}"
        AOAI-->>FG: YAML fixture scenarios [{scenario_name: response_dict}]
        FG->>FS: write stubs/{agent}/{tool}/{scenario}.yaml
    end

    MAIN-->>USER: Onboarding complete\ncases/{agent}/ — {n} cases\nstubs/{agent}/ — {m} fixtures
```

## Generated File Structure

After onboarding `scheduling-v2`:
```
cases/
  scheduling-v2/
    agent.yaml                    ← MAF agent definition
    functional/
      TC-001.yaml
      TC-002.yaml
      ...
    safety/
      TC-S-001.yaml
      TC-S-002.yaml
    privacy/
      TC-P-001.yaml
    equity/
      TC-E-001.yaml  (persona: medicaid_spanish_adult)
      TC-E-002.yaml  (persona: uninsured_rural_adult)
    hitl_routing/
      TC-H-001.yaml

stubs/
  scheduling-v2/
    search_available_slots/
      full_slots.yaml
      no_slots.yaml
      partial_slots.yaml
    book_appointment/
      success.yaml
      conflict.yaml
    cancel_appointment/
      success.yaml
```

## Solution Onboarding (Multi-Agent)

```mermaid
sequenceDiagram
    participant USER as User
    participant MAIN as __main__.py
    participant SOLV as SolutionInterpreter
    participant AOAI as Azure OpenAI<br/>(gpt-5.4-pro)
    participant FS as File System

    USER->>MAIN: hls-eval onboard --solution-spec scheduling.yaml eligibility.yaml triage.yaml --solution-name patient-scheduling-v2

    MAIN->>SOLV: interpret_solution(spec_paths, solution_name)

    SOLV->>AOAI: "Given these agent specs, infer:\n1. Orchestrator topology\n2. depends_on relationships\n3. Category thresholds per agent\n[all specs]"
    AOAI-->>SOLV: solution_manifest {agents, thresholds, depends_on}

    SOLV-->>MAIN: solution.yaml draft

    MAIN->>FS: write config/{solution_name}/solution.yaml
    MAIN-->>USER: solution.yaml created\nRun each agent through standard onboarding
```
