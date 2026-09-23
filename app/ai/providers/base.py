from dataclasses import dataclass
from typing import Protocol


class LLMProviderError(RuntimeError):
    """Base error for expected provider failures."""


class LLMProviderTimeoutError(LLMProviderError):
    """Raised when a provider does not answer within the configured timeout."""


@dataclass(frozen=True)
class LLMProviderResponse:
    """Provider response plus operational metadata, before validation."""

    content: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


class LLMProvider(Protocol):
    """Any provider adapter must implement this small interface."""

    def generate(
        self,
        messages: tuple[dict[str, str], ...],
        timeout_seconds: float,
    ) -> LLMProviderResponse:
        ...
