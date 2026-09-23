from fastapi import APIRouter, Depends, HTTPException
from datetime import date
from pydantic import BaseModel, Field

from app.database import get_db_connection
from app.dependencies import get_current_user
from app.services.date_service import current_business_date

router = APIRouter()


class CycleCreate(BaseModel):
    cycle_name: str | None = None
    income_amount: float
    start_date: date
    end_date: date


class CycleUpdate(BaseModel):
    cycle_name: str


class CycleBudgetAdjustmentCreate(BaseModel):
    amount: float = Field(gt=0)
    note: str | None = Field(default=None, max_length=160)


def normalize_cycle_name(cycle_name):
    normalized = (cycle_name or "Monthly Income").strip()

    if not normalized:
        normalized = "Monthly Income"

    if len(normalized) > 120:
        raise HTTPException(
            status_code=400,
            detail="cycle_name must be 120 characters or fewer"
        )

    return normalized


def get_cycle_status(start_date, end_date, today=None):
    today = today or current_business_date()

    if start_date <= today <= end_date:
        return "active"

    if start_date > today:
        return "upcoming"

    return "ended"


def serialize_cycle(row, today=None):
    start_date = row[3]
    end_date = row[4]

    return {
        "id": row[0],
        "cycle_name": row[1] or "Monthly Income",
        "income_amount": float(row[2]),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "status": get_cycle_status(start_date, end_date, today)
    }


def calculate_change(current, previous):
    current_value = float(current or 0)
    previous_value = float(previous or 0)
    difference = round(current_value - previous_value, 2)

    if previous_value == 0:
        percentage_change = None if current_value != 0 else 0
    else:
        percentage_change = round((difference / previous_value) * 100, 2)

    return {
        "current": round(current_value, 2),
        "previous": round(previous_value, 2),
        "difference": difference,
        "percentage_change": percentage_change
    }


def get_cycle_financial_summary(cur, cycle_id, user_id):
    cur.execute(
        """
        SELECT id, cycle_name, income_amount, start_date, end_date
        FROM financial_cycles
        WHERE id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    cycle = cur.fetchone()

    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE cycle_id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    total_spending = float(cur.fetchone()[0])

    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM goal_contributions
        WHERE cycle_id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    goal_contributions = float(cur.fetchone()[0])

    cur.execute(
        """
        SELECT c.name, COALESCE(SUM(t.amount), 0) AS amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.cycle_id = %s AND t.user_id = %s
        GROUP BY c.name
        ORDER BY amount DESC, c.name
        """,
        (cycle_id, user_id)
    )
    categories = {
        row[0]: round(float(row[1]), 2)
        for row in cur.fetchall()
    }

    cur.execute(
        """
        SELECT
            c.name,
            s.name,
            COALESCE(SUM(t.amount), 0) AS amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        LEFT JOIN subcategories s ON t.subcategory_id = s.id
        WHERE t.cycle_id = %s AND t.user_id = %s
        GROUP BY c.name, s.name
        ORDER BY amount DESC, c.name, s.name
        """,
        (cycle_id, user_id)
    )
    subcategories = {
        f"{row[0]} / {row[1] or 'Uncategorized'}": round(float(row[2]), 2)
        for row in cur.fetchall()
    }

    income = float(cycle[2])
    remaining_balance = round(
        income - total_spending - goal_contributions,
        2
    )

    return {
        "cycle": serialize_cycle(
            (cycle[0], cycle[1], cycle[2], cycle[3], cycle[4])
        ),
        "income": round(income, 2),
        "total_spending": round(total_spending, 2),
        "goal_contributions": round(goal_contributions, 2),
        "remaining_balance": remaining_balance,
        "categories": categories,
        "subcategories": subcategories
    }


def compare_breakdown(current_breakdown, previous_breakdown):
    names = sorted(set(current_breakdown) | set(previous_breakdown))

    return [
        {
            "name": name,
            **calculate_change(
                current_breakdown.get(name, 0),
                previous_breakdown.get(name, 0)
            )
        }
        for name in names
    ]


@router.post("/cycle")
def create_cycle(
    cycle: CycleCreate,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    if cycle.income_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="income_amount must be greater than zero"
        )

    if cycle.end_date < cycle.start_date:
        raise HTTPException(
            status_code=400,
            detail="end_date must be on or after start_date"
        )

    cycle_name = normalize_cycle_name(cycle.cycle_name)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO financial_cycles
        (
            income_amount,
            cycle_name,
            start_date,
            end_date,
            user_id
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            cycle.income_amount,
            cycle_name,
            cycle.start_date,
            cycle.end_date,
            user_id
        )
    )

    cycle_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return {
        "message": "Cycle created",
        "cycle_id": cycle_id,
        "user_id": user_id
    }


@router.get("/current-cycle")
def get_current_cycle(
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]
    today = current_business_date()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, cycle_name, income_amount, start_date, end_date
        FROM financial_cycles
        WHERE user_id = %s
        ORDER BY
            CASE
                WHEN %s BETWEEN start_date AND end_date THEN 0
                WHEN start_date > %s THEN 1
                ELSE 2
            END,
            CASE
                WHEN %s BETWEEN start_date AND end_date
                THEN (end_date - start_date)
                ELSE NULL
            END ASC NULLS LAST,
            start_date DESC,
            id DESC
        LIMIT 1
        """,
        (user_id, today, today, today)
    )

    cycle = cur.fetchone()

    cur.close()
    conn.close()

    if not cycle:
        return {
            "cycle": None
        }

    return {
        "cycle": serialize_cycle(cycle)
    }


