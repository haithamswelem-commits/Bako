from dataclasses import dataclass

from pydantic import ValidationError

from app.ai.expense_categorization import (
    ExpenseCategorizationRequest,
    ExpenseCategorizationProposal,
    ExpenseCategorizationSuggestion,
    SemanticCategorizationDecision,
    validate_suggestion_against_options,
)
from app.ai.prompts.expense_categorizer_v1 import (
    PROMPT_VERSION,
    build_expense_categorizer_messages,
)
from app.ai.providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMProviderTimeoutError,
)


@dataclass(frozen=True)
class SemanticCategorizationOutcome:
    suggestion: ExpenseCategorizationSuggestion | None
    provider: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int | None
    fallback_reason: str | None
    proposal: ExpenseCategorizationProposal | None = None
    prompt_version: str = PROMPT_VERSION


def suggest_expense_category_semantically(
    request: ExpenseCategorizationRequest,
    provider: LLMProvider | None,
    timeout_seconds: float,
) -> SemanticCategorizationOutcome:
    if provider is None:
        return SemanticCategorizationOutcome(
            suggestion=None,
            provider=None,
            model=None,
            input_tokens=0,
            output_tokens=0,
            latency_ms=None,
            fallback_reason="provider_disabled",
        )

    try:
        response = provider.generate(
            build_expense_categorizer_messages(request),
            timeout_seconds,
        )
    except LLMProviderTimeoutError:
        fallback_reason = "provider_timeout"
    except LLMProviderError as exc:
        if str(exc) == "OpenAI returned no structured response":
            fallback_reason = "provider_no_structured_output"
        else:
            fallback_reason = "provider_unavailable"

    if "fallback_reason" in locals():
        return SemanticCategorizationOutcome(
            suggestion=None,
            provider=None,
            model=None,
            input_tokens=0,
            output_tokens=0,
            latency_ms=None,
            fallback_reason=fallback_reason,
        )

    try:
        decision = SemanticCategorizationDecision.model_validate_json(
            response.content
        )
        suggestion = None
        proposal = None
        if decision.matched:
            category = next(
                item
                for item in request.categories
                if item.id == decision.category_id
            )
            subcategory = next(
                item
                for item in category.subcategories
                if item.id == decision.subcategory_id
            )
            suggestion = ExpenseCategorizationSuggestion(
                source="llm",
                category_id=category.id,
                category_name=category.name,
                subcategory_id=subcategory.id,
                subcategory_name=subcategory.name,
                confidence=decision.confidence,
                reason=decision.reason,
            )
            validate_suggestion_against_options(request, suggestion)
        elif (
            decision.proposed_category_name
            and decision.proposed_subcategory_name
        ):
            proposal = ExpenseCategorizationProposal(
                category_name=decision.proposed_category_name,
                subcategory_name=decision.proposed_subcategory_name,
                confidence=decision.confidence,
                reason=decision.reason,
            )
    except (ValidationError, ValueError, StopIteration):
        return SemanticCategorizationOutcome(
            suggestion=None,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens or 0,
            output_tokens=response.output_tokens or 0,
            latency_ms=response.latency_ms,
            fallback_reason="invalid_provider_response",
        )

    return SemanticCategorizationOutcome(
        suggestion=suggestion,
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens or 0,
        output_tokens=response.output_tokens or 0,
        latency_ms=response.latency_ms,
        fallback_reason=None,
        proposal=proposal,
    )
