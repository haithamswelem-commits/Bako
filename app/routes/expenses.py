from fastapi import APIRouter, Depends, HTTPException
from datetime import date
from app.database import get_db_connection
from app.dependencies import get_current_user
from app.metrics import record_expense_created
from pydantic import BaseModel, Field
from typing import Literal, Optional

from app.services.date_service import current_business_date
from app.services.expense_categorization_feedback_service import (
    finalize_categorization_feedback,
)
from app.services.expense_categorization_service import (
    remember_expense_categorization,
)

router = APIRouter()


class ExpenseCreate(BaseModel):
    amount: float
    category_id: int
    subcategory_id: int
    cycle_id: int
    description: Optional[str] = ""
    expense_date: Optional[date] = None
    payment_channel: Literal["cash", "credit_card"] = "cash"
    credit_card_id: Optional[int] = Field(default=None, gt=0)
    categorization_suggestion_id: Optional[int] = Field(default=None, gt=0)


class ExpenseUpdate(BaseModel):
    amount: float
    category_id: int
    subcategory_id: int
    description: Optional[str] = ""
    expense_date: Optional[date] = None
    payment_channel: Literal["cash", "credit_card"] = "cash"
    credit_card_id: Optional[int] = Field(default=None, gt=0)


class CreditCardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CreditCardSettlementUpdate(BaseModel):
    settled: bool


class CreditCardBulkSettlementUpdate(BaseModel):
    cycle_id: int
    settled: bool = True


def validate_category_and_subcategory(
    cur,
    category_id,
    subcategory_id,
    user_id,
):
    cur.execute(
        """
        SELECT id, name
        FROM categories
        WHERE id = %s
        AND user_id = %s
        AND is_active = TRUE
        """,
        (category_id, user_id)
    )

    category = cur.fetchone()

    if not category:
        raise HTTPException(
            status_code=400,
            detail="Invalid spending group"
        )

    cur.execute(
        """
        SELECT subcategories.id
        FROM subcategories
        JOIN categories ON categories.id = subcategories.category_id
        WHERE subcategories.id = %s
        AND subcategories.category_id = %s
        AND categories.user_id = %s
        AND subcategories.is_active = TRUE
        """,
        (
            subcategory_id,
            category_id,
            user_id,
        )
    )

    if not cur.fetchone():
        raise HTTPException(
            status_code=400,
            detail="Invalid expense type for this spending group"
        )

    return category[1]


def validate_cycle(cur, cycle_id, user_id, expense_date=None):
    cur.execute(
        """
        SELECT start_date, end_date
        FROM financial_cycles
        WHERE id = %s
        AND user_id = %s
        """,
        (cycle_id, user_id)
    )

    cycle = cur.fetchone()

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Cycle not found"
        )

    if expense_date and not cycle[0] <= expense_date <= cycle[1]:
        raise HTTPException(
            status_code=400,
            detail="expense_date must be within the financial cycle"
        )


def validate_credit_card(cur, credit_card_id, user_id, payment_channel):
    if payment_channel != "credit_card" or credit_card_id is None:
        return None
    cur.execute(
        """
        SELECT id FROM credit_cards
        WHERE id = %s AND user_id = %s AND is_active = TRUE
        """,
        (credit_card_id, user_id),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=400, detail="Invalid credit card")
    return credit_card_id