@router.get("/cycles")
def list_cycles(
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, cycle_name, income_amount, start_date, end_date
        FROM financial_cycles
        WHERE user_id = %s
        ORDER BY start_date DESC, id DESC
        """,
        (user_id,)
    )

    cycles = [
        serialize_cycle(row)
        for row in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return {
        "cycles": cycles
    }


@router.put("/cycles/{cycle_id}")
def update_cycle(
    cycle_id: int,
    cycle: CycleUpdate,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]
    cycle_name = normalize_cycle_name(cycle.cycle_name)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE financial_cycles
        SET cycle_name = %s
        WHERE id = %s AND user_id = %s
        RETURNING id, cycle_name, income_amount, start_date, end_date
        """,
        (cycle_name, cycle_id, user_id)
    )

    updated_cycle = cur.fetchone()

    if not updated_cycle:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Cycle not found")

    conn.commit()
    cur.close()
    conn.close()

    return {
        "message": "Cycle updated",
        "cycle": serialize_cycle(updated_cycle)
    }


@router.post("/cycles/{cycle_id}/budget-adjustments")
def add_cycle_budget(
    cycle_id: int,
    adjustment: CycleBudgetAdjustmentCreate,
    current_user=Depends(get_current_user),
):
    user_id = current_user["id"]
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE financial_cycles
            SET income_amount = income_amount + %s
            WHERE id = %s AND user_id = %s
            RETURNING id, cycle_name, income_amount, start_date, end_date
            """,
            (adjustment.amount, cycle_id, user_id),
        )
        updated_cycle = cur.fetchone()
        if not updated_cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")

        cur.execute(
            """
            INSERT INTO cycle_budget_adjustments (cycle_id, user_id, amount, note)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (cycle_id, user_id, adjustment.amount, adjustment.note),
        )
        adjustment_id, created_at = cur.fetchone()
        conn.commit()
        return {
            "message": "Budget added",
            "adjustment": {
                "id": adjustment_id,
                "amount": round(adjustment.amount, 2),
                "note": adjustment.note,
                "created_at": created_at.isoformat(),
            },
            "cycle": serialize_cycle(updated_cycle),
        }
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.delete("/cycles/{cycle_id}")
def delete_cycle(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM financial_cycles
        WHERE id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )

    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Cycle not found")

    cur.execute(
        """
        SELECT goal_id, COALESCE(SUM(amount), 0)
        FROM goal_contributions
        WHERE cycle_id = %s AND user_id = %s
        GROUP BY goal_id
        """,
        (cycle_id, user_id)
    )
    contribution_totals = cur.fetchall()

    reversed_goal_progress = 0
    for goal_id, amount in contribution_totals:
        cur.execute(
            """
            UPDATE goals
            SET
                current_amount = GREATEST(current_amount - %s, 0),
                updated_at = NOW()
            WHERE id = %s AND user_id = %s
            """,
            (amount, goal_id, user_id)
        )
        reversed_goal_progress += cur.rowcount

    cur.execute(
        """
        DELETE FROM goal_contributions
        WHERE cycle_id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    deleted_goal_contributions = cur.rowcount

    cur.execute(
        """
        UPDATE goals
        SET cycle_id = NULL, updated_at = NOW()
        WHERE cycle_id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    detached_goals = cur.rowcount
    deleted_goals = 0

    cur.execute(
        """
        DELETE FROM transactions
        WHERE cycle_id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    deleted_transactions = cur.rowcount

    cur.execute(
        """
        DELETE FROM financial_cycles
        WHERE id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "message": "Cycle deleted",
        "cycle_id": cycle_id,
        "deleted_goal_contributions": deleted_goal_contributions,
        "deleted_goals": deleted_goals,
        "detached_goals": detached_goals,
        "reversed_goal_progress": reversed_goal_progress,
        "deleted_transactions": deleted_transactions
    }


@router.get("/cycles/compare")
def compare_cycles(
    base_cycle_id: int,
    comparison_cycle_id: int,
    current_user=Depends(get_current_user)
):
    if base_cycle_id == comparison_cycle_id:
        raise HTTPException(
            status_code=400,
            detail="Choose two different cycles to compare"
        )

    user_id = current_user["id"]
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        base = get_cycle_financial_summary(cur, base_cycle_id, user_id)
        comparison = get_cycle_financial_summary(
            cur,
            comparison_cycle_id,
            user_id
        )

        totals = {
            "income": calculate_change(
                comparison["income"],
                base["income"]
            ),
            "total_spending": calculate_change(
                comparison["total_spending"],
                base["total_spending"]
            ),
            "goal_contributions": calculate_change(
                comparison["goal_contributions"],
                base["goal_contributions"]
            ),
            "remaining_balance": calculate_change(
                comparison["remaining_balance"],
                base["remaining_balance"]
            )
        }

        return {
            "base_cycle": base["cycle"],
            "comparison_cycle": comparison["cycle"],
            "totals": totals,
            "categories": compare_breakdown(
                comparison["categories"],
                base["categories"]
            ),
            "subcategories": compare_breakdown(
                comparison["subcategories"],
                base["subcategories"]
            )
        }
    finally:
        cur.close()
        conn.close()


@router.get("/cycles/{cycle_id}/summary")
def get_cycle_summary(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT cycle_name, income_amount, start_date, end_date
        FROM financial_cycles
        WHERE id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    cycle = cur.fetchone()

    if not cycle:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Cycle not found")

    cycle_name = cycle[0] or "Monthly Income"
    income_amount = float(cycle[1])
    start_date = cycle[2]
    end_date = cycle[3]

    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE cycle_id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    total_spent = float(cur.fetchone()[0])

    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM goal_contributions
        WHERE cycle_id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )
    goal_contributions = float(cur.fetchone()[0])

    cur.execute(
        """
        SELECT c.name, COALESCE(SUM(t.amount), 0) AS amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.cycle_id = %s AND t.user_id = %s
        GROUP BY c.name
        ORDER BY amount DESC
        LIMIT 1
        """,
        (cycle_id, user_id)
    )
    top_row = cur.fetchone()
    top_category = top_row[0] if top_row else None

    cur.execute(
        """
        SELECT COUNT(*)
        FROM goals
        WHERE user_id = %s
        AND cycle_id = %s
        AND current_amount >= target_amount
        """,
        (user_id, cycle_id)
    )
    goals_achieved = int(cur.fetchone()[0])

    total_saved = round(
        income_amount - total_spent - goal_contributions,
        2
    )

    summary_text = (
        "You preserved money this cycle. Keep a portion as buffer and move a safe share toward goals."
        if total_saved > 0
        else "This cycle ended tight. Review optional categories before starting the next cycle."
    )

    cur.close()
    conn.close()

    return {
        "cycle_id": cycle_id,
        "cycle_name": cycle_name,
        "income": income_amount,
        "total_spent": total_spent,
        "total_saved": total_saved,
        "goal_contributions": goal_contributions,
        "top_spending_category": top_category,
        "goals_achieved": goals_achieved,
        "summary_text": summary_text
    }
