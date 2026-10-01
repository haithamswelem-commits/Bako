from app.database import get_db_connection


def percentage(part, total):
    if total <= 0:
        return 0

    return round((float(part) / float(total)) * 100, 2)


def calculate_spending_analysis(
    cycle_id: int,
    user_id: int
):
    conn = get_db_connection()
    cur = conn.cursor()

    # Get user's cycle
    cur.execute(
        """
        SELECT income_amount
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

    income = float(cycle[0])

    # Total spent by user
    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE cycle_id = %s
        AND user_id = %s
        """,
        (
            cycle_id,
            user_id
        )
    )

    total_spent = float(cur.fetchone()[0])

    cur.execute(
        """
        SELECT payment_channel, COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE cycle_id = %s
        AND user_id = %s
        GROUP BY payment_channel
        """,
        (
            cycle_id,
            user_id
        )
    )
    by_payment_channel = {
        row[0]: float(row[1])
        for row in cur.fetchall()
    }

    cur.execute(
        """
        SELECT
            COALESCE(SUM(amount) FILTER (
                WHERE payment_channel = 'credit_card'
                AND settled_at IS NULL
            ), 0),
            COALESCE(SUM(amount) FILTER (
                WHERE payment_channel = 'credit_card'
                AND settled_at IS NOT NULL
            ), 0)
        FROM transactions
        WHERE cycle_id = %s
        AND user_id = %s
        """,
        (
            cycle_id,
            user_id
        )
    )
    credit_card_status_row = cur.fetchone()

    # Spending by category
    cur.execute(
        """
        SELECT
            c.name,
            COALESCE(SUM(t.amount), 0)
        FROM transactions t
        JOIN categories c
            ON t.category_id = c.id
        WHERE t.cycle_id = %s
        AND t.user_id = %s
        GROUP BY c.name
        ORDER BY SUM(t.amount) DESC
        """,
        (
            cycle_id,
            user_id
        )
    )

    category_rows = cur.fetchall()

    by_category = [
        {
            "category": row[0],

            "amount": float(row[1]),

            "percentage_of_total_spent": percentage(
                row[1],
                total_spent
            ),

            "percentage_of_income": percentage(
                row[1],
                income
            )
        }

        for row in category_rows
    ]

    # Spending by subcategory
    cur.execute(
        """
        SELECT
            c.name,
            s.name,
            COALESCE(SUM(t.amount), 0)

        FROM transactions t

        JOIN categories c
            ON t.category_id = c.id

        JOIN subcategories s
            ON t.subcategory_id = s.id

        WHERE t.cycle_id = %s
        AND t.user_id = %s

        GROUP BY c.name, s.name

        ORDER BY SUM(t.amount) DESC
        """,
        (
            cycle_id,
            user_id
        )
    )

    subcategory_rows = cur.fetchall()

    category_totals = {
        item["category"]: item["amount"]
        for item in by_category
    }

    by_subcategory = [
        {
            "category": row[0],

            "subcategory": row[1],

            "amount": float(row[2]),

            "percentage_of_total_spent": percentage(
                row[2],
                total_spent
            ),

            "percentage_of_income": percentage(
                row[2],
                income
            ),

            "percentage_of_category": percentage(
                row[2],
                category_totals[row[0]]
            )
        }

        for row in subcategory_rows
    ]

    top_category = (
        by_category[0]["category"]
        if by_category
        else None
    )

    cur.close()
    conn.close()

    return {
        "cycle_id": cycle_id,

        "user_id": user_id,

        "income": income,

        "total_spent": total_spent,

        "by_payment_channel": {
            "cash": by_payment_channel.get("cash", 0),
            "credit_card": by_payment_channel.get("credit_card", 0)
        },

        "credit_card_status": {
            "outstanding": float(credit_card_status_row[0]),
            "settled": float(credit_card_status_row[1])
        },

        "by_category": by_category,

        "by_subcategory": by_subcategory,

        "top_category": top_category

    }, None
