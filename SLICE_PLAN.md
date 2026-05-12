# HLS Harness — Slice Plan

Complete record of all slices: entry conditions, deliverables, exit results, and GitHub references.

---

## How to read this document

Each slice entry records:
- **Entry condition** — what must be true before the slice starts (merged PRs, green CI)
- **Deliverables** — what the slice produces
- **Exit results** — what was actually shipped (PR, CI status, test count, coverage)
- **GitHub refs** — PR number, issue number

---

## Historical slices (Slices 1–11) — all merged to `main`

### Slice 1 — Project scaffold: AgentAdapter, ToolSimulator, CaseLoader

| Field | Value |
|-------|-------|
| **PRD** | — (pre-PRD era) |
| **Issue** | #13 |
| **PR** | #1 |
| **Branch** | `slice/1-scaffold` |
| **Entry** | Empty repo with initial commit |
| **Deliverables** | `AgentAdapter`, `ToolDefinition`, `AgentResponse`, `ToolSimulator`, `CaseLoader`, `VALID_CATEGORIES`, unit tests |
| **CI result** | ✅ Green |
| **Exit** | Foundation data model and contracts in place; all later slices build on this |

---

### Slice 2 — Eval controller, Judge, Scorer protocol, MetricCollector, EvalResults

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #14 |
| **PR** | #2 |
| **Branch** | `slice/2-controller` |
| **Entry** | Slice 1 merged |
| **Deliverables** | `EvalController`, `Scorer` protocol (4-method), `Judge`, `MetricCollector`, `EvalResults`, `CategorySummary`, `CaseResult`, `harness.py run` CLI, `results.json` output |
| **CI result** | ✅ Green |
| **Exit** | Full eval pipeline working end-to-end for functional category |

---

### Slice 3 — Streamlit dashboard: category scorecards and case detail view

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #15 |
| **PR** | #3 |
| **Branch** | `slice/3-dashboard` |
| **Entry** | Slice 2 merged |
| **Deliverables** | `dashboard/app.py`, category pass-rate gauges, case detail view (input, response, trajectory, score, rationale), filter by category/failed |
| **CI result** | ✅ Green |
| **Exit** | Stakeholders can explore eval results interactively without reading JSON |

---

### Slice 4 — LLM-powered YAML case generator CLI

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #16 |
| **PR** | #4 |
| **Branch** | `slice/4-generator` |
| **Entry** | Slice 2 merged |
| **Deliverables** | `CaseGenerator`, `harness.py generate` subcommand, `llm_fn` injectable seam, YAML output validated by `CaseLoader` |
| **CI result** | ✅ Green |
| **Exit** | Engineers can draft new test cases from the CLI without writing YAML by hand |

---

### Slice 5 — Safety category: SafetyEscalator, 6 cases, 19 tests

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #17 |
| **PR** | #5 |
| **Branch** | `slice/5-safety` |
| **Entry** | Slice 2 merged |
| **Deliverables** | `SafetyEscalator`, `score_safety()` on Scorer + Judge, 6 safety YAML cases, 19 unit tests, 90% pass-rate threshold |
| **CI result** | ✅ Green |
| **Exit** | Safety scoring live; cardiac emergency, stroke, medication advice cases all covered |

---

### Slice 6 — Privacy category: PrivacyGuard + PHI regex, 6 cases, 21 tests

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #18 |
| **PR** | #6 |
| **Branch** | `slice/6-privacy` |
| **Entry** | Slice 5 merged |
| **Deliverables** | `PrivacyGuard`, PHI regex (SSN + MRN), `score_privacy()`, 6 privacy YAML cases, 21 unit tests, 100% pass-rate threshold |
| **CI result** | ✅ Green |
| **Exit** | Privacy scoring live with deterministic pre-LLM PHI detection |

---

