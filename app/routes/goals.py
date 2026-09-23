from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import get_db_connection
from app.dependencies import get_current_user
from app.metrics import record_goal_contribution
from app.services.date_service import current_business_date
from app.services.goals_service import get_user_goals, serialize_goal


router = APIRouter()

GoalType = Literal[
    "required_bill",
    "savings",
    "charity",
    "lifestyle",
    "event",
    "debt"
]
GoalPriority = Literal["high", "medium", "low"]


class GoalCreate(BaseModel):
    cycle_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=120)
    type: GoalType
    target_amount: float = Field(gt=0)
    current_amount: float = Field(default=0, ge=0)
    deadline_date: Optional[date] = None
    priority: GoalPriority = "medium"
    auto_rule: Optional[str] = Field(default=None, max_length=80)
    is_active: bool = True


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    type: Optional[GoalType] = None
    target_amount: Optional[float] = Field(default=None, gt=0)
    current_amount: Optional[float] = Field(default=None, ge=0)
    deadline_date: Optional[date] = None
    priority: Optional[GoalPriority] = None
    auto_rule: Optional[str] = Field(default=None, max_length=80)
    is_active: Optional[bool] = None


class GoalContribution(BaseModel):
    amount: float = Field(gt=0)
    cycle_id: Optional[int] = None
    contribution_date: Optional[date] = None


GOAL_COLUMNS = """
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
"""


def validate_cycle(cur, cycle_id, user_id):
    if cycle_id is None:
        return

    cur.execute(
        """
        SELECT id
        FROM financial_cycles
        WHERE id = %s AND user_id = %s
        """,
        (cycle_id, user_id)
    )

    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Cycle not found")


@router.post("/goals")
def create_goal(
    goal: GoalCreate,
    current_user=Depends(get_current_user)
):
    if goal.current_amount > goal.target_amount:
        raise HTTPException(
            status_code=400,
            detail="current_amount cannot exceed target_amount"
        )

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        validate_cycle(cur, goal.cycle_id, current_user["id"])

        cur.execute(
            f"""
            INSERT INTO goals (
                user_id,
                cycle_id,
                name,
                type,
                target_amount,
                current_amount,
                deadline_date,
                priority,
                auto_rule,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {GOAL_COLUMNS}
            """,
            (
                current_user["id"],
                goal.cycle_id,
                goal.name.strip(),
                goal.type,
                goal.target_amount,
                goal.current_amount,
                goal.deadline_date,
                goal.priority,
                goal.auto_rule.strip() if goal.auto_rule else None,
                goal.is_active
            )
        )
        created_goal = serialize_goal(cur.fetchone())
        conn.commit()
        return created_goal
    finally:
        cur.close()
        conn.close()


@router.get("/goals")
def list_goals(
    active_only: bool = False,
    cycle_id: Optional[int] = None,
    current_user=Depends(get_current_user)
):
    return {
        "goals": get_user_goals(
            current_user["id"],
            active_only=active_only,
            cycle_id=cycle_id
        )
    }


@router.put("/goals/{goal_id}")
def update_goal(
    goal_id: int,
    goal: GoalUpdate,
    current_user=Depends(get_current_user)
):
    updates = goal.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "name" in updates:
        updates["name"] = updates["name"].strip()
    if updates.get("auto_rule"):
        updates["auto_rule"] = updates["auto_rule"].strip()

    allowed_columns = {
        "name",
        "type",
        "target_amount",
        "current_amount",
        "deadline_date",
        "priority",
        "auto_rule",
        "is_active"
    }
    assignments = [
        f"{column} = %s"
        for column in updates
        if column in allowed_columns
    ]
    values = [
        updates[column]
        for column in updates
        if column in allowed_columns
    ]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            f"""
            UPDATE goals
            SET {", ".join(assignments)}, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING {GOAL_COLUMNS}
            """,
            (*values, goal_id, current_user["id"])
        )
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Goal not found")

        updated_goal = serialize_goal(row)
        if updated_goal["current_amount"] > updated_goal["target_amount"]:
            raise HTTPException(
                status_code=400,
                detail="current_amount cannot exceed target_amount"
            )

        conn.commit()
        return updated_goal
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.delete("/goals/{goal_id}")
def delete_goal(
    goal_id: int,
    current_user=Depends(get_current_user)
):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            DELETE FROM goals
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (goal_id, current_user["id"])
        )

        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Goal not found")

        conn.commit()
        return {"message": "Goal deleted", "id": goal_id}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.post("/goals/{goal_id}/contribute")
def contribute_to_goal(
    goal_id: int,
    contribution: GoalContribution,
    current_user=Depends(get_current_user)
):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT
                target_amount,
                current_amount,
                deadline_date,
                created_at
            FROM goals
            WHERE id = %s
            AND user_id = %s
            AND is_active = TRUE
            FOR UPDATE
            """,
            (
                goal_id,
                current_user["id"]
            )
        )
        existing_goal = cur.fetchone()

        if not existing_goal:
            raise HTTPException(
                status_code=404,
                detail="Active goal not found"
            )

        if contribution.cycle_id is None:
            raise HTTPException(
                status_code=400,
                detail="Contribution cycle is required"
            )

        remaining_goal_amount = max(
            float(existing_goal[0]) - float(existing_goal[1]),
            0
        )
        applied_amount = round(
            min(float(contribution.amount), remaining_goal_amount),
            2
        )

        if applied_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Goal is already complete"
            )

        contribution_date = (
            contribution.contribution_date or current_business_date()
        )
        goal_deadline = existing_goal[2]
        goal_created_date = existing_goal[3].date()

        if contribution_date < goal_created_date:
            raise HTTPException(
                status_code=400,
                detail="Contribution date must not be before goal creation"
            )

        if goal_deadline and contribution_date > goal_deadline:
            raise HTTPException(
                status_code=400,
                detail="Contribution date must not be after goal deadline"
            )

        cur.execute(
            """
            SELECT id
            FROM financial_cycles
            WHERE id = %s
            AND user_id = %s
            AND %s BETWEEN start_date AND end_date
            """,
            (
                contribution.cycle_id,
                current_user["id"],
                contribution_date
            )
        )

        if not cur.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Contribution date must be within the selected cycle"
            )

        cur.execute(
            f"""
            UPDATE goals
            SET
                current_amount = LEAST(
                    target_amount,
                    current_amount + %s
                ),
                updated_at = NOW()
            WHERE id = %s
            AND user_id = %s
            AND is_active = TRUE
            RETURNING {GOAL_COLUMNS}
            """,
            (
                applied_amount,
                goal_id,
                current_user["id"]
            )
        )
        row = cur.fetchone()

        updated_goal = serialize_goal(row)

        cur.execute(
            """
            INSERT INTO goal_contributions (
                user_id,
                goal_id,
                cycle_id,
                amount,
                contribution_date
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                current_user["id"],
                goal_id,
                contribution.cycle_id,
                applied_amount,
                contribution_date
            )
        )

        conn.commit()
        record_goal_contribution(applied_amount)
        return updated_goal
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
