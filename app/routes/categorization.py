import os
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from opentelemetry import trace

from app.ai.expense_categorization import (
    ApprovedCategory,
    ApprovedSubcategory,
    ExpenseCategorizationRequest,
)
from app.database import get_db_connection
from app.dependencies import get_current_user
from app.ai.providers.factory import build_expense_categorization_provider
from app.ai.providers.base import LLMProviderError
from app.services.ai_chat_history_service import (
    get_ai_usage_summary,
    record_ai_usage_event,
)
from app.services.expense_categorization_service import (
    suggest_expense_category,
    suggest_expense_category_from_memory,
)
from app.services.expense_categorization_feedback_service import (
    get_categorization_feedback_report,
    record_categorization_suggestion,
)
from app.services.semantic_expense_categorization_service import (
    suggest_expense_category_semantically,
)


router = APIRouter(tags=["expense-categorization"])
logger = logging.getLogger(__name__)


def _timeout_seconds() -> float:
    return min(
        max(float(os.getenv("AI_EXPLANATION_TIMEOUT_SECONDS", "8")), 1.0),
        30.0,
    )


class ExpenseCategorizationInput(BaseModel):
    description: str = Field(min_length=2, max_length=200)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not any(character.isalpha() for character in normalized):
            raise ValueError("Description must include at least one letter")
        return normalized


