def summarize_budget_health(budget_data):
    available_budget = float(budget_data.get("available_budget", 0))
    remaining_budget = float(
        budget_data.get("remaining_total_budget", 0)
    )
    remaining_days = max(int(budget_data.get("remaining_days", 0)), 0)
    total_days = max(int(budget_data.get("total_days", 0)), 0)

    if available_budget > 0:
        budget_remaining_percentage = max(
            min((remaining_budget / available_budget) * 100, 100),
            0
        )
        used_percentage = max(
            ((available_budget - remaining_budget) / available_budget) * 100,
            0
        )
    else:
        budget_remaining_percentage = 0
        used_percentage = 100 if remaining_budget <= 0 else 0

    time_remaining_percentage = (
        max(min((remaining_days / total_days) * 100, 100), 0)
        if total_days > 0
        else 0
    )
    pace_gap = budget_remaining_percentage - time_remaining_percentage

    if remaining_budget < 0 or available_budget <= 0:
        status = "risk"
    elif pace_gap >= 15:
        status = "healthy"
    elif pace_gap >= -5:
        status = "stable"
    elif pace_gap >= -15:
        status = "warning"
    else:
        status = "risk"

    return {
        "status": status,
        "available_budget": round(available_budget, 2),
        "remaining_budget": round(remaining_budget, 2),
        "used_percentage": round(used_percentage, 1),
        "budget_remaining_percentage": round(
            budget_remaining_percentage,
            1
        ),
        "time_remaining_percentage": round(time_remaining_percentage, 1),
        "pace_gap": round(pace_gap, 1)
    }
