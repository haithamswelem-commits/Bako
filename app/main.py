from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_db_connection
from app.metrics import setup_metrics
from app.routes.cycles import router as cycles_router
from app.routes.expenses import router as expenses_router
from app.routes.categories import router as categories_router
from app.routes.categorization import router as categorization_router
from app.routes.budget import router as budget_router
from app.routes.analysis import router as analysis_router
from app.routes.auth import router as auth_router
from app.routes.goals import router as goals_router
from app.routes.ml import router as ml_router
from app.schema import (
    ensure_ai_coach_schema,
    ensure_base_schema,
    ensure_budget_adjustments_schema,
    ensure_credit_cards_schema,
    ensure_cycles_schema,
    ensure_goals_schema,
    ensure_payment_channel_schema,
    ensure_performance_indexes,
    ensure_user_profile_schema,
    ensure_user_categories_schema,
)
from app.telemetry import setup_tracing
from opentelemetry.instrumentation.utils import suppress_instrumentation

app = FastAPI(
    title="Bako API",
    description="Keep your money together",
)
SCHEMA_INIT_LOCK_ID = 2026062601

setup_tracing(app)
setup_metrics(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://localhost:3000"
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(cycles_router)
app.include_router(expenses_router)
app.include_router(categories_router)
app.include_router(categorization_router)
app.include_router(budget_router)
app.include_router(analysis_router)
app.include_router(goals_router)
app.include_router(ml_router)


@app.on_event("startup")
def initialize_schema():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT pg_advisory_lock(%s)",
            (SCHEMA_INIT_LOCK_ID,)
        )

        ensure_base_schema()
        ensure_ai_coach_schema()
        ensure_user_categories_schema()
        ensure_cycles_schema()
        ensure_goals_schema()
        ensure_payment_channel_schema()
        ensure_credit_cards_schema()
        ensure_budget_adjustments_schema()
        ensure_user_profile_schema()
        ensure_performance_indexes()
    finally:
        try:
            cur.execute(
                "SELECT pg_advisory_unlock(%s)",
                (SCHEMA_INIT_LOCK_ID,)
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()


@app.get("/daily-details")
def get_daily_details(cycle_id: int, date: str):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE cycle_id = %s
        AND DATE(created_at) = %s
        """,
        (cycle_id, date)
    )

    total_spent = cur.fetchone()[0]

    cur.execute(
        """
        SELECT
            categories.name,
            SUM(transactions.amount)
        FROM transactions
        JOIN categories
            ON transactions.category_id = categories.id
        WHERE transactions.cycle_id = %s
        AND DATE(transactions.created_at) = %s
        GROUP BY categories.name
        """,
        (cycle_id, date)
    )

    rows = cur.fetchall()

    by_category = []

    for row in rows:
        category_name = row[0]
        amount = float(row[1])

        percentage = (
            (amount / total_spent) * 100
            if total_spent > 0
            else 0
        )

        by_category.append({
            "category": category_name,
            "amount": amount,
            "percentage": round(percentage, 1)
        })

    cur.close()
    conn.close()

    return {
        "date": date,
        "total_spent": float(total_spent),
        "by_category": by_category
    }

@app.get("/live")
def liveness_check():
    return {
        "status": "alive"
    }


@app.get("/ready")
def readiness_check():
    conn = None
    cur = None

    try:
        with suppress_instrumentation():
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")

        return {
            "status": "ready",
            "database": "reachable"
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is not reachable"
        ) from exc
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