@router.get("/expense-category-feedback-report")
def get_expense_category_feedback_report(
    current_user=Depends(get_current_user),
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        return get_categorization_feedback_report(
            cur,
            user_id=current_user["id"],
        )
    finally:
        cur.close()
        conn.close()


def _approved_categories(rows) -> tuple[ApprovedCategory, ...]:
    categories = {}
    for category_id, category_name, subcategory_id, subcategory_name in rows:
        # Legacy records created before name validation must never be offered
        # to the AI provider as valid classification choices.
        if not any(character.isalpha() for character in category_name):
            continue
        if not any(character.isalpha() for character in subcategory_name):
            continue

        category = categories.setdefault(
            category_id,
            {
                "id": category_id,
                "name": category_name,
                "subcategories": [],
            },
        )
        category["subcategories"].append(
            ApprovedSubcategory(id=subcategory_id, name=subcategory_name)
        )

    return tuple(
        ApprovedCategory(
            id=category["id"],
            name=category["name"],
            subcategories=tuple(category["subcategories"]),
        )
        for category in categories.values()
    )


@router.post("/expense-category-suggestion")
def get_expense_category_suggestion(
    payload: ExpenseCategorizationInput,
    current_user=Depends(get_current_user),
):
    current_span = trace.get_current_span()
    current_span.set_attribute("bako.category.feature", "smart_categories")
    current_span.set_attribute(
        "bako.category.capture_sensitive_inputs",
        os.getenv("OTEL_CAPTURE_SENSITIVE_INPUTS", "false").lower() == "true",
    )

    if os.getenv("OTEL_CAPTURE_SENSITIVE_INPUTS", "false").lower() == "true":
        current_span.set_attribute(
            "bako.category.description",
            payload.description,
        )
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                categories.id,
                categories.name,
                subcategories.id,
                subcategories.name
            FROM categories
            JOIN subcategories
                ON subcategories.category_id = categories.id
            WHERE categories.user_id = %s
            AND categories.is_active = TRUE
            AND subcategories.is_active = TRUE
            ORDER BY categories.name, subcategories.name
            """,
            (current_user["id"],),
        )
        categories = _approved_categories(cur.fetchall())
        request = ExpenseCategorizationRequest(
            description=payload.description,
            categories=categories,
        )
        memory_suggestion = suggest_expense_category_from_memory(
            cur,
            request=request,
            user_id=current_user["id"],
        )
    finally:
        cur.close()
        conn.close()

    usage_summary = None
    suggestion = memory_suggestion
    proposal = None
    provider_name = None
    model_name = None
    prompt_version = "user-memory-v1"
    input_tokens = 0
    output_tokens = 0
    latency_ms = 0
    openai_called = False
    fallback_reason = None
    result_source = "user_memory" if memory_suggestion else "none"

    if suggestion is None:
        try:
            provider = build_expense_categorization_provider()
        except (LLMProviderError, ValueError):
            provider = None
        semantic_outcome = suggest_expense_category_semantically(
            request=request,
            provider=provider,
            timeout_seconds=_timeout_seconds(),
        )
        openai_called = provider is not None
        fallback_reason = semantic_outcome.fallback_reason
        proposal = semantic_outcome.proposal
        provider_name = semantic_outcome.provider
        model_name = semantic_outcome.model
        prompt_version = semantic_outcome.prompt_version
        input_tokens = semantic_outcome.input_tokens
        output_tokens = semantic_outcome.output_tokens
        latency_ms = semantic_outcome.latency_ms

        if input_tokens + output_tokens > 0:
            try:
                record_ai_usage_event(
                    user_id=current_user["id"],
                    feature="expense_categorization",
                    provider=provider_name or "unknown",
                    model=model_name or "unknown",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                usage_summary = get_ai_usage_summary(
                    user_id=current_user["id"]
                )
            except Exception as exc:
                # Telemetry must not turn a valid suggestion into a failure.
                logger.warning(
                    "Could not record categorization usage (%s)",
                    type(exc).__name__,
                )

        suggestion = semantic_outcome.suggestion

        if suggestion is not None:
            result_source = "llm"
        elif proposal is not None:
            result_source = "llm_proposal"

        if provider is None or semantic_outcome.fallback_reason:
            suggestion = suggest_expense_category(request)
            result_source = "deterministic_fallback" if suggestion else "none"

    suggestion_event_id = None
    if suggestion is not None or proposal is not None:
        feedback_conn = get_db_connection()
        feedback_cur = feedback_conn.cursor()
        try:
            suggestion_event_id = record_categorization_suggestion(
                feedback_cur,
                user_id=current_user["id"],
                suggestion=suggestion,
                proposal=proposal,
                provider=provider_name,
                model=model_name,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            )
            feedback_conn.commit()
        except Exception as exc:
            feedback_conn.rollback()
            logger.warning(
                "Could not record categorization feedback (%s)",
                type(exc).__name__,
            )
            suggestion_event_id = None
        finally:
            feedback_cur.close()
            feedback_conn.close()

    current_span.set_attribute(
        "bako.category.provider_called",
        openai_called,
    )
    current_span.set_attribute(
        "bako.category.result_source",
        result_source,
    )
    current_span.set_attribute(
        "bako.category.suggestion_found",
        suggestion is not None,
    )
    current_span.set_attribute(
        "bako.category.proposal_created",
        proposal is not None,
    )
    current_span.set_attribute(
        "bako.category.response_valid",
        openai_called and fallback_reason is None,
    )
    current_span.set_attribute(
        "bako.category.input_tokens",
        input_tokens,
    )
    current_span.set_attribute(
        "bako.category.output_tokens",
        output_tokens,
    )
    current_span.set_attribute(
        "bako.category.provider_latency_ms",
        latency_ms or 0,
    )

    if provider_name:
        current_span.set_attribute(
            "bako.category.provider",
            provider_name,
        )

    if model_name:
        current_span.set_attribute(
            "bako.category.model",
            model_name,
        )

    if fallback_reason:
        current_span.set_attribute(
            "bako.category.fallback_reason",
            fallback_reason,
        )

    if suggestion is None:
        response = {
            "suggestion": None,
            "proposal": (
                proposal.model_dump() if proposal else None
            ),
            "message": (
                "No existing match. Review this new pair before creating it."
                if proposal
                else "No suitable match yet. Please choose or add the two fields."
            ),
        }
        if suggestion_event_id is not None:
            response["suggestion_event_id"] = suggestion_event_id
        if usage_summary is not None:
            response["usage_summary"] = usage_summary
        return response

    response = {
        "suggestion": suggestion.model_dump(),
        "message": (
            "Matched your previous choice. Review it before adding the expense."
            if suggestion.source == "user_memory"
            else "Suggestion ready. Review it before adding the expense."
        ),
    }
    if suggestion_event_id is not None:
        response["suggestion_event_id"] = suggestion_event_id
    if usage_summary is not None:
        response["usage_summary"] = usage_summary
    return response