@router.post("/expense")
def add_expense(
    expense: ExpenseCreate,
    current_user=Depends(get_current_user)
):
    expense_date = expense.expense_date or current_business_date()
    user_id = current_user["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if expense.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="amount must be greater than zero"
            )

        validate_cycle(
            cur,
            expense.cycle_id,
            user_id,
            expense_date
        )

        category_name = validate_category_and_subcategory(
            cur,
            expense.category_id,
            expense.subcategory_id,
            user_id,
        )
        credit_card_id = validate_credit_card(
            cur, expense.credit_card_id, user_id, expense.payment_channel
        )

        cur.execute(
            """
            INSERT INTO transactions
            (
                cycle_id,
                user_id,
                amount,
                category_id,
                subcategory_id,
                description,
                expense_date,
                payment_channel,
                credit_card_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                expense.cycle_id,
                user_id,
                expense.amount,
                expense.category_id,
                expense.subcategory_id,
                expense.description,
                expense_date,
                expense.payment_channel,
                credit_card_id
            )
        )

        expense_id = cur.fetchone()[0]
        if expense.categorization_suggestion_id is not None:
            finalize_categorization_feedback(
                cur,
                suggestion_event_id=expense.categorization_suggestion_id,
                user_id=user_id,
                expense_id=expense_id,
                final_category_id=expense.category_id,
                final_subcategory_id=expense.subcategory_id,
            )
        remember_expense_categorization(
            cur,
            user_id=user_id,
            description=expense.description,
            category_id=expense.category_id,
            subcategory_id=expense.subcategory_id,
        )
        conn.commit()
        record_expense_created(
            expense.payment_channel,
            category_name,
            expense.amount
        )

        return {
            "message": "Expense added successfully",
            "id": expense_id,
            "user_id": user_id,
            "amount": expense.amount,
            "category_id": expense.category_id,
            "subcategory_id": expense.subcategory_id,
            "cycle_id": expense.cycle_id,
            "expense_date": str(expense_date),
            "payment_channel": expense.payment_channel,
            "credit_card_id": credit_card_id
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as error:
        conn.rollback()
        print(error)
        raise HTTPException(
            status_code=500,
            detail="Failed to add expense"
        )

    finally:
        cur.close()
        conn.close()


@router.put("/expense/{expense_id}")
def update_expense(
    expense_id: int,
    expense: ExpenseUpdate,
    current_user=Depends(get_current_user)
):
    expense_date = expense.expense_date or current_business_date()
    user_id = current_user["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if expense.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="amount must be greater than zero"
            )

        cur.execute(
            """
            SELECT cycle_id
            FROM transactions
            WHERE id = %s
            AND user_id = %s
            """,
            (expense_id, user_id)
        )

        existing_expense = cur.fetchone()

        if not existing_expense:
            raise HTTPException(
                status_code=404,
                detail="Expense not found"
            )

        validate_cycle(
            cur,
            existing_expense[0],
            user_id,
            expense_date
        )

        validate_category_and_subcategory(
            cur,
            expense.category_id,
            expense.subcategory_id,
            user_id,
        )
        credit_card_id = validate_credit_card(
            cur, expense.credit_card_id, user_id, expense.payment_channel
        )

        cur.execute(
            """
            UPDATE transactions
            SET
                amount = %s,
                category_id = %s,
                subcategory_id = %s,
                description = %s,
                expense_date = %s,
                payment_channel = %s,
                credit_card_id = %s,
                settled_at = CASE
                    WHEN %s = 'credit_card' THEN settled_at
                    ELSE NULL
                END
            WHERE id = %s
            AND user_id = %s
            RETURNING id
            """,
            (
                expense.amount,
                expense.category_id,
                expense.subcategory_id,
                expense.description,
                expense_date,
                expense.payment_channel,
                credit_card_id,
                expense.payment_channel,
                expense_id,
                user_id
            )
        )

        updated_expense = cur.fetchone()

        if not updated_expense:
            raise HTTPException(
                status_code=404,
                detail="Expense not found"
            )

        remember_expense_categorization(
            cur,
            user_id=user_id,
            description=expense.description,
            category_id=expense.category_id,
            subcategory_id=expense.subcategory_id,
        )
        conn.commit()

        return {
            "message": "Expense updated successfully",
            "id": expense_id,
            "amount": expense.amount,
            "category_id": expense.category_id,
            "subcategory_id": expense.subcategory_id,
            "expense_date": str(expense_date),
            "payment_channel": expense.payment_channel,
            "credit_card_id": credit_card_id
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as error:
        conn.rollback()
        print(error)
        raise HTTPException(
            status_code=500,
            detail="Failed to update expense"
        )

    finally:
        cur.close()
        conn.close()


@router.delete("/expense/{expense_id}")
def delete_expense(
    expense_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            DELETE FROM transactions
            WHERE id = %s
            AND user_id = %s
            RETURNING id
            """,
            (
                expense_id,
                user_id
            )
        )

        deleted_expense = cur.fetchone()

        if not deleted_expense:
            raise HTTPException(
                status_code=404,
                detail="Expense not found"
            )

        conn.commit()

        return {
            "message": "Expense deleted successfully",
            "id": expense_id
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as error:
        conn.rollback()
        print(error)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete expense"
        )

    finally:
        cur.close()
        conn.close()


@router.get("/credit-cards")
def get_credit_cards(current_user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, name FROM credit_cards
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY LOWER(name), id
            """,
            (current_user["id"],),
        )
        return {"credit_cards": [
            {"id": row[0], "name": row[1]} for row in cur.fetchall()
        ]}
    finally:
        cur.close()
        conn.close()


@router.post("/credit-cards", status_code=201)
def create_credit_card(
    card: CreditCardCreate,
    current_user=Depends(get_current_user),
):
    name = " ".join(card.name.split())
    if not name:
        raise HTTPException(status_code=400, detail="Card name is required")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, name FROM credit_cards
            WHERE user_id = %s AND LOWER(name) = LOWER(%s)
            """,
            (current_user["id"], name),
        )
        existing = cur.fetchone()
        if existing:
            return {"id": existing[0], "name": existing[1]}
        cur.execute(
            """
            INSERT INTO credit_cards (user_id, name)
            VALUES (%s, %s) RETURNING id, name
            """,
            (current_user["id"], name),
        )
        created = cur.fetchone()
        conn.commit()
        return {"id": created[0], "name": created[1]}
    finally:
        cur.close()
        conn.close()


