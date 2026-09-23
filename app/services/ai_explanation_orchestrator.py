from dataclasses import dataclass

from pydantic import ValidationError

from app.ai.contracts import (
    CoachExplanation,
    CoachExplanationRequest,
    validate_explanation_against_facts,
)
from app.ai.prompts.budget_coach_v3 import build_budget_coach_messages
from app.ai.providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMProviderResponse,
    LLMProviderTimeoutError,
)
from app.services.ai_explanation_service import (
    build_clarification_explanation,
    build_conversation_explanation,
    build_fallback_explanation,
    build_unsupported_question_explanation,
    build_unknown_goal_explanation,
)


@dataclass(frozen=True)
class ExplanationOperationalMetadata:
    provider: str | None
    model: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    attempts: int
    used_fallback: bool
    fallback_reason: str | None


@dataclass(frozen=True)
class CoachExplanationOutcome:
    explanation: CoachExplanation
    metadata: ExplanationOperationalMetadata


def _local_outcome(
    explanation: CoachExplanation,
    reason: str,
) -> CoachExplanationOutcome:
    return CoachExplanationOutcome(
        explanation=explanation,
        metadata=ExplanationOperationalMetadata(
            provider=None,
            model=None,
            latency_ms=None,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=None,
            attempts=0,
            used_fallback=False,
            fallback_reason=reason,
        ),
    )


def conversation_outcome(
    request: CoachExplanationRequest,
    conversation_kind: str,
    first_name: str | None,
    language: str,
) -> CoachExplanationOutcome:
    return _local_outcome(
        build_conversation_explanation(
            request,
            conversation_kind,
            first_name,
            language,
        ),
        reason="local_conversation",
    )


def clarification_outcome(
    request: CoachExplanationRequest,
    available_goal_names: tuple[str, ...],
) -> CoachExplanationOutcome:
    return _local_outcome(
        build_clarification_explanation(request, available_goal_names),
        reason="clarification_needed",
    )


def unknown_goal_outcome(
    request: CoachExplanationRequest,
    requested_goal_name: str,
    available_goal_names: tuple[str, ...],
) -> CoachExplanationOutcome:
    """Return a grounded answer without spending tokens on a missing goal."""

    return CoachExplanationOutcome(
        explanation=build_unknown_goal_explanation(
            request,
            requested_goal_name,
            available_goal_names,
        ),
        metadata=ExplanationOperationalMetadata(
            provider=None,
            model=None,
            latency_ms=None,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=None,
            attempts=0,
            used_fallback=True,
            fallback_reason="goal_not_found",
        ),
    )


def unsupported_question_outcome(
    request: CoachExplanationRequest,
) -> CoachExplanationOutcome:
    """Decline an unrelated question before creating an OpenAI provider."""

    return CoachExplanationOutcome(
        explanation=build_unsupported_question_explanation(request),
        metadata=ExplanationOperationalMetadata(
            provider=None,
            model=None,
            latency_ms=None,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=None,
            attempts=0,
            used_fallback=True,
            fallback_reason="unsupported_question",
        ),
    )


def _fallback_outcome(
    request: CoachExplanationRequest,
    reason: str,
    attempts: int,
    provider_response: LLMProviderResponse | None = None,
) -> CoachExplanationOutcome:
    return CoachExplanationOutcome(
        explanation=build_fallback_explanation(request),
        metadata=ExplanationOperationalMetadata(
            provider=(
                provider_response.provider if provider_response else None
            ),
            model=provider_response.model if provider_response else None,
            latency_ms=(
                provider_response.latency_ms if provider_response else None
            ),
            input_tokens=(
                provider_response.input_tokens if provider_response else None
            ),
            output_tokens=(
                provider_response.output_tokens if provider_response else None
            ),
            estimated_cost_usd=(
                provider_response.estimated_cost_usd
                if provider_response
                else None
            ),
            attempts=attempts,
            used_fallback=True,
            fallback_reason=reason,
        ),
    )


def generate_coach_explanation(
    request: CoachExplanationRequest,
    user_question: str,
    provider: LLMProvider | None,
    timeout_seconds: float = 3.0,
    max_attempts: int = 2,
    disabled_reason: str = "provider_disabled",
) -> CoachExplanationOutcome:
    """Generate, validate, and safely fall back without changing finances."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3")

    if provider is None:
        return _fallback_outcome(
            request,
            reason=disabled_reason,
            attempts=0,
        )

    messages = build_budget_coach_messages(request, user_question)
    response = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = provider.generate(messages, timeout_seconds)
            break
        except LLMProviderTimeoutError:
            if attempt == max_attempts:
                return _fallback_outcome(
                    request,
                    reason="provider_timeout",
                    attempts=attempt,
                )
        except LLMProviderError:
            if attempt == max_attempts:
                return _fallback_outcome(
                    request,
                    reason="provider_unavailable",
                    attempts=attempt,
                )

    if response is None:
        return _fallback_outcome(
            request,
            reason="provider_unavailable",
            attempts=max_attempts,
        )

    try:
        explanation = CoachExplanation.model_validate_json(response.content)
        validate_explanation_against_facts(request, explanation)
    except (ValidationError, ValueError):
        return _fallback_outcome(
            request,
            reason="invalid_provider_response",
            attempts=attempt,
            provider_response=response,
        )

    return CoachExplanationOutcome(
        explanation=explanation,
        metadata=ExplanationOperationalMetadata(
            provider=response.provider,
            model=response.model,
            latency_ms=response.latency_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost_usd=response.estimated_cost_usd,
            attempts=attempt,
            used_fallback=False,
            fallback_reason=None,
        ),
    )
