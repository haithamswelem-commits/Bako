from typing import Literal


FeedbackOutcome = Literal["accepted", "corrected"]


def get_categorization_feedback_report(cur, *, user_id: int) -> dict:
    """Summarize one user's categorizer feedback without expense text."""

    cur.execute(
        """
        SELECT
            COUNT(*) AS total_suggestions,
            COUNT(*) FILTER (WHERE outcome = 'pending') AS pending_suggestions,
            COUNT(*) FILTER (WHERE outcome = 'accepted') AS accepted_suggestions,
            COUNT(*) FILTER (WHERE outcome = 'corrected') AS corrected_suggestions,
            COUNT(*) FILTER (WHERE source = 'user_memory')
                AS personal_memory_suggestions,
            COALESCE(AVG(input_tokens + output_tokens), 0) AS average_tokens,
            COALESCE(AVG(latency_ms) FILTER (WHERE latency_ms IS NOT NULL), 0)
                AS average_latency_ms
        FROM expense_categorization_feedback
        WHERE user_id = %s
        """,
        (user_id,),
    )
    (
        total,
        pending,
        accepted,
        corrected,
        personal_memory_suggestions,
        average_tokens,
        average_latency_ms,
    ) = cur.fetchone()

    completed = accepted + corrected
    cur.execute(
        """
        SELECT
            COALESCE(suggested_category.name, feedback.proposed_category_name),
            COALESCE(
                suggested_subcategory.name,
                feedback.proposed_subcategory_name
            ),
            final_category.name,
            final_subcategory.name,
            COUNT(*) AS correction_count
        FROM expense_categorization_feedback AS feedback
        LEFT JOIN categories AS suggested_category
            ON suggested_category.id = feedback.suggested_category_id
        LEFT JOIN subcategories AS suggested_subcategory
            ON suggested_subcategory.id = feedback.suggested_subcategory_id
        LEFT JOIN categories AS final_category
            ON final_category.id = feedback.final_category_id
        LEFT JOIN subcategories AS final_subcategory
            ON final_subcategory.id = feedback.final_subcategory_id
        WHERE feedback.user_id = %s
        AND feedback.outcome = 'corrected'
        GROUP BY
            COALESCE(
                suggested_category.name,
                feedback.proposed_category_name
            ),
            COALESCE(
                suggested_subcategory.name,
                feedback.proposed_subcategory_name
            ),
            final_category.name,
            final_subcategory.name
        ORDER BY correction_count DESC, 1, 2, 3, 4
        LIMIT 10
        """,
        (user_id,),
    )
    frequent_corrections = [
        {
            "suggested_category": row[0],
            "suggested_type": row[1],
            "final_category": row[2],
            "final_type": row[3],
            "count": row[4],
        }
        for row in cur.fetchall()
    ]

    return {
        "scope": "authenticated_user",
        "total_suggestions": total,
        "completed_suggestions": completed,
        "pending_suggestions": pending,
        "accepted_suggestions": accepted,
        "corrected_suggestions": corrected,
        "personal_memory_suggestions": personal_memory_suggestions,
        "openai_calls_avoided": personal_memory_suggestions,
        "acceptance_rate_percent": (
            round((accepted / completed) * 100, 1) if completed else 0.0
        ),
        "correction_rate_percent": (
            round((corrected / completed) * 100, 1) if completed else 0.0
        ),
        "average_tokens_per_suggestion": round(float(average_tokens), 1),
        "average_latency_ms": round(float(average_latency_ms), 1),
        "frequently_corrected_pairs": frequent_corrections,
    }


def record_categorization_suggestion(
    cur,
    *,
    user_id: int,
    suggestion,
    proposal,
    provider: str | None,
    model: str | None,
    prompt_version: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int | None,
) -> int | None:
    """Store trusted inference metadata without duplicating expense text."""

    if suggestion is None and proposal is None:
        return None

    source = suggestion.source if suggestion is not None else proposal.source
    confidence = (
        suggestion.confidence if suggestion is not None else proposal.confidence
    )
    cur.execute(
        """
        INSERT INTO expense_categorization_feedback (
            user_id,
            source,
            provider,
            model,
            prompt_version,
            suggested_category_id,
            suggested_subcategory_id,
            proposed_category_name,
            proposed_subcategory_name,
            confidence,
            input_tokens,
            output_tokens,
            latency_ms
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        RETURNING id
        """,
        (
            user_id,
            source,
            provider,
            model,
            prompt_version,
            suggestion.category_id if suggestion is not None else None,
            suggestion.subcategory_id if suggestion is not None else None,
            proposal.category_name if proposal is not None else None,
            proposal.subcategory_name if proposal is not None else None,
            confidence,
            input_tokens,
            output_tokens,
            latency_ms,
        ),
    )
    return cur.fetchone()[0]


def finalize_categorization_feedback(
    cur,
    *,
    suggestion_event_id: int,
    user_id: int,
    expense_id: int,
    final_category_id: int,
    final_subcategory_id: int,
) -> FeedbackOutcome | None:
    """Attach a pending suggestion to a successful user-owned expense."""

    cur.execute(
        """
        SELECT
            suggested_category_id,
            suggested_subcategory_id,
            proposed_category_name,
            proposed_subcategory_name
        FROM expense_categorization_feedback
        WHERE id = %s
        AND user_id = %s
        AND outcome = 'pending'
        AND expense_id IS NULL
        FOR UPDATE
        """,
        (suggestion_event_id, user_id),
    )
    row = cur.fetchone()
    if not row:
        return None

    (
        suggested_category_id,
        suggested_subcategory_id,
        proposed_category_name,
        proposed_subcategory_name,
    ) = row

    if suggested_category_id is not None:
        accepted = (
            suggested_category_id == final_category_id
            and suggested_subcategory_id == final_subcategory_id
        )
    else:
        cur.execute(
            """
            SELECT categories.name, subcategories.name
            FROM categories
            JOIN subcategories
                ON subcategories.category_id = categories.id
            WHERE categories.id = %s
            AND subcategories.id = %s
            AND categories.user_id = %s
            """,
            (final_category_id, final_subcategory_id, user_id),
        )
        names = cur.fetchone()
        accepted = bool(
            names
            and proposed_category_name
            and proposed_subcategory_name
            and names[0].casefold() == proposed_category_name.casefold()
            and names[1].casefold() == proposed_subcategory_name.casefold()
        )

    outcome: FeedbackOutcome = "accepted" if accepted else "corrected"
    cur.execute(
        """
        UPDATE expense_categorization_feedback
        SET
            expense_id = %s,
            final_category_id = %s,
            final_subcategory_id = %s,
            outcome = %s,
            completed_at = NOW()
        WHERE id = %s AND user_id = %s
        """,
        (
            expense_id,
            final_category_id,
            final_subcategory_id,
            outcome,
            suggestion_event_id,
            user_id,
        ),
    )
    return outcome