@router.get("/payment-summary")
def get_payment_summary(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        validate_cycle(cur, cycle_id, user_id)
        cur.execute(
            """
            SELECT
                COALESCE(SUM(amount), 0),
                COALESCE(SUM(amount) FILTER (WHERE settled_at IS NULL), 0),
                COALESCE(SUM(amount) FILTER (WHERE settled_at IS NOT NULL), 0),
                COUNT(*) FILTER (WHERE settled_at IS NULL)
            FROM transactions
            WHERE cycle_id = %s
            AND user_id = %s
            AND payment_channel = 'credit_card'
            """,
            (cycle_id, user_id)
        )
        total, outstanding, settled, outstanding_count = cur.fetchone()
        cur.execute(
            """
            SELECT
                COALESCE(cc.name, 'Unassigned card'),
                COALESCE(SUM(t.amount), 0),
                COALESCE(SUM(t.amount) FILTER (WHERE t.settled_at IS NULL), 0),
                COUNT(*) FILTER (WHERE t.settled_at IS NULL)
            FROM transactions t
            LEFT JOIN credit_cards cc ON cc.id = t.credit_card_id
            WHERE t.cycle_id = %s AND t.user_id = %s
            AND t.payment_channel = 'credit_card'
            GROUP BY COALESCE(cc.name, 'Unassigned card')
            ORDER BY COALESCE(
                SUM(t.amount) FILTER (WHERE t.settled_at IS NULL), 0
            ) DESC
            """,
            (cycle_id, user_id),
        )
        cards = cur.fetchall()

        return {
            "cycle_id": cycle_id,
            "total_credit_card": float(total),
            "outstanding_credit_card": float(outstanding),
            "settled_credit_card": float(settled),
            "outstanding_count": int(outstanding_count),
            "cards": [
                {
                    "name": row[0],
                    "total": float(row[1]),
                    "outstanding": float(row[2]),
                    "outstanding_count": int(row[3]),
                }
                for row in cards
            ],
        }
    finally:
        cur.close()
        conn.close()


@router.get("/credit-card-expenses")
def get_credit_card_expenses(
    cycle_id: int,
    current_user=Depends(get_current_user)
):
    user_id = current_user["id"]
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        validate_cycle(cur, cycle_id, user_id)
        cur.execute(
            """
            SELECT
                t.id,
                t.amount,
                t.description,
                t.expense_date,
                t.settled_at,
                c.name,
                s.name,
                cc.id,
                COALESCE(cc.name, 'Unassigned card')
            FROM transactions t
            JOIN categories c ON c.id = t.category_id
            JOIN subcategories s ON s.id = t.subcategory_id
            LEFT JOIN credit_cards cc ON cc.id = t.credit_card_id
            WHERE t.cycle_id = %s
            AND t.user_id = %s
            AND t.payment_channel = 'credit_card'
            ORDER BY t.expense_date DESC, t.id DESC
            """,
            (cycle_id, user_id)
        )
        return {
            "cycle_id": cycle_id,
            "expenses": [
                {
                    "id": row[0],
                    "amount": float(row[1]),
                    "description": row[2] or "",
                    "expense_date": row[3].isoformat(),
                    "settled_at": row[4].isoformat() if row[4] else None,
                    "category": row[5],
                    "subcategory": row[6],
                    "credit_card_id": row[7],
                    "credit_card_name": row[8],
                }
                for row in cur.fetchall()
            ],
        }
    finally:
        cur.close()
        conn.close()


@router.patch("/expense/{expense_id}/settlement")
def update_credit_card_settlement(
    expense_id: int,
    payment: CreditCardSettlementUpdate,
    current_user=Depends(get_current_user),
):
    user_id = current_user["id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE transactions
            SET settled_at = CASE WHEN %s THEN NOW() ELSE NULL END
            WHERE id = %s
            AND user_id = %s
            AND payment_channel = 'credit_card'
            RETURNING id, settled_at
            """,
            (payment.settled, expense_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Credit card expense not found",
            )
        conn.commit()
        return {
            "id": row[0],
            "settled_at": row[1].isoformat() if row[1] else None,
        }
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.patch("/credit-card-expenses/settlement")
def update_all_credit_card_settlements(
    payment: CreditCardBulkSettlementUpdate,
    current_user=Depends(get_current_user),
):
    user_id = current_user["id"]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        validate_cycle(cur, payment.cycle_id, user_id)
        cur.execute(
            """
            UPDATE transactions
            SET settled_at = CASE WHEN %s THEN NOW() ELSE NULL END
            WHERE cycle_id = %s
            AND user_id = %s
            AND payment_channel = 'credit_card'
            """,
            (payment.settled, payment.cycle_id, user_id),
        )
        updated = cur.rowcount
        conn.commit()
        return {"updated": updated, "settled": payment.settled}
    finally:
        cur.close()
        conn.close()
