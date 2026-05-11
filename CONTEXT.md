# HLS Harness — Domain Glossary

Terms meaningful to domain experts and architecture reviewers. Not coupled to implementation details.

---

## Core concepts

**Scoring Pipeline**
The three-stage process applied to every agent response before a score is recorded:
1. `must_not_contain` veto — deterministic string matching; match returns 0.0 immediately.
2. Pre-LLM check — optional category-specific check (e.g., PHI regex for privacy); match returns 0.0.
3. LLM rubric — probabilistic scoring by the judge model; returns 0.0–1.0 with plain-English rationale.

**Scorer**
A module that evaluates one dimension of agent behavior and returns a `JudgeResult` (score, passed, rationale). Each evaluation category has exactly one Scorer.

**Category**
An evaluation dimension: `functional`, `safety`, `privacy`, or `equity`. Each category has its own Scorer, YAML cases, pass-rate threshold, and scoring rubric.

**Category Author**
An engineer adding a new evaluation dimension to the harness. Their job: subclass `BaseScorer`, implement the rubric hook, write YAML cases.

**Tool Function Implementer**
The developer who writes real Python tool functions registered with a MAF Agent for production deployment. Distinct from the Architect — works from the tool definitions in the MAF YAML. No harness boilerplate; pure business logic. Replaces the former Adapter Author role.

**Architect**
A solutions architect onboarding a new HLS use case. Drives the three-phase onboarding flow: (1) spec → MAF YAML draft, (2) LLM Manifest Critique review + approval, (3) fixture library + test case generation. Hands the approved MAF YAML to a Tool Function Implementer and consumes Evaluation Reports as output.

**Category Registry**
A dict mapping category name → `BaseScorer` instance, owned and initialized by `Judge`. The registry is the single place that maps a category string to its scoring logic.

**Rubric Hook**
The abstract method `_build_prompt(case, response) -> str` that each concrete Scorer overrides to supply its category-specific LLM prompt. The only required customization point for a new Scorer.

**Pre-LLM Check Hook**
The optional method `_pre_llm_check(case, response) -> JudgeResult | None` on `BaseScorer`. Defaults to `None` (no-op). Overridden only by scorers that need a deterministic check between `must_not_contain` and the LLM call (e.g., PHI regex in `PrivacyGuard`).

**Upfront Validation**
Case-list validation performed once in `EvalController.run()` before the eval loop starts. Checks that `tool_responses` keys match tool names in the MAF Agent YAML, and that equity cases have required metadata keys (`patient_age`, `language`, `insurance`). All config errors surface together, not mid-run.

**Evaluation Report**
A PDF artifact produced by `hls-eval --pdf` after a run. Structured as: cover page (agent name, date, overall verdict) → summary table → failed cases with judge rationale. Primary sharing artifact for clinical directors and compliance officers who do not run the harness themselves. Configurable branding via `report_config.yaml`.

**ReportConfig**
Immutable dataclass loaded from an optional `report_config.yaml`. Fields: `org` (organization name), `brand_color` (hex), `title_template` (supports `{agent}` and `{date}` placeholders). Defaults to `"Contoso Health"`, `"#0D3B66"`, and `"{agent} — AI Quality Evaluation"`. Unknown YAML keys are silently ignored for forward compatibility.

---

## MAF / Foundry integration concepts

**MAF Agent**
A declarative agent definition in Microsoft Agent Framework format (YAML). The single authoritative artifact for agent identity, tool definitions, model config, system prompt, and harness evaluation metadata. Replaces the former `manifest.yaml` + Python adapter stub pair. Deployed to Azure AI Foundry for production; loaded locally by EvalController for eval runs.

**x-harness extension block**
A custom extension namespace (`x-harness:`) embedded in the MAF Agent YAML. Carries eval-specific metadata: category list, pass-rate thresholds, persona references. Ignored by MAF runtime; read by EvalController and CaseGenerator.

**StubToolMiddleware**
A MAF middleware component injected by EvalController at eval time. Intercepts tool dispatch before real tool function implementations execute. Reads scripted responses from a `ContextVar` set per test case; records every call as a trajectory entry. Replaces `ToolSimulator`. Not present in production Foundry deployments.

**Manifest Critique**
An LLM-generated deep behavioral review of a draft MAF Agent YAML produced during onboarding Phase 2. Reasons about completeness and safety: missing error-path tool responses, ambiguous parameter schemas, tool descriptions that under-constrain agent behavior, threshold values inconsistent with the agent's risk profile. Presented alongside the draft for Architect review before Phase 3.

**Fixture Library**
Named, reusable tool response scenarios stored in `stubs/{agent}/{tool_name}/` as YAML files (e.g., `no_availability.yaml`, `confirmed.yaml`). Generated per-tool by CaseGenerator from the MAF Agent YAML tool schemas. Test cases reference scenarios by name; Architects can review and edit the library independently of cases. Supplemented by per-case inline `tool_responses` for edge cases.

**Persona Library**
Shared domain persona definitions stored in `personas/` as typed YAML files. Each persona captures healthcare-relevant dimensions: `id`, `age`, `language`, `insurance`, `location`, `care_context`. Referenced by test cases via `persona:` ID. Reusable across agents — the same persona exercises equity behavior consistently in scheduling-v1 and prior-auth-v1 without copy-paste.

**Upfront Validation**
Case-list validation performed once in `EvalController.run()` before the eval loop starts. Checks that `tool_responses` keys (inline or resolved from Fixture Library) match tool names in the MAF Agent YAML, and that equity cases have required metadata keys (`patient_age`, `language`, `insurance`). All config errors surface together, not mid-run.
