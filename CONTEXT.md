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

**Adapter Author**
The developer who implements the `run()` method on a generated adapter stub. Distinct from the Architect — works from the generated stub and two `TODO` markers (deployment env var name, system prompt). Does not need to read the full guide.

**Architect**
A solutions architect onboarding a new HLS use case. Their job ends at Phase 2 of onboarding — they produce the manifest and seed cases. They hand the adapter stub to an Adapter Author and consume Evaluation Reports as output.

**Category Registry**
A dict mapping category name → `BaseScorer` instance, owned and initialized by `Judge`. The registry is the single place that maps a category string to its scoring logic.

**Rubric Hook**
The abstract method `_build_prompt(case, response) -> str` that each concrete Scorer overrides to supply its category-specific LLM prompt. The only required customization point for a new Scorer.

**Pre-LLM Check Hook**
The optional method `_pre_llm_check(case, response) -> JudgeResult | None` on `BaseScorer`. Defaults to `None` (no-op). Overridden only by scorers that need a deterministic check between `must_not_contain` and the LLM call (e.g., PHI regex in `PrivacyGuard`).

**Upfront Validation**
Case-list validation performed once in `EvalController.run()` before the eval loop starts. Checks that `tool_responses` keys match `adapter.tools` and that equity cases have required metadata keys (`patient_age`, `language`, `insurance`). All config errors surface together, not mid-run.

**Evaluation Report**
A PDF artifact produced by `hls-eval --pdf` after a run. Structured as: cover page (agent name, date, overall verdict) → summary table → failed cases with judge rationale. Primary sharing artifact for clinical directors and compliance officers who do not run the harness themselves. Configurable branding via `report_config.yaml`.

**ReportConfig**
Immutable dataclass loaded from an optional `report_config.yaml`. Fields: `org` (organization name), `brand_color` (hex), `title_template` (supports `{agent}` and `{date}` placeholders). Defaults to `"Contoso Health"`, `"#0D3B66"`, and `"{agent} — AI Quality Evaluation"`. Unknown YAML keys are silently ignored for forward compatibility.
