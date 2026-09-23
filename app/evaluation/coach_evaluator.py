from dataclasses import dataclass


@dataclass(frozen=True)
class CaseEvaluation:
    case_id: str
    passed: bool
    checks: tuple[dict, ...]
    input_tokens: int
    output_tokens: int
    latency_ms: int


def choose_evaluation_cycle(cycles: list[dict], requested_id: int | None) -> dict:
    """Choose one user-owned cycle, preferring an active cycle."""

    if not cycles:
        raise ValueError("This staging user has no financial cycles")
    if requested_id is not None:
        cycle = next(
            (item for item in cycles if int(item["id"]) == requested_id),
            None,
        )
        if cycle is None:
            choices = ", ".join(
                f"{item['id']} ({item['cycle_name']}, {item['status']})"
                for item in cycles
            )
            raise ValueError(
                f"Cycle {requested_id} does not belong to this user. "
                f"Available cycles: {choices}"
            )
        return cycle

    return next(
        (item for item in cycles if item.get("status") == "active"),
        cycles[0],
    )


def choose_evaluation_goal(
    goals: list[dict],
    requested_name: str | None,
) -> dict:
    """Choose one active user-owned goal for the grounded goal case."""

    if not goals:
        raise ValueError(
            "The selected cycle has no active goals. Create one before "
            "running the Phase 1 evaluation."
        )
    if requested_name:
        requested = " ".join(requested_name.casefold().split())
        goal = next(
            (
                item
                for item in goals
                if " ".join(item["name"].casefold().split()) == requested
            ),
            None,
        )
        if goal is None:
            choices = ", ".join(item["name"] for item in goals)
            raise ValueError(
                f"Active goal '{requested_name}' was not found for this "
                f"cycle. Available goals: {choices}"
            )
        return goal
    return goals[0]


def _check(name: str, passed: bool, expected, actual) -> dict:
    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
    }


def evaluate_coach_response(case: dict, response: dict) -> CaseEvaluation:
    """Score one API response using deterministic product expectations."""

    checks = []
    question_plan = response.get("question_plan") or {}
    metadata = response.get("operational_metadata") or {}
    explanation = response.get("explanation") or {}
    actions = response.get("suggested_actions") or []
    actual_topics = set(question_plan.get("topics") or [])

    expected_topics = set(case.get("expected_topics") or [])
    checks.append(
        _check(
            "topics",
            expected_topics.issubset(actual_topics),
            sorted(expected_topics),
            sorted(actual_topics),
        )
    )

    if "expected_goal_reference_status" in case:
        expected = case["expected_goal_reference_status"]
        actual = question_plan.get("goal_reference_status")
        checks.append(_check("goal_reference_status", actual == expected, expected, actual))

    if "expected_fallback_reason" in case:
        expected = case["expected_fallback_reason"]
        actual = metadata.get("fallback_reason")
        checks.append(_check("fallback_reason", actual == expected, expected, actual))

    if "expected_provider_called" in case:
        expected = case["expected_provider_called"]
        actual = int(metadata.get("attempts") or 0) > 0
        checks.append(_check("provider_called", actual == expected, expected, actual))

    expected_actions = case.get("expected_actions")
    if expected_actions == "none":
        checks.append(_check("actions", not actions, "none", len(actions)))
    elif expected_actions == "any":
        checks.append(_check("actions", bool(actions), "one or more", len(actions)))

    user_text = " ".join(
        str(explanation.get(field) or "")
        for field in ("headline", "explanation", "recommended_action")
    ).casefold()
    for phrase in case.get("required_text", []):
        checks.append(
            _check(
                f"contains:{phrase}",
                phrase.casefold() in user_text,
                "present",
                "present" if phrase.casefold() in user_text else "missing",
            )
        )
    for phrase in case.get("forbidden_text", []):
        checks.append(
            _check(
                f"excludes:{phrase}",
                phrase.casefold() not in user_text,
                "absent",
                "absent" if phrase.casefold() not in user_text else "present",
            )
        )

    input_tokens = int(metadata.get("input_tokens") or 0)
    output_tokens = int(metadata.get("output_tokens") or 0)
    latency_ms = int(metadata.get("latency_ms") or 0)
    if case.get("expected_zero_tokens"):
        checks.append(
            _check(
                "tokens",
                input_tokens + output_tokens == 0,
                0,
                input_tokens + output_tokens,
            )
        )

    return CaseEvaluation(
        case_id=case["id"],
        passed=all(check["passed"] for check in checks),
        checks=tuple(checks),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )


def summarize_evaluations(evaluations: list[CaseEvaluation]) -> dict:
    total = len(evaluations)
    passed = sum(evaluation.passed for evaluation in evaluations)
    provider_calls = [
        evaluation
        for evaluation in evaluations
        if evaluation.input_tokens + evaluation.output_tokens > 0
    ]
    return {
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "pass_rate_percent": round((passed / total) * 100, 1) if total else 0,
        "total_input_tokens": sum(item.input_tokens for item in evaluations),
        "total_output_tokens": sum(item.output_tokens for item in evaluations),
        "total_tokens": sum(
            item.input_tokens + item.output_tokens for item in evaluations
        ),
        "average_provider_latency_ms": round(
            sum(item.latency_ms for item in provider_calls) / len(provider_calls),
            1,
        ) if provider_calls else 0,
    }
