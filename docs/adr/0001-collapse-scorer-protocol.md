# ADR-0001: Collapse Scorer protocol to single score() method

**Status:** Accepted  
**Date:** 2026-05-10

## Context

The original `Scorer` protocol had four methods: `score_functional`, `score_safety`, `score_privacy`, `score_equity`. This shape was forced by `EvalController`'s elif routing — the controller needed to call the right method by name because it drove routing itself.

Once the Category Registry moved into `Judge.__init__`, the elif chain disappeared. `Judge.score()` became the single dispatch point. There was no longer any reason for callers to know which category-specific method to invoke.

## Decision

Collapse `Scorer` to a single method: `score(category: str, case: TestCase, response: AgentResponse) -> JudgeResult`.

## Consequences

- `EvalController` calls `judge.score(case.category, case, response)` — no elif chain, no category-specific imports.
- `_FakeJudge` in `test_controller.py` becomes a single-method stub instead of a four-method mirror.
- Adding a new category does not require adding a method to the `Scorer` protocol.
- **Trade-off accepted:** callers lose compile-time category-specificity. A call with `category="typo"` will raise `KeyError` at runtime rather than failing mypy. Mitigated by `VALID_CATEGORIES` validation in `CaseLoader` and upfront validation in `EvalController`.
