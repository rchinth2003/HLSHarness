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
An evaluation dimension: `functional`, `safety`, `privacy`, `equity`, `urgency_triage`, `regulatory_compliance`, or `hitl_routing`. Each category has its own Scorer, YAML cases, pass-rate threshold, and scoring rubric.

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

---

## Multi-agent and drift concepts

**Solution**
A named multi-agent workflow composed of two or more MAF agents that must collectively satisfy quality thresholds. Described by a `solution.yaml` manifest and evaluated by `SolutionController`. Distinct from a single-agent eval run.

**Solution Manifest**
The `solution.yaml` file that declares which agents belong to a Solution, whether each runs live or in stub mode, and the L2 solution-level pass-rate thresholds. Generated by `SolutionInterpreter` from individual `agent.yaml` files; reviewed and approved by the Architect before the first solution eval run.

**SolutionController**
The orchestrator that drives L3 evaluation: runs L1 `EvalController` for each agent in the Solution, then aggregates per-category pass rates into an L2 `SolutionResult`. Writes both per-agent `results.json` and a top-level `solution_results.json`. Implements a DAG routing gate: agents declaring `depends_on` are excluded from the L2 rollup if any named dependency's `functional` or `hitl_routing` category failed threshold.

**L1 Evaluation**
A single-agent eval run driven by `EvalController`. Produces an `EvalResults` with per-case scores, per-category `CategorySummary`, and an overall pass/fail verdict. The atomic unit of harness measurement.

**L2 Evaluation**
The solution-level aggregation step performed by `SolutionController`. Averages L1 per-category pass rates across all eligible agents in the Solution; applies solution-level thresholds to determine whether the Solution as a whole passes. Agents excluded by the DAG routing gate do not contribute to pass or fail counts.

**Routing Dependency**
A declared dependency between agents in `solution.yaml` via `agents[].depends_on`. When agent B depends on agent A, `SolutionController` checks whether agent A's `functional` and `hitl_routing` categories both met threshold before including agent B's scores in the L2 rollup.

**DAG Rollup**
The scoring algorithm in `SolutionController._rollup()` that walks the agent dependency graph before aggregating scores. Agents whose routing dependencies were not satisfied are excluded (not failed) from the L2 rollup — their scores neither inflate nor deflate the solution-level result.

**L3 Evaluation**
The full end-to-end evaluation run for a multi-agent Solution: L1 per-agent evals followed by L2 solution rollup in a single `hls-eval --solution` invocation. The term used in ARCHITECT_GUIDE and issue tracker to refer to the complete three-layer measurement pipeline.

**RunStore**
The SQLite persistence layer (`hlsharness/run_store.py`) that records every `EvalResults` run for an agent. Supports baseline promotion (D1 auto / D2 human), run history retrieval, per-case pass/fail storage, and delta computation. Powers the dashboard Run History and Delta View panels.

**Baseline**
A designated `RunRecord` in `RunStore` that serves as the reference point for regression detection. Promoted either automatically by CI on passing main-branch runs (D1) or manually by the Architect via the dashboard (D2). Only one baseline is active per agent/version at a time.

**Regression Drift**
A statistically meaningful decrease in a category's pass rate between the current run and the designated baseline. Surfaced as a negative delta in the CI report and as a red delta cell in the dashboard Delta View. The CI gate exits with code `3` when any category regresses beyond its delta threshold.

**Delta Threshold**
The maximum allowable decrease in a category's pass rate from baseline before the CI gate signals a regression (exit code `3`). Configured per-category in `hls-eval` CI flags (e.g., `--delta-threshold 0.05`). Distinct from the absolute pass-rate threshold — a run can pass its absolute threshold while still triggering a delta regression.

**UrgencyTriageScorer**
A domain scorer (`hlsharness/urgency_triage.py`) that evaluates whether an HLS agent correctly identifies and escalates clinical urgency signals (e.g., chest pain, shortness of breath) in patient messages. Uses a multi-tier rubric: immediate escalation, same-day escalation, routine scheduling, or inappropriate dismissal.

**RegulatoryComplianceScorer**
A domain scorer (`hlsharness/regulatory_compliance.py`) that evaluates whether an HLS agent's responses comply with applicable regulatory requirements — HIPAA privacy language, prior authorization disclosures, scope-of-practice boundaries, and referral obligations. Flags any response that asserts clinical judgments outside the agent's permitted role.

**HITLRoutingScorer**
A domain scorer (`hlsharness/hitl_routing.py`) that evaluates whether an orchestrator agent correctly detects and routes structured escalation signals emitted by sub-agents. Uses a two-stage pipeline: Stage 1 is a structural pre-LLM check validating signal shape (`escalate`, `reason`, `confidence` fields) and that `reason` is in `VALID_REASON_CODES`; partial credit (0.5) awarded on reason code mismatch. Stage 2 is the LLM rubric assessing routing correctness.

**VALID_REASON_CODES**
The closed set of permitted `reason` values in a HITL escalation signal: `{"ambiguous_intent", "eligibility_failure", "no_available_slots", "red_flag_symptom", "late_cancellation_policy"}`. Defined in `hlsharness/hitl_routing.py`. Signals with a reason code outside this set receive score 0.0 from the structural pre-check.

---

## PatSch Implementation Status

### Slice 0 — Harness Foundation (Complete)

| Issue | Title | PR | Status |
|-------|-------|----|--------|
| #97 | HITL routing scorer | #97 | Merged |
| #98 | Solution manifest + DAG | #98 | Merged |
| #99 | Docs: hitl_routing + DAG rollup | #99 | Merged |

