from datetime import date

from app.services.goals_service import (
    PRIORITY_ORDER,
    forecast_goals
)
from app.services.date_service import current_business_date


SAFE_ALLOCATION_RATIO = 0.5


def build_insight(
    insight_type,
    title,
    description,
    suggested_action,
    priority,
    goal_id=None,
    amount=None
):
    insight = {
        "type": insight_type,
        "title": title,
        "description": description,
        "suggested_action": suggested_action,
        "priority": priority,
        "goal_id": goal_id,
        "amount": round(float(amount), 2) if amount is not None else None
    }
    return insight


def allocate_positive_carryover(carryover, goals):
    positive_carryover = max(float(carryover), 0)
    safe_allocation = round(
        positive_carryover * SAFE_ALLOCATION_RATIO,
        2
    )
    buffer_amount = round(
        positive_carryover - safe_allocation,
        2
    )
    allocations = []
    amount_left = safe_allocation

    active_goals = sorted(
        (
            goal
            for goal in goals
            if goal.get("is_active", True)
            and float(goal.get("remaining_amount", 0)) > 0
        ),
        key=lambda goal: (
            PRIORITY_ORDER.get(goal.get("priority"), 1),
            goal.get("deadline_date") or "9999-12-31",
            goal.get("id", 0)
        )
    )

    for goal in active_goals:
        if amount_left <= 0:
            break

        allocation = round(
            min(amount_left, float(goal["remaining_amount"])),
            2
        )

        if allocation <= 0:
            continue

        allocations.append({
            "goal_id": goal.get("id"),
            "goal_name": goal["name"],
            "priority": goal.get("priority", "medium"),
            "amount": allocation
        })
        amount_left = round(amount_left - allocation, 2)

    buffer_amount = round(buffer_amount + amount_left, 2)

    return {
        "carryover": round(positive_carryover, 2),
        "safe_allocation": safe_allocation,
        "buffer_amount": buffer_amount,
        "goal_allocations": allocations
    }


def build_overspending_recovery(
    negative_carryover,
    remaining_days,
    daily_budget
):
    recovery_amount = abs(min(float(negative_carryover), 0))
    recovery_days = max(int(remaining_days), 1)
    recovery_per_day = round(
        recovery_amount / recovery_days,
        2
    )
    temporary_daily_target = round(
        max(float(daily_budget) - recovery_per_day, 0),
        2
    )

    return {
        "recovery_amount": round(recovery_amount, 2),
        "recovery_days": recovery_days,
        "recovery_per_day": recovery_per_day,
        "temporary_daily_target": temporary_daily_target
    }


def generate_rule_based_insights(
    budget_data,
    goals,
    today=None
):
    current_date = today or current_business_date()
    daily_table = budget_data.get("daily_table", [])
    actual_days = [
        row
        for row in daily_table
        if row.get("status") == "actual"
        and row.get("remaining_today") is not None
    ]
    current_row = actual_days[-1] if actual_days else None
    current_carryover = (
        float(current_row["remaining_today"])
        if current_row
        else 0
    )
    daily_budget = float(
        budget_data.get(
            "current_daily_allowance",
            current_row["available_today"] if current_row else 0
        )
    )
    remaining_days = len([
        row
        for row in daily_table
        if row.get("date") > current_date
    ])
    goal_forecasts = forecast_goals(
        goals,
        today=current_date,
        daily_budget=daily_budget
    )
    insights = []
    remaining_total_budget = budget_data.get("remaining_total_budget")
    cycle_budget_exhausted = (
        remaining_total_budget is not None
        and float(remaining_total_budget) <= 0
    )

    if cycle_budget_exhausted:
        remaining_total_budget = float(remaining_total_budget)
        recovery = build_overspending_recovery(
            remaining_total_budget,
            remaining_days,
            daily_budget
        )
        insights.append(build_insight(
            "risk",
            "Cycle budget exhausted",
            (
                f"The cycle balance is short by EGP "
                f"{recovery['recovery_amount']:.2f}."
            ),
            (
                f"Reduce daily spending by EGP "
                f"{recovery['recovery_per_day']:.2f} for "
                f"{recovery['recovery_days']} days."
            ),
            "high",
            amount=recovery["recovery_per_day"]
        ))

    elif current_carryover > 0:
        allocation = allocate_positive_carryover(
            current_carryover,
            goal_forecasts
        )

        for item in allocation["goal_allocations"]:
            insights.append(build_insight(
                "goal",
                f"Support {item['goal_name']}",
                (
                    f"You have EGP {current_carryover:.2f} left from "
                    "today's allowance."
                ),
                (
                    f"Add EGP {item['amount']:.2f} to "
                    f"{item['goal_name']}."
                ),
                item["priority"],
                goal_id=item["goal_id"],
                amount=item["amount"]
            ))

        insights.append(build_insight(
            "opportunity",
            "Protect your buffer",
            (
                "Only part of positive carryover is suggested for goals "
                "so the cycle keeps a safety margin."
            ),
            f"Keep EGP {allocation['buffer_amount']:.2f} as buffer.",
            "high",
            amount=allocation["buffer_amount"]
        ))

    elif current_carryover < 0:
        recovery = build_overspending_recovery(
            current_carryover,
            remaining_days,
            daily_budget
        )
        insights.append(build_insight(
            "risk",
            "Overspending recovery plan",
            (
                f"Today's spending exceeded the allowance by "
                f"EGP {recovery['recovery_amount']:.2f}."
            ),
            (
                f"Reduce daily spending by EGP "
                f"{recovery['recovery_per_day']:.2f} for "
                f"{recovery['recovery_days']} days."
            ),
            "high",
            amount=recovery["recovery_per_day"]
        ))

        low_priority_goals = [
            goal
            for goal in goal_forecasts
            if goal.get("priority") == "low"
        ]
        if low_priority_goals:
            insights.append(build_insight(
                "warning",
                "Pause low-priority goals",
                (
                    "Temporary goal contributions can make recovery harder "
                    "after an overspending day."
                ),
                (
                    f"Pause {low_priority_goals[0]['name']} until the "
                    "negative carryover is recovered."
                ),
                "medium",
                goal_id=low_priority_goals[0].get("id")
            ))

    if not cycle_budget_exhausted:
        for goal in goal_forecasts:
            if (
                goal["required_daily_saving"] is not None
                and goal["is_on_track"] is False
            ):
                insights.append(build_insight(
                    "goal",
                    f"{goal['name']} needs attention",
                    (
                        f"EGP {goal['remaining_amount']:.2f} remains with "
                        f"{goal['days_until_deadline']} days until the "
                        "deadline."
                    ),
                    (
                        f"Save EGP {goal['required_daily_saving']:.2f} per "
                        "day to reach this goal."
                    ),
                    goal.get("priority", "medium"),
                    goal_id=goal.get("id"),
                    amount=goal["required_daily_saving"]
                ))

    if not insights:
        insights.append(build_insight(
            "healthy",
            "Budget is balanced",
            "No carryover recovery action is needed today.",
            "Keep following today's recommended allowance.",
            "low"
        ))

    return {
        "current_carryover": round(current_carryover, 2),
        "goal_forecasts": goal_forecasts,
        "insights": insights
    }
