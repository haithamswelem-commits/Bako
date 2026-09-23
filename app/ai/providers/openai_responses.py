import os
import time
import logging
from typing import Any

from pydantic import BaseModel

from app.ai.contracts import CoachExplanation
from app.ai.providers.base import (
    LLMProviderError,
    LLMProviderResponse,
    LLMProviderTimeoutError,
)


DEFAULT_MODEL = "gpt-5.4-nano"
logger = logging.getLogger(__name__)

_TIMEOUT_ERROR_NAMES = {
    "APITimeoutError",
    "ConnectTimeout",
    "ReadTimeout",
    "TimeoutException",
}
_PROVIDER_ERROR_NAMES = {
    "APIConnectionError",
    "APIError",
    "AuthenticationError",
    "BadRequestError",
    "InternalServerError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
}


def _create_client(api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMProviderError(
            "The openai package is not installed. Install requirements.txt."
        ) from exc

    return OpenAI(api_key=api_key)


class OpenAIResponsesProvider:
    """OpenAI Responses API adapter for explanation-only shadow calls."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        response_format: type[BaseModel] = CoachExplanation,
    ) -> None:
        self.model = (model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip()
        if not self.model:
            raise ValueError("OpenAI model cannot be empty")
        self.response_format = response_format

        if client is not None:
            self._client = client
            return

        resolved_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        if not resolved_key:
            raise LLMProviderError(
                "OPENAI_API_KEY is required for a real provider call"
            )
        self._client = _create_client(resolved_key)

    def generate(
        self,
        messages: tuple[dict[str, str], ...],
        timeout_seconds: float,
    ) -> LLMProviderResponse:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        started = time.perf_counter()
        try:
            client = self._client.with_options(
                timeout=timeout_seconds,
                max_retries=0,
            )
            response = client.responses.parse(
                model=self.model,
                input=list(messages),
                text_format=self.response_format,
                store=False,
            )
        except Exception as exc:
            error_name = type(exc).__name__
            if error_name in _TIMEOUT_ERROR_NAMES:
                raise LLMProviderTimeoutError(str(exc)) from exc
            logger.warning("OpenAI provider call failed (%s)", error_name)
            if error_name in _PROVIDER_ERROR_NAMES:
                raise LLMProviderError(str(exc)) from exc
            raise LLMProviderError(
                f"OpenAI provider returned an unusable response ({error_name})"
            ) from exc

        parsed = response.output_parsed
        if parsed is None:
            raise LLMProviderError(
                "OpenAI returned no structured response"
            )

        usage = getattr(response, "usage", None)
        latency_ms = round((time.perf_counter() - started) * 1000)
        return LLMProviderResponse(
            content=parsed.model_dump_json(),
            provider=self.provider_name,
            model=getattr(response, "model", self.model),
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            estimated_cost_usd=None,
        )