**Added to HLSHarness:**
- `hlsharness/hitl_routing.py` — `HITLRoutingScorer`; `VALID_REASON_CODES`
- `hlsharness/solution_manifest.py` — `AgentEntry.depends_on`; `AgentEntry.case_dir`
- `hlsharness/solution_controller.py` — DAG-aware `_rollup()`; `case_dir`-aware path resolution
- `config/solution.yaml` — `patient-scheduling-v1`: 4 agents, hub-and-spoke topology
- `docs/adr/patsch/` — ADRs 0001–0003

### Slice 1 — MVE: Slot Search + Intent Capture (Complete)

| Issue | Title | PR | Status |
|-------|-------|----|--------|
| #100 | AgentEntry.case_dir + SolutionController path resolution | #103 | Merged |
| #101 | Orchestrator agent definition + 5 test cases | #104 | Merged |
| #102 | Eligibility agent + 3 stub fixtures + 4 test cases | #105 | Merged |
| #106 | PatSch monorepo migration | #106 | Merged |
| #110 | Scheduling Agent | #118 | Merged |
| #112 | Slice 1 eval suites + harness baseline | #119 | Merged |

**Added to HLSHarness:**
- `cases/orchestrator-v1/agent.yaml` — categories: `functional`, `hitl_routing`
- `cases/orchestrator-v1/functional/` — TC-O-001, TC-O-005
- `cases/orchestrator-v1/hitl_routing/` — TC-O-002, TC-O-003, TC-O-004
- `cases/eligibility-v1/agent.yaml` — tool: `check_eligibility`; categories: `functional`, `privacy`
- `cases/eligibility-v1/functional/` — TC-E-001/002/003
- `cases/eligibility-v1/privacy/` — TC-E-004
- `stubs/eligibility-v1/check_eligibility/` — covered, not_covered, prior_auth_required
- `cases/scheduling-v1/agent.yaml` — model: `gpt-5.4-nano`; tools: `search_available_slots`, `book_appointment`, `cancel_appointment`, `get_patient_record`; categories: `functional`, `equity`; 10 personas
- `cases/scheduling-v1/functional/` — TC-S-001 (slot found), TC-S-002 (booking confirmed), TC-S-003 (no-slots HITL escalation), TC-S-004 (multi-provider)
- `cases/scheduling-v1/equity/` — TC-S-EQ-001..010 (one per persona)
- `stubs/scheduling-v1/search_available_slots/` — full_slots, no_availability, multi_provider
- `personas/medicare_spanish_elderly.yaml` — 10th harness persona
- `tests/test_orchestrator_v1_cases.py` — 32 structural assertions
- `tests/test_eligibility_v1_cases.py` — 32 structural assertions
- `tests/test_patsch_solution_manifest.py` — 9 manifest tests
- `tests/test_slice1_agent_definitions.py` — 14 structural tests
- `tests/test_scheduling_v1_cases.py` — 105 structural assertions
- `tests/test_e2e_solution.py` — 12 SolutionController wiring tests (real PatSch manifest, DAG gate, RunStore, triage empty-categories)
- `tests/test_hitl_propagation.py` — 14 HITL signal propagation tests (TC-O-002/003/004 vs. HITLRoutingScorer._pre_llm_check)

**Coverage:** 633 passed, 1 skipped (triage-v1, Slice 3)

---

### Slice 2 — Reschedule + Waitlist Management (Complete)

| Issue | Title | PR | Status |
|-------|-------|----|--------|
| #122 | agent.yaml: reschedule/waitlist tools + hitl_routing category | #127 | Merged |
| #123 | 5 new stubs: rescheduled, reschedule_no_slots, notified, no_slot, late_cancelled | #127 | Merged |
| #124 | Functional + hitl_routing cases: TC-S-005–008, TC-S-HIT-001–003 | #127 | Merged |
| #125 | Equity cases: TC-S-EQ-011–014 | #127 | Merged |
| #126 | test_loader.py: count assertions + 3 fixture resolution tests | #127 | Merged |

**Added to HLSHarness:**
- `cases/scheduling-v1/agent.yaml` — added `reschedule_appointment`, `check_and_notify_waitlist` tools; `hitl_routing` category (threshold 0.90); system prompt rules 8–10; `late_cancellation` flag in `cancel_appointment` description
- `stubs/scheduling-v1/reschedule_appointment/` — rescheduled, reschedule_no_slots
- `stubs/scheduling-v1/check_and_notify_waitlist/` — notified, no_slot
- `stubs/scheduling-v1/cancel_appointment/late_cancelled.yaml`
- `cases/scheduling-v1/functional/` — TC-S-005 (reschedule success), TC-S-006 (reschedule no-slots HITL), TC-S-007 (late cancellation HITL), TC-S-008 (waitlist notified)
- `cases/scheduling-v1/hitl_routing/` — TC-S-HIT-001 (late_cancellation_policy), TC-S-HIT-002 (no_available_slots / no-slots), TC-S-HIT-003 (no_available_slots / reschedule)
- `cases/scheduling-v1/equity/` — TC-S-EQ-011..014 (reschedule + waitlist across medicaid, medicare, uninsured, commercial/disability personas)
- `hlsharness/hitl_routing.py` — added `no_available_slots` to `VALID_REASON_CODES`

**Coverage:** 696 passed, 1 skipped (triage-v1, Slice 3), 93.9%
