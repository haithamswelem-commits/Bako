from datetime import timedelta
from app.database import get_db_connection
from app.metrics import BUDGET_CALCULATIONS_TOTAL
from app.services.date_service import current_business_date
from app.services.payment_service import (
    build_daily_spending_by_date,
    build_goal_contributions_by_date,
)


def build_daily_budget_table(
    income,
    start_date,
    end_date,
    spending_by_date,
    goal_contributions_by_date=None,
    today=None
):
    total_days = (end_date - start_date).days + 1

    if total_days <= 0:
        raise ValueError("Invalid cycle dates")

    current_day = today or current_business_date()
    available_budget = round(float(income), 2)
    remaining_total_budget = available_budget
    cumulative_carryover = 0
    goal_contributions_by_date = goal_contributions_by_date or {}
    result = []
    current_date = start_date

    while current_date <= end_date:
        daily_expenses_today = round(
            float(spending_by_date.get(current_date, 0)),
            2
        )
        goal_contributions_today = round(
            float(goal_contributions_by_date.get(current_date, 0)),
            2
        )
        used_today = round(
            daily_expenses_today + goal_contributions_today,
            2
        )
        remaining_days = (end_date - current_date).days + 1
        carryover_from_previous_day = round(
            cumulative_carryover,
            2
        )

        # Carry-over is already preserved in the remaining cycle balance.
        # Adding it here again would overstate today's recommendation.
        dynamic_daily_average = round(
            remaining_total_budget / remaining_days,
            2
        )
        # A recommendation cannot be negative. Any deficit remains visible in
        # remaining_total_budget and is handled by the recovery coach.
        available_today = max(dynamic_daily_average, 0)

        if current_date <= current_day:
            remaining_today = round(
                available_today - used_today,
                2
            )
            remaining_total_budget = round(
                remaining_total_budget - used_today,
                2
            )
            cumulative_carryover = round(
                cumulative_carryover + remaining_today,
                2
            )
            carryover_to_next_day = cumulative_carryover
            status = "actual"
        else:
            remaining_today = None
            carryover_to_next_day = None
            status = "future"

        result.append({
            "date": current_date,
            "status": status,
            "dynamic_daily_average": dynamic_daily_average,
            "carryover_from_previous_day": carryover_from_previous_day,
            "available_today": available_today,
            "daily_expenses_today": daily_expenses_today,
            "goal_contributions_today": goal_contributions_today,
            "used_today": used_today,
            "spent_today": used_today,
            "remaining_today": remaining_today,
            "carryover_to_next_day": carryover_to_next_day,
            "remaining_total_budget": remaining_total_budget
        })

        current_date += timedelta(days=1)

    remaining_days = max((end_date - current_day).days + 1, 0)
    current_daily_allowance = round(
        max(remaining_total_budget, 0) / remaining_days,
        2
    ) if remaining_days else 0

    return {
        "income": float(income),
        "available_budget": available_budget,
        "remaining_total_budget": remaining_total_budget,
        "remaining_days": remaining_days,
        "current_daily_allowance": current_daily_allowance,
        "total_days": total_days,
        "daily_table": result
    }


def calculate_daily_table(
    cycle_id: int,
    user_id: int
):
    conn = get_db_connection()
    cur = conn.cursor()

    # Get user's cycle
    cur.execute(
        """
        SELECT income_amount, start_date, end_date
        FROM financial_cycles
        WHERE id = %s
        AND user_id = %s
        """,
        (
            cycle_id,
            user_id
        )
    )

    cycle = cur.fetchone()

    if not cycle:
        cur.close()
        conn.close()

        return None, "Cycle not found"

    income, start_date, end_date = cycle

    # Get user's transactions
    cur.execute(
        """
        SELECT expense_date, COALESCE(SUM(amount), 0), payment_channel
        FROM transactions
        WHERE cycle_id = %s
        AND user_id = %s
        GROUP BY expense_date, payment_channel
        """,
        (
            cycle_id,
            user_id
        )
    )

    spending_rows = cur.fetchall()

    spending_by_date = build_daily_spending_by_date(spending_rows)

    cur.execute(
        """
        SELECT contribution_date, COALESCE(SUM(amount), 0)
        FROM goal_contributions
        WHERE cycle_id = %s
        AND user_id = %s
        GROUP BY contribution_date
        """,
        (
            cycle_id,
            user_id
        )
    )

    contribution_rows = cur.fetchall()

    goal_contributions_by_date = build_goal_contributions_by_date(
        contribution_rows
    )
    try:
        data = build_daily_budget_table(
            income=income,
            start_date=start_date,
            end_date=end_date,
            spending_by_date=spending_by_date,
            goal_contributions_by_date=goal_contributions_by_date
        )
    except ValueError as error:
        cur.close()
        conn.close()

        return None, str(error)

    BUDGET_CALCULATIONS_TOTAL.inc()

    cur.close()
    conn.close()

    return {
        "cycle_id": cycle_id,
        "user_id": user_id,
        **data
    }, None
