import re
from datetime import date, datetime

from app.database import get_db_connection
from app.services.date_service import current_business_date


PRIORITY_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2
}


def serialize_goal(row):
    return {
        "id": row[0],
        "cycle_id": row[1],
        "name": row[2],
        "type": row[3],
        "target_amount": float(row[4]),
        "current_amount": float(row[5]),
        "deadline_date": str(row[6]) if row[6] else None,
        "priority": row[7],
        "auto_rule": row[8],
        "is_active": row[9],
        "created_at": row[10].isoformat() if row[10] else None
    }


def get_user_goals(user_id, active_only=False, cycle_id=None):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cycle_window = None
        if cycle_id is not None:
            cur.execute(
                """
                SELECT start_date, end_date
                FROM financial_cycles
                WHERE id = %s AND user_id = %s
                """,
                (cycle_id, user_id)
            )
            cycle_window = cur.fetchone()

            if not cycle_window:
                return []

        query = """
            SELECT
                id,
                cycle_id,
                name,
                type,
                target_amount,
                current_amount,
                deadline_date,
                priority,
                auto_rule,
                is_active,
                created_at
            FROM goals
            WHERE user_id = %s
        """
        params = [user_id]

        if active_only or cycle_id is not None:
            query += " AND is_active = TRUE"

        if cycle_id is not None:
            cycle_start, cycle_end = cycle_window
            query += """
                AND current_amount < target_amount
                AND DATE(created_at) <= %s
                AND (
                    deadline_date IS NULL
                    OR deadline_date >= %s
                )
            """
            params.extend([cycle_end, cycle_start])

        query += """
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                deadline_date NULLS LAST,
                id
        """

        cur.execute(query, params)
        return [serialize_goal(row) for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def parse_auto_rule_daily_amount(auto_rule, daily_budget):
    if not auto_rule:
        return 0

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)_percent_of_daily_budget",
        auto_rule.strip().lower()
    )

    if not match:
        return 0

    percentage = float(match.group(1))
    return round(max(float(daily_budget), 0) * percentage / 100, 2)


def forecast_goal(goal, today=None, daily_budget=0):
    forecast_date = today or current_business_date()
    target_amount = float(goal["target_amount"])
    current_amount = float(goal.get("current_amount", 0))
    remaining_amount = round(max(target_amount - current_amount, 0), 2)
    deadline_value = goal.get("deadline_date")

    if isinstance(deadline_value, str):
        deadline = date.fromisoformat(deadline_value)
    else:
        deadline = deadline_value

    days_until_deadline = (
        max((deadline - forecast_date).days, 0)
        if deadline
        else None
    )

    if remaining_amount == 0:
        required_daily_saving = 0
    elif deadline:
        required_daily_saving = round(
            remaining_amount / max(days_until_deadline, 1),
            2
        )
    else:
        required_daily_saving = None

    created_value = goal.get("created_at")
    if isinstance(created_value, str):
        created_date = datetime.fromisoformat(created_value).date()
    elif isinstance(created_value, datetime):
        created_date = created_value.date()
    else:
        created_date = created_value

    elapsed_days = max(
        (forecast_date - created_date).days,
        1
    ) if created_date else 1
    current_daily_pace = round(current_amount / elapsed_days, 2)
    auto_daily_amount = parse_auto_rule_daily_amount(
        goal.get("auto_rule"),
        daily_budget
    )
    effective_daily_pace = max(current_daily_pace, auto_daily_amount)

    if remaining_amount == 0:
        is_on_track = True
    elif required_daily_saving is None:
        is_on_track = None
    else:
        is_on_track = effective_daily_pace >= required_daily_saving

    return {
        **goal,
        "remaining_amount": remaining_amount,
        "days_until_deadline": days_until_deadline,
        "required_daily_saving": required_daily_saving,
        "current_daily_pace": current_daily_pace,
        "is_on_track": is_on_track
    }


def forecast_goals(goals, today=None, daily_budget=0):
    return [
        forecast_goal(goal, today=today, daily_budget=daily_budget)
        for goal in goals
        if goal.get("is_active", True)
    ]
