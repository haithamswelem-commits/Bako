from fastapi import APIRouter, Depends
from datetime import date

from app.database import get_db_connection
from app.dependencies import get_current_user
from app.services.date_service import current_business_date
from app.services.budget_service import calculate_daily_table

router = APIRouter()


@router.get("/daily-table")
def daily_table(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    data, error = calculate_daily_table(
        cycle_id=cycle_id,
        user_id=user_id
    )

    if error:
        return {
            "error": error
        }

    for row in data["daily_table"]:
        row["date"] = str(row["date"])

    return data


@router.get("/daily-details")
def daily_details(
    cycle_id: int,
    expense_date: date,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            t.id,
            t.amount,
            t.category_id,
            c.name AS category_name,
            t.subcategory_id,
            s.name AS subcategory_name,
            t.description,
            t.expense_date,
            t.payment_channel,
            t.credit_card_id,
            cc.name AS credit_card_name
        FROM transactions t
        JOIN categories c
            ON t.category_id = c.id
        JOIN subcategories s
            ON t.subcategory_id = s.id
        LEFT JOIN credit_cards cc
            ON t.credit_card_id = cc.id
        WHERE t.cycle_id = %s
        AND t.user_id = %s
        AND t.expense_date = %s
        ORDER BY t.id DESC
        """,
        (
            cycle_id,
            user_id,
            expense_date
        )
    )

    rows = cur.fetchall()

    expenses = [
        {
            "id": row[0],
            "amount": float(row[1]),
            "category_id": row[2],
            "category_name": row[3],
            "subcategory_id": row[4],
            "subcategory_name": row[5],
            "description": row[6],
            "expense_date": str(row[7]),
            "payment_channel": row[8],
            "credit_card_id": row[9],
            "credit_card_name": row[10]
        }
        for row in rows
    ]

    cur.execute(
        """
        SELECT
            gc.id,
            gc.goal_id,
            g.name,
            gc.amount,
            gc.contribution_date
        FROM goal_contributions gc
        JOIN goals g
            ON gc.goal_id = g.id
        WHERE gc.cycle_id = %s
        AND gc.user_id = %s
        AND gc.contribution_date = %s
        ORDER BY gc.id DESC
        """,
        (
            cycle_id,
            user_id,
            expense_date
        )
    )

    contribution_rows = cur.fetchall()

    goal_contributions = [
        {
            "id": row[0],
            "goal_id": row[1],
            "goal_name": row[2],
            "amount": float(row[3]),
            "contribution_date": str(row[4])
        }
        for row in contribution_rows
    ]

    cur.close()
    conn.close()

    return {
        "cycle_id": cycle_id,
        "expense_date": str(expense_date),
        "expenses": expenses,
        "goal_contributions": goal_contributions,
        "daily_expenses_total": round(
            sum(expense["amount"] for expense in expenses),
            2
        ),
        "goal_contributions_total": round(
            sum(item["amount"] for item in goal_contributions),
            2
        )
    }


@router.get("/daily-summary")
def daily_summary(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    data, error = calculate_daily_table(
        cycle_id=cycle_id,
        user_id=user_id
    )

    if error:
        return {
            "error": error
        }

    today = current_business_date()

    today_row = next(
        (
            row
            for row in data["daily_table"]
            if row["date"] == today
        ),
        None
    )

    if not today_row:
        return {
            "error": "Today is outside cycle"
        }

    remaining = today_row["remaining_today"]

    if remaining is None:
        message = "No spending yet"

    elif remaining < 0:
        message = f"You overspent by {abs(remaining)}"

    else:
        message = f"You can still spend {remaining}"

    return {
        "today": str(today),
        "available_today": today_row["available_today"],
        "daily_expenses_today": today_row["daily_expenses_today"],
        "goal_contributions_today": today_row["goal_contributions_today"],
        "used_today": today_row["used_today"],
        "spent_today": today_row["spent_today"],
        "remaining_today": remaining,
        "message": message
    }
