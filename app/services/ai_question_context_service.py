from dataclasses import replace
from datetime import date

from app.ai.contracts import CoachExplanationRequest, VerifiedFinancialFact
from app.ai.question_router import (
    CoachQuestionPlan,
    resolve_goal_reference,
    route_coach_question,
)
from app.services.ai_explanation_service import build_explanation_request
from app.services.analysis_service import calculate_spending_analysis
from app.services.goals_service import forecast_goals, get_user_goals


def _spending_facts(cycle_id: int, user_id: int) -> list[VerifiedFinancialFact]:
    analysis, error = calculate_spending_analysis(cycle_id, user_id)
    if error or analysis is None:
        return []

    facts = [
        VerifiedFinancialFact(
            fact_id="cycle_income",
            label="Cycle income",
            value=analysis["income"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="total_spending",
            label="Total spending",
            value=analysis["total_spent"],
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="cash_spending",
            label="Spending paid in cash",
            value=analysis.get("by_payment_channel", {}).get("cash", 0),
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="credit_card_spending",
            label="Spending paid by credit card",
            value=analysis.get("by_payment_channel", {}).get("credit_card", 0),
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="credit_card_outstanding",
            label="Outstanding credit card spending in this cycle",
            value=analysis.get("credit_card_status", {}).get("outstanding", 0),
            unit="EGP",
        ),
        VerifiedFinancialFact(
            fact_id="credit_card_settled",
            label="Settled credit card spending in this cycle",
            value=analysis.get("credit_card_status", {}).get("settled", 0),
            unit="EGP",
        ),
    ]
    for index, item in enumerate(analysis["by_category"][:10], start=1):
        facts.append(
            VerifiedFinancialFact(
                fact_id=f"category_{index}_amount",
                label=f"Spending in category {item['category']}",
                value=item["amount"],
                unit="EGP",
            )
        )
    for index, item in enumerate(analysis["by_subcategory"][:15], start=1):
        facts.append(
            VerifiedFinancialFact(
                fact_id=f"subcategory_{index}_amount",
                label=(
                    f"Spending in {item['category']} / "
                    f"{item['subcategory']}"
                ),
                value=item["amount"],
                unit="EGP",
            )
        )
    return facts


def _goal_facts(goals: list[dict]) -> list[VerifiedFinancialFact]:
    facts = []
    for index, goal in enumerate(goals[:5], start=1):
        prefix = f"goal_{index}"
        name = goal["name"]
        facts.extend(
            [
                VerifiedFinancialFact(
                    fact_id=f"{prefix}_target",
                    label=f"Target amount for goal {name}",
                    value=goal["target_amount"],
                    unit="EGP",
                ),
                VerifiedFinancialFact(
                    fact_id=f"{prefix}_saved",
                    label=f"Amount saved for goal {name}",
                    value=goal["current_amount"],
                    unit="EGP",
                ),
                VerifiedFinancialFact(
                    fact_id=f"{prefix}_remaining",
                    label=f"Amount remaining for goal {name}",
                    value=goal["remaining_amount"],
                    unit="EGP",
                ),
            ]
        )
        if goal["days_until_deadline"] is not None:
            facts.append(
                VerifiedFinancialFact(
                    fact_id=f"{prefix}_days_left",
                    label=f"Days remaining for goal {name}",
                    value=goal["days_until_deadline"],
                    unit="days",
                )
            )
        if goal["required_daily_saving"] is not None:
            facts.append(
                VerifiedFinancialFact(
                    fact_id=f"{prefix}_daily_saving",
                    label=f"Required daily saving for goal {name}",
                    value=goal["required_daily_saving"],
                    unit="EGP",
                )
            )
    return facts


def build_contextual_explanation_request(
    cycle_coach: dict,
    question: str,
    user_id: int,
) -> tuple[CoachExplanationRequest, CoachQuestionPlan]:
    """Gather only read-only facts relevant to the user's question."""

    plan = route_coach_question(question)
    base_request = build_explanation_request(cycle_coach)
    extra_facts: list[VerifiedFinancialFact] = []

    if "spending" in plan.topics:
        extra_facts.extend(
            _spending_facts(base_request.cycle_id, user_id)
        )
    goals = []
    if "goals" in plan.topics or not plan.supported:
        goals = forecast_goals(
            get_user_goals(
                user_id,
                active_only=True,
                cycle_id=base_request.cycle_id,
            ),
            today=base_request.as_of_date,
            daily_budget=dict(
                (fact.fact_id, fact.value) for fact in base_request.facts
            )["safe_daily_target"],
        )
        goal_names = tuple(goal["name"] for goal in goals[:5])
        goal_reference = resolve_goal_reference(question, goal_names)
        normalized_question = " ".join(
            question.casefold().strip(" .,!؟?").split()
        )
        exact_goal_reply = next(
            (
                name
                for name in goal_names
                if " ".join(name.casefold().split()) == normalized_question
            ),
            None,
        )
        if not plan.supported and exact_goal_reply:
            plan = replace(plan, topics=("goals",), supported=True)
            goal_reference = resolve_goal_reference(question, goal_names)
        plan = replace(
            plan,
            goal_reference_status=goal_reference.status,
            requested_goal_name=goal_reference.requested_name,
            matched_goal_name=goal_reference.matched_name,
            available_goal_names=goal_names,
        )
        if "goals" in plan.topics:
            extra_facts.extend(_goal_facts(goals))
    return (
        base_request.model_copy(
            update={"facts": base_request.facts + tuple(extra_facts)}
        ),
        plan,
    )
