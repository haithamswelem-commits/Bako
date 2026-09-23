import os

from app.database import get_db_connection


DEFAULT_OPENAI_TPD_LIMIT = 2_000_000


def _daily_token_limit() -> int:
    raw_value = os.getenv(
        "OPENAI_TOKENS_PER_DAY_LIMIT",
        str(DEFAULT_OPENAI_TPD_LIMIT),
    )
    try:
        limit = int(raw_value)
    except ValueError as error:
        raise ValueError(
            "OPENAI_TOKENS_PER_DAY_LIMIT must be an integer"
        ) from error
    if limit <= 0:
        raise ValueError(
            "OPENAI_TOKENS_PER_DAY_LIMIT must be greater than zero"
        )
    return limit


def record_ai_exchange(
    *,
    user_id: int,
    cycle_id: int,
    question: str,
    explanation,
    topics,
    metadata,
) -> int:
    """Store one completed question and its validated answer."""

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ai_coach_exchanges (
                user_id,
                cycle_id,
                question,
                headline,
                explanation,
                recommended_action,
                response_source,
                topics,
                provider,
                model,
                input_tokens,
                output_tokens,
                used_fallback,
                fallback_reason
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                user_id,
                cycle_id,
                question,
                explanation.headline,
                explanation.explanation,
                explanation.recommended_action,
                explanation.source,
                list(topics),
                metadata.provider,
                metadata.model,
                metadata.input_tokens or 0,
                metadata.output_tokens or 0,
                metadata.used_fallback,
                metadata.fallback_reason,
            ),
        )
        exchange_id = cur.fetchone()[0]
        conn.commit()
        return exchange_id
    finally:
        cur.close()
        conn.close()


def get_ai_chat_history(
    *,
    user_id: int,
    cycle_id: int,
    limit: int = 100,
) -> list[dict] | None:
    """Return the user's saved exchanges in reading order."""

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
            FROM financial_cycles
            WHERE id = %s AND user_id = %s
            """,
            (cycle_id, user_id),
        )
        if not cur.fetchone():
            return None

        cur.execute(
            """
            SELECT
                id,
                question,
                headline,
                explanation,
                recommended_action,
                response_source,
                topics,
                created_at
            FROM (
                SELECT
                    id,
                    question,
                    headline,
                    explanation,
                    recommended_action,
                    response_source,
                    topics,
                    created_at
                FROM ai_coach_exchanges
                WHERE user_id = %s AND cycle_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
            ) recent
            ORDER BY created_at, id
            """,
            (user_id, cycle_id, limit),
        )
        return [
            {
                "id": row[0],
                "question": row[1],
                "headline": row[2],
                "explanation": row[3],
                "recommended_action": row[4],
                "source": row[5],
                "topics": row[6] or [],
                "created_at": row[7].isoformat(),
            }
            for row in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


def record_ai_usage_event(
    *,
    user_id: int,
    feature: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Record provider usage for AI features that are not chat exchanges."""

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ai_usage_events (
                user_id,
                feature,
                provider,
                model,
                input_tokens,
                output_tokens
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                feature,
                provider,
                model,
                input_tokens,
                output_tokens,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_ai_usage_summary(*, user_id: int) -> dict:
    """Summarize one user's Bako-recorded usage for the UTC day."""

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(total_tokens), 0),
                COUNT(*) FILTER (WHERE total_tokens > 0)
            FROM (
                SELECT
                    user_id,
                    input_tokens + output_tokens AS total_tokens,
                    created_at
                FROM ai_coach_exchanges
                UNION ALL
                SELECT
                    user_id,
                    input_tokens + output_tokens AS total_tokens,
                    created_at
                FROM ai_usage_events
            ) usage
            WHERE user_id = %s
            AND created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')
                AT TIME ZONE 'UTC'
            AND created_at < (
                DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')
                + INTERVAL '1 day'
            ) AT TIME ZONE 'UTC'
            """,
            (user_id,),
        )
        tokens_used, requests = cur.fetchone()
        limit = _daily_token_limit()
        return {
            "tokens_used_today": int(tokens_used),
            "daily_token_limit": limit,
            "usage_percentage": round(
                (int(tokens_used) / limit) * 100,
                2,
            ),
            "requests_today": int(requests),
            "scope": "authenticated_user_usage",
            "provider_limit_scope": "shared_openai_project_model_limit",
            "window_timezone": "UTC",
        }
    finally:
        cur.close()
        conn.close()