### Slice 7 — Equity category: EquityAnalyzer + demographics, 6 cases, 22 tests

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #19 |
| **PR** | #7 |
| **Branch** | `slice/7-equity` |
| **Entry** | Slice 6 merged |
| **Deliverables** | `EquityAnalyzer`, `_build_demographics()`, `score_equity()`, 6 equity YAML cases, 22 unit tests, 90% pass-rate threshold |
| **CI result** | ✅ Green |
| **Exit** | All four evaluation dimensions live; equity covers Medicaid, language, age, disability |

---

### Slice 8 — Full 30-case demo suite, hls-eval CLI, threshold-gated exit code

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #20 |
| **PR** | #8 |
| **Branch** | `slice/8-demo-suite` |
| **Entry** | Slice 7 merged |
| **Deliverables** | 30 YAML cases (functional 3, safety 9, privacy 9, equity 9), `hlsharness/__main__.py`, `hls-eval` pyproject.toml script, exit codes 0/1/2, mypy adapter override, `tests/test_main.py` |
| **CI result** | ✅ Green |
| **Coverage** | 88.9% |
| **Exit** | `uv run hls-eval` runs the full 30-case suite with threshold-gated exit code |

---

### Slice 9 — Developer README: quickstart, architecture, extension guides

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #21 |
| **PR** | #9 |
| **Branch** | `slice/9-readme` |
| **Entry** | Slice 8 merged |
| **Deliverables** | `README.md` — prerequisites, 6-step quickstart, ASCII project layout, core concepts (YAML schema, adapter pattern, scoring pipeline diagram), CI table, contribution guidelines |
| **CI result** | ✅ Green |
| **Exit** | Any engineer who clones the repo can get to a running eval in under 10 minutes |

---

### Slice 10 — Architect guide + PriorAuthAdapter reference implementation

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #22 |
| **PR** | #10 |
| **Branch** | `slice/10-architect-guide` |
| **Entry** | Slice 9 merged |
| **Deliverables** | `ARCHITECT_GUIDE.md` (2 ASCII diagrams, component table, 5-step walkthrough, design decisions, 10-step new-category checklist, troubleshooting), `hlsharness/adapters/prior_auth.py`, `prior-auth-v1` registry entry |
| **CI result** | ✅ Green |
| **Exit** | Adapter authors and category authors have a step-by-step guide backed by a working reference implementation |

---

### Slice 11 — Stakeholder demo guide: scenarios, scoring, dashboard walkthrough

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issue** | #23 |
| **PR** | #11 |
| **Branch** | `slice/11-demo-guide` |
| **Entry** | Slice 10 merged |
| **Deliverables** | `DEMO_GUIDE.md` — 4 evaluation dimensions in plain English, 4 real scenario walkthroughs, 5-step failure protocol, 5-minute demo script, 13-term glossary |
| **CI result** | ✅ Green |
| **Exit** | Clinical directors, compliance officers, and PMs can evaluate and present the harness without engineering support |

---

## Completed slices (Slices 12A–12F) — extensibility refactor

