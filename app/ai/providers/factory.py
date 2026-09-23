import os

from app.ai.expense_categorization import SemanticCategorizationDecision
from app.ai.providers.base import LLMProvider
from app.ai.providers.openai_responses import OpenAIResponsesProvider


DISABLED_PROVIDER_NAMES = {"", "disabled", "fallback", "none"}


def build_shadow_explanation_provider() -> LLMProvider | None:
    """Return the explicitly configured shadow provider, if one is enabled."""

    provider_name = os.getenv(
        "AI_EXPLANATION_PROVIDER",
        "disabled",
    ).strip().lower()

    if provider_name in DISABLED_PROVIDER_NAMES:
        return None
    if provider_name == "openai":
        return OpenAIResponsesProvider()

    supported = "disabled, openai"
    raise ValueError(
        f"Unsupported AI_EXPLANATION_PROVIDER '{provider_name}'. "
        f"Supported values: {supported}."
    )


def build_expense_categorization_provider() -> LLMProvider | None:
    """Use the configured provider with the categorization response contract."""

    provider_name = os.getenv(
        "AI_EXPLANATION_PROVIDER",
        "disabled",
    ).strip().lower()
    if provider_name in DISABLED_PROVIDER_NAMES:
        return None
    if provider_name == "openai":
        return OpenAIResponsesProvider(
            response_format=SemanticCategorizationDecision,
        )
    raise ValueError(
        f"Unsupported AI_EXPLANATION_PROVIDER '{provider_name}'."
    )
