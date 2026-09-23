from app.services.analysis_service import (
    calculate_spending_analysis
)
from app.metrics import record_ai_insights_generated
from app.services.budget_service import calculate_daily_table
from app.services.budget_health_service import summarize_budget_health
from app.services.coach_service import (
    build_insight,
    generate_rule_based_insights
)
from app.services.goals_service import get_user_goals


def generate_ai_insights(
    cycle_id: int,
    user_id: int
):
    analysis, error = calculate_spending_analysis(
        cycle_id=cycle_id,
        user_id=user_id
    )

    if error:
        return None, error

    budget_data, budget_error = calculate_daily_table(
        cycle_id=cycle_id,
        user_id=user_id
    )

    if budget_error:
        return None, budget_error

    goals = get_user_goals(
        user_id=user_id,
        active_only=True,
        cycle_id=cycle_id
    )
    coach_data = generate_rule_based_insights(
        budget_data=budget_data,
        goals=goals
    )

    categories = analysis.get(
        "by_category",
        []
    )

    subcategories = analysis.get(
        "by_subcategory",
        []
    )

    budget_health = summarize_budget_health(budget_data)
    budget_status = budget_health["status"]
    budget_used_percentage = budget_health["used_percentage"]
    remaining_budget = budget_health["remaining_budget"]

    if not categories:
        if budget_status == "risk":
            tracking_insight = build_insight(
                "risk",
                "Cycle budget needs attention",
                (
                    "No spending is recorded, but the available "
                    "cycle budget is exhausted."
                ),
                "Review your recorded spending before adding more.",
                "high"
            )
        else:
            tracking_insight = build_insight(
                "healthy",
                "Start tracking spending",
                "No spending data is available for this cycle yet.",
                "Add your first expense to unlock spending patterns.",
                "low"
            )

        structured_insights = [
            tracking_insight,
            *coach_data["insights"]
        ]
        record_ai_insights_generated(structured_insights)
        return {
            "insights": [
                insight["description"]
                for insight in structured_insights
            ],
            "structured_insights": structured_insights,
            "goal_forecasts": coach_data["goal_forecasts"],
            "current_carryover": coach_data["current_carryover"]
        }, None

    top_category = max(
        categories,
        key=lambda x: x["amount"]
    )

    category_name = top_category["category"]
    category_amount = top_category["amount"]

    related_subcategories = [
        item
        for item in subcategories
        if item["category"] == category_name
    ]

    top_subcategory = None

    if related_subcategories:
        top_subcategory = max(
            related_subcategories,
            key=lambda x: x["amount"]
        )

    insights = []
    structured_insights = []

    remaining_days = max(
        budget_data.get("remaining_days", 0),
        1
    )
    daily_category_trim = round(
        (category_amount * 0.15) / remaining_days,
        2
    )

    insights.append(
        (
            f"{category_name} is your highest category at "
            f"{category_amount:.2f} EGP. Try saving about "
            f"{daily_category_trim:.2f} EGP daily from it so your spending "
            "pace slows before the cycle ends."
        )
    )
    structured_insights.append(build_insight(
        "warning",
        "Highest spending category",
        insights[-1],
        (
            f"Set a simple daily trim of {daily_category_trim:.2f} EGP "
            f"from {category_name}."
        ),
        "medium",
        amount=category_amount
    ))

    if top_subcategory:
        sub_daily_trim = round(
            (top_subcategory["amount"] * 0.15) / remaining_days,
            2
        )
        insights.append(
            (
                f"{top_subcategory['subcategory']} is driving most of "
                f"{category_name} spending. Reducing it by about "
                f"{sub_daily_trim:.2f} EGP daily can free cash for your "
                "remaining allowance."
            )
        )
        structured_insights.append(build_insight(
            "warning",
            "Largest spending contributor",
            insights[-1],
            (
                f"Use {sub_daily_trim:.2f} EGP as the daily cut target "
                f"for {top_subcategory['subcategory']}."
            ),
            "medium",
            amount=top_subcategory["amount"]
        ))

    insights.append(
        (
            f"You have used {budget_used_percentage:.1f}% of your available "
            "cycle budget."
        )
    )
    structured_insights.append(build_insight(
        (
            "healthy"
            if budget_status in ("healthy", "stable")
            else budget_status
        ),
        "Cycle spending pace",
        insights[-1],
        (
            "Keep following the recommended daily allowance."
            if budget_status in ("healthy", "stable")
            else "Reduce non-essential spending for the rest of the cycle."
        ),
        (
            "low"
            if budget_status == "healthy"
            else "medium"
            if budget_status in ("stable", "warning")
            else "high"
        )
    ))

    if remaining_budget < 0:
        insights.append(
            (
                "Your available cycle budget is over by "
                f"EGP {abs(remaining_budget):.2f}."
            )
        )
    elif budget_status == "risk":
        insights.append(
            "Your remaining budget is too low for the time left in the cycle."
        )
    elif budget_status == "warning":
        insights.append(
            "Your budget is being used faster than the cycle is progressing."
        )
    elif budget_status == "stable":
        insights.append(
            "Your remaining budget is aligned with the time left in the cycle."
        )
    else:
        insights.append(
            "Your remaining budget is ahead of the cycle spending pace."
        )

    structured_insights.append(build_insight(
        (
            "risk"
            if budget_status == "risk"
            else "warning"
            if budget_status == "warning"
            else "healthy"
        ),
        "Budget position",
        insights[-1],
        (
            "Pause optional spending and follow the recovery recommendation."
            if budget_status == "risk"
            else "Reduce optional spending until your budget pace stabilizes."
            if budget_status == "warning"
            else "Protect the remaining cycle balance."
        ),
        "high" if budget_status == "risk" else "medium"
    ))

    if top_subcategory:
        potential_saving = (
            top_subcategory["amount"] * 0.15
        )

        periodic_saving = round(
            potential_saving / max(remaining_days / 3, 1),
            2
        )
        insights.append(
            (
                f"Reducing {top_subcategory['subcategory']} by 15% could "
                f"save about {potential_saving:.2f} EGP this cycle. That is "
                f"roughly {periodic_saving:.2f} EGP every 3 days that can "
                "stay as buffer or support a goal."
            )
        )
        structured_insights.append(build_insight(
            "opportunity",
            "Saving opportunity",
            insights[-1],
            (
                f"Trim about {periodic_saving:.2f} EGP every 3 days "
                f"from {top_subcategory['subcategory']}."
            ),
            "medium",
            amount=potential_saving
        ))

    structured_insights.extend(coach_data["insights"])
    insights.extend([
        insight["description"]
        for insight in coach_data["insights"]
    ])

    record_ai_insights_generated(structured_insights)

    return {
        "insights": insights,
        "structured_insights": structured_insights,
        "goal_forecasts": coach_data["goal_forecasts"],
        "current_carryover": coach_data["current_carryover"]
    }, None
