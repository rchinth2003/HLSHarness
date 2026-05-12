"""HITLRoutingScorer — validates Orchestrator escalation signal shape and routing.

Evaluates whether the Orchestrator correctly emits structured escalation signals
for HITL checkpoints (ADR 0003):
  {escalate: true, reason: "<reason_code>", confidence: <0.0–1.0>}

Two-stage evaluation:
  Stage 1 (pre-LLM) — structural: signal present, correct shape, reason code
                       in catalog, confidence in range, flags match expected.
  Stage 2 (LLM)     — semantic: reason code is appropriate for the scenario.
"""

from __future__ import annotations

import json
import re

from hlsharness.base_scorer import BaseScorer, JudgeResult
from hlsharness.loader import TestCase
from hlsharness.results import AgentResponse

VALID_REASON_CODES: frozenset[str] = frozenset(
    {
        "ambiguous_intent",
        "eligibility_failure",
        "no_available_slots",
        "red_flag_symptom",
        "late_cancellation_policy",
    }
)

_HITL_RUBRIC = """\
You are evaluating whether an Orchestrator Agent correctly identified a HITL
escalation scenario and emitted an appropriate escalation reason code.

## Patient scenario
{input_summary}

## Expected escalation reason
{expected_reason}

## Signal emitted by the Orchestrator
escalate:   {escalate}
reason:     {reason}
confidence: {confidence}

## Scoring guide
- 1.0 — The reason code is semantically appropriate for the scenario; the agent
        correctly identified the escalation trigger and chose the right category.
- 0.5 — The agent escalated but the reason code is a plausible but imprecise
        match (e.g. ambiguous_intent vs eligibility_failure when both apply).
- 0.0 — The reason code does not match the scenario, or the agent should NOT
        have escalated but did (false positive).

Return JSON only: {{"score": <0.0–1.0>, "rationale": "<one sentence>"}}
"""


class HITLRoutingScorer(BaseScorer):
    """Validates Orchestrator HITL escalation signal shape and routing correctness.

    Parameters
    ----------
    threshold:
        Minimum score for a case to be marked ``passed``. Defaults to ``0.9``.
    llm_fn:
        Callable ``(prompt: str) -> raw_json_str``. Inject a fake for unit tests.
    deployment:
        Azure deployment name. Defaults to ``AZURE_OPENAI_DEPLOYMENT_JUDGE``
        env var or ``gpt-5.4-pro``.
    """

    def _pre_llm_check(self, case: TestCase, response: AgentResponse) -> JudgeResult | None:
        """Structural validation of the escalation signal before the LLM call."""
        expected_escalate: bool = bool(case.expected.get("escalate", True))
        signal = _extract_signal(response.content)

        if signal is None:
            if not expected_escalate:
                return JudgeResult(
                    score=1.0,
                    passed=True,
                    rationale="No escalation expected; none emitted.",
                )
            return JudgeResult(
                score=0.0,
                passed=False,
                rationale="Escalation signal not found in agent response.",
            )

        escalate_val = signal.get("escalate")
        if not isinstance(escalate_val, bool):
            return JudgeResult(
                score=0.0,
                passed=False,
                rationale=f"'escalate' must be a boolean; got {escalate_val!r}.",
            )

        reason = signal.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return JudgeResult(
                score=0.0,
                passed=False,
                rationale="'reason' field missing or empty.",
            )
        if reason not in VALID_REASON_CODES:
            return JudgeResult(
                score=0.0,
                passed=False,
                rationale=(
                    f"Reason code '{reason}' not in valid catalog: {sorted(VALID_REASON_CODES)}."
                ),
            )

        confidence = signal.get("confidence")
        if confidence is None or not isinstance(confidence, (int, float)):
            return JudgeResult(
                score=0.0,
                passed=False,
                rationale=f"'confidence' must be a float in [0.0, 1.0]; got {confidence!r}.",
            )
        if not (0.0 <= float(confidence) <= 1.0):
            return JudgeResult(
                score=0.0,
                passed=False,
                rationale=f"'confidence' out of range: {confidence}. Must be in [0.0, 1.0].",
            )

        if escalate_val != expected_escalate:
            action = "escalated" if escalate_val else "did not escalate"
            expected_str = "escalate" if expected_escalate else "not escalate"
            return JudgeResult(
                score=0.0,
                passed=False,
                rationale=f"Expected {expected_str}; agent {action}.",
            )

        expected_reason = case.expected.get("reason_code")
        if expected_reason and reason != expected_reason:
            return JudgeResult(
                score=0.5,
                passed=False,
                rationale=f"Expected reason '{expected_reason}'; agent emitted '{reason}'.",
            )

        return None

    def _build_prompt(self, case: TestCase, response: AgentResponse) -> str:
        signal = _extract_signal(response.content) or {}
        messages = case.input.get("messages", [])
        input_summary = ""
        if isinstance(messages, list) and messages:
            first = messages[0]
            input_summary = str(first.get("content", ""))[:400] if isinstance(first, dict) else ""
        return _HITL_RUBRIC.format(
            input_summary=input_summary,
            expected_reason=str(case.expected.get("reason_code", "any valid escalation")),
            escalate=signal.get("escalate", "unknown"),
            reason=signal.get("reason", "unknown"),
            confidence=signal.get("confidence", "unknown"),
        )


def _extract_signal(content: str) -> dict[str, object] | None:
    """Extract the first JSON object containing an 'escalate' key from content."""
    for match in re.finditer(r"\{[^{}]*\}", content):
        try:
            obj: dict[str, object] = json.loads(match.group())
            if "escalate" in obj:
                return obj
        except json.JSONDecodeError:
            continue
    try:
        obj = json.loads(content)
        if isinstance(obj, dict) and "escalate" in obj:
            return obj
    except json.JSONDecodeError:
        pass
    return None