**PRD:** [#24 — Harness extensibility refactor — BaseScorer, category registry, upfront validation](https://github.com/rchinth2003/HLSHarness/issues/24)

**ADR:** `docs/adr/0001-collapse-scorer-protocol.md`

---

### Slice 12A — Extract BaseScorer: shared pipeline, rubric hook, pre-LLM hook

| Field | Value |
|-------|-------|
| **Issue** | #25 | **PR** | #31 |
| **CI result** | ✅ Green |
| **Exit** | `hlsharness/base_scorer.py` with `BaseScorer`; `tests/test_base_scorer.py` |

---

### Slice 12B — Thin three scorers: inherit BaseScorer, delete copy-paste

| Field | Value |
|-------|-------|
| **Issue** | #26 | **PR** | #32 |
| **CI result** | ✅ Green |
| **Exit** | `SafetyEscalator`, `PrivacyGuard`, `EquityAnalyzer` thinned; ~60 lines of copy-paste deleted per scorer |

---

### Slice 12C — Judge registry + Scorer protocol collapse + remove elif chain

| Field | Value |
|-------|-------|
| **Issue** | #27 | **PR** | #33 |
| **CI result** | ✅ Green |
| **Exit** | Single `score()` method on `Scorer` protocol; `Judge` category registry; elif chain eliminated |

---

### Slice 12D — Delete MetricCollector, inline CaseMetrics

| Field | Value |
|-------|-------|
| **Issue** | #28 | **PR** | #36 |
| **CI result** | ✅ Green |
| **Exit** | `hlsharness/metrics.py` deleted; `CaseMetrics` inlined in `EvalController._run_case()` |

---

### Slice 12E — Upfront validation in EvalController.run()

| Field | Value |
|-------|-------|
| **Issue** | #29 | **PR** | #34 |
| **CI result** | ✅ Green |
| **Exit** | `CaseValidationError` raised before eval loop for bad tool keys or missing equity metadata |

---

### Slice 12F — advance_turn() contract: docstring + trajectory assertion

| Field | Value |
|-------|-------|
| **Issue** | #30 | **PR** | #35 |
| **CI result** | ✅ Green |
| **Exit** | `AgentAdapter.run()` docstring + trajectory assertion in `EvalController._run_case()` |

---

## Completed slices (Slice 13) — MAF onboarding CLI

**PRD:** #41 (Architect Adoption Package)

---

### Slice 13 — AgentManifest, SpecInterpreter, AdapterScaffolder, CaseGenerator enrichment, hls-eval onboard CLI

| Field | Value |
|-------|-------|
| **PRs** | #38 (13A), #39 (13B–E), #40 (13F–G) |
| **CI result** | ✅ Green |
| **Exit** | `hls-eval onboard --spec` / `--generate` CLI live; `SpecInterpreter`, `AdapterScaffolder`, `CaseGenerator` wired end-to-end |

---

## Completed slices (Slices 14A–14F) — Architect Adoption Package

**PRD:** #41

---

### Slice 14A — Devcontainer + .env.example

| Field | Value |
|-------|-------|
| **Issue** | #42 | **PR** | #48 |
| **CI result** | ✅ Green |
| **Exit** | `.devcontainer/devcontainer.json` — zero-install VS Code setup; `.env.example` |

---

### Slice 14B — PdfExtractor — PDF and TXT spec support

| Field | Value |
|-------|-------|
| **PR** | #49 |
| **CI result** | ✅ Green |
| **Exit** | `hlsharness/pdf_extractor.py`; `hls-eval onboard --spec` accepts `.pdf` and `.txt` |

---

### Slice 14C — `--yes` flag — one-shot onboarding

| Field | Value |
|-------|-------|
| **Issue** | #46 | **PR** | #52 |
| **CI result** | ✅ Green |
| **Exit** | `hls-eval onboard --spec … --yes` chains Phase 1 → Phase 2 in one command; without `--yes` prompts before chaining |

---

### Slice 14D — Pre-filled AdapterScaffolder stub *(superseded by Slice 15G)*

| Field | Value |
|-------|-------|
| **PR** | #50 |
| **CI result** | ✅ Green |
| **Exit** | Shipped; subsequently eliminated in Slice 15G when `AgentAdapter` was replaced by MAF `agent.yaml` |

---

### Slice 14E — ReportConfig branding dataclass

| Field | Value |
|-------|-------|
| **Issue** | #45 | **PR** | #51 |
| **CI result** | ✅ Green |
| **Exit** | `hlsharness/report_config.py` — frozen dataclass; `load(path)`, `defaults()`, `render_title()` |

---

### Slice 14F — ReportRenderer + `--pdf` flag

| Field | Value |
|-------|-------|
| **Issue** | #47 | **PR** | #72 |
| **CI result** | ✅ Green |
| **Exit** | `hlsharness/report_renderer.py`; `hls-eval --pdf PATH` writes branded PDF evaluation report |

---

## Completed slices (Slices 15A–15G) — MAF migration

**PRD:** #54 (MAF Agent Migration)

**ADR:** `docs/adr/0002-replace-adapter-with-maf-agents.md`

---

### Slice 15A — MAF SDK spike

| Field | Value |
|-------|-------|
| **PR** | #65 |
| **CI result** | ✅ Green |
| **Exit** | `spike/maf_stub_middleware_spike.py` — validated `StubToolMiddleware` ContextVar intercept pattern |

---

### Slice 15B — MAF Agent YAML + StubToolMiddleware

| Field | Value |
|-------|-------|
| **PR** | #66 |
| **CI result** | ✅ Green |
| **Exit** | `hlsharness/maf_agent.py`, `hlsharness/stub_middleware.py`; `scheduling-v1` runs via MAF |

---

### Slice 15C — Persona library

| Field | Value |
|-------|-------|
| **PR** | #67 |
| **CI result** | ✅ Green |
| **Exit** | `hlsharness/persona_loader.py`; `personas/` YAML library; equity cases reference personas by ID |

---

### Slice 15D — Fixture library

| Field | Value |
|-------|-------|
| **PR** | #68 |
| **CI result** | ✅ Green |
| **Exit** | `stubs/` YAML library; `CaseLoader` resolves fixture refs; existing cases migrated |

---

### Slice 15E — SpecInterpreter → MAF YAML + LLM behavioral critique

| Field | Value |
|-------|-------|
| **PR** | #69 |
| **CI result** | ✅ Green |
| **Exit** | `SpecInterpreter` emits MAF `agent.yaml`; Phase 2 LLM critique added to onboard CLI |

---

### Slice 15F — CaseGenerator → agent.yaml + fixture library + persona refs

| Field | Value |
|-------|-------|
| **PR** | #70 |
| **CI result** | ✅ Green |
| **Exit** | `CaseGenerator` reads tool schemas from `agent.yaml`; generates fixture stubs and cases referencing `personas/` |

---

### Slice 15G — Eliminate AgentAdapter, ToolSimulator, AdapterScaffolder — MAF migration complete

| Field | Value |
|-------|-------|
| **PR** | #71 |
| **CI result** | ✅ Green |
| **Exit** | `adapter.py`, `adapter_scaffolder.py`, `manifest.py`, `simulator.py`, `adapters/` deleted; docs updated for MAF-only world |

---

---

## PatSch Slices — Patient Scheduling Portfolio

### PatSch Slice 0 — Harness Foundation (Complete)

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issues** | HLSHarness#97–99 |
| **PRs** | HLSHarness#97, #98, #99 |
| **Entry** | HLSHarness Slice 15G merged |
| **CI result** | ✅ Green |
| **Exit** | `HITLRoutingScorer`, `SolutionController` DAG rollup, `solution.yaml`, ADRs 0001–0003 |

---

### PatSch Slice 1 — MVE: Slot Search + Intent Capture (Complete)

| Field | Value |
|-------|-------|
| **PRD** | — |
| **Issues** | HLSHarness#100–102, #106, #110, #112 |
| **PRs** | HLSHarness#103–106, #118, #119 |
| **Entry** | PatSch Slice 0 merged |
| **CI result** | ✅ Green |
| **Tests** | 633 passed, 1 skipped |
| **Coverage** | 93.8% |
| **Exit** | orchestrator-v1 + eligibility-v1 + scheduling-v1 agent definitions; 14 functional/equity/hitl_routing/privacy cases; SolutionController L2 wiring + DAG gate |

---

### PatSch Slice 2 — Reschedule + Waitlist Management (Complete)

| Field | Value |
|-------|-------|
| **PRD** | HLSHarness#121 |
| **Issues** | HLSHarness#122–126 |
| **PR** | HLSHarness#127 |
| **Branch** | `slice-2-reschedule-waitlist` |
| **Entry** | PatSch Slice 1 merged; CI green (633 tests) |
| **Deliverables** | `reschedule_appointment` + `check_and_notify_waitlist` tools in scheduling-v1; `hitl_routing` category (0.90); system prompt rules 8–10; `late_cancellation` flag; 5 stubs; 11 cases (TC-S-005–008, TC-S-HIT-001–003, TC-S-EQ-011–014); `no_available_slots` added to `VALID_REASON_CODES` |
| **CI result** | ✅ Green |
| **Tests** | 696 passed, 1 skipped |
| **Coverage** | 93.9% |
| **Exit** | Reschedule + waitlist flows fully covered; scheduling-v1 now has `functional`, `equity`, `hitl_routing` categories |

---

### PatSch Slice 3 — Triage Agent (Complete)

| Field | Value |
|-------|-------|
| **PRD** | HLSHarness#129 |
| **Issues** | HLSHarness#130–135 |
| **PR** | HLSHarness#136 |
| **Branch** | `slice-3-triage-v1` |
| **Entry** | PatSch Slice 2 merged; CI green (696 tests, 1 skipped) |
| **Deliverables** | `cases/triage-v1/agent.yaml` (tool-free, `gpt-5.4-pro`, categories: `urgency_triage`/`safety`/`hitl_routing`, all thresholds 0.90, locked jailbreak-resistant system prompt); 30 cases (14 urgency_triage TC-T-001–014, 10 safety TC-T-015–024, 6 hitl_routing TC-T-HIT-001–006); `tests/test_triage_v1_cases.py` (38 structural assertions); `test_e2e_solution.py` updated to 6-category rollup + 2 triage DAG gate tests |
| **CI result** | ✅ Green |
| **Tests** | 918 passed, 0 skipped |
| **Exit** | triage-v1 fully covered; solution rollup now spans 6 categories (functional, hitl_routing, equity, privacy, urgency_triage, safety); previously skipped triage test resolved |

---

### PatSch Slice 4 — Eligibility Agent Deep-Dive (Complete)

| Field | Value |
|-------|-------|
| **PRD** | HLSHarness#137 |
| **Issues** | HLSHarness#138–143 |
| **PR** | HLSHarness#144 |
| **Branch** | `slice-4-eligibility-deep-dive` |
| **Entry** | PatSch Slice 3 merged; CI green (918 tests, 0 skipped) |
| **Deliverables** | `cases/eligibility-v1/agent.yaml` (add `regulatory_compliance` threshold 0.95 + `hitl_routing` threshold 0.90; Rules 5–9 + Scope integrity block); 5 new stubs (`prior_auth_approved`, `out_of_network`, `high_deductible`, `copay_disclosed`, `prior_auth_denied`); 10 new cases (TC-E-005–010 regulatory_compliance, TC-E-HIT-001–004 hitl_routing); `tests/test_eligibility_v1_cases.py` updated (14-case counts, 8-stub assertions, category validators); `tests/test_e2e_solution.py` updated (7-category rollup) |
| **CI result** | ✅ Green |
| **Tests** | 1005 passed, 0 skipped |
| **Coverage** | 93.9% |
| **Exit** | eligibility-v1 fully covered across 4 categories (functional, privacy, regulatory_compliance, hitl_routing); solution rollup spans 7 categories (adding regulatory_compliance); PatSch demo scope (Slices 1–4) complete |

---

## Dependency graph

```
Slice 1 → Slice 2 → Slice 3 (dashboard)
                  → Slice 4 (generator)
                  → Slice 5 → Slice 6 → Slice 7 → Slice 8 → Slice 9 → Slice 10 → Slice 11
                                                                                      │
                                                                              Slices 12A–12F
                                                                                      │
                                                                                  Slice 13
                                                                                      │
                                                                             Slices 14A–14F
                                                                                      │
                                                                             Slices 15A–15G
```

---

## Governance notes

- **Rule:** No slice begins until the previous blocking slice has a green CI PR merged to `main`.
- **ADRs:** `docs/adr/0001-collapse-scorer-protocol.md` (Scorer collapse), `docs/adr/0002-replace-adapter-with-maf-agents.md` (MAF migration).
- **Domain glossary:** `CONTEXT.md` at repo root defines canonical terms for all architecture reviews.
- **Issue tracker:** All slices have corresponding GitHub issues under `rchinth2003/HLSHarness`.
