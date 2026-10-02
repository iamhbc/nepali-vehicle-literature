"""LLM provider abstraction. The Anthropic implementation uses JSON-schema-constrained output."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Protocol

import anthropic
from pydantic import BaseModel

from ..config import Settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """The provider failed; callers fall back to the baseline engine."""


class LLMRefusal(LLMError):
    pass


@dataclass
class LLMResponse:
    data: dict
    model: str
    usage: dict


class LLMProvider(Protocol):
    name: str
    model: str

    async def structured(self, system: str, content: list | str, schema: dict, max_tokens: int) -> LLMResponse: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        self.model = settings.llm_model
        self.effort = settings.llm_effort
        self.client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    async def structured(self, system: str, content: list | str, schema: dict, max_tokens: int) -> LLMResponse:
        try:
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                # The system prompt is stable across requests: cache it.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": content}],
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
                # Re-run a safety-classifier decline on Anthropic's recommended fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise LLMError("The LLM provider rejected the API key.") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("The LLM provider is rate-limiting requests.") from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"The LLM provider rejected the request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"The LLM provider returned HTTP {exc.status_code}.") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the LLM provider.") from exc

        if response.stop_reason == "refusal":
            raise LLMRefusal("The model declined to analyse this input.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The model's answer was cut off before it finished.")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise LLMError("The model returned no structured output.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("The model returned malformed JSON.") from exc
        usage = response.usage
        return LLMResponse(
            data=data,
            model=response.model,
            usage={
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
            },
        )


def image_block(image_bytes: bytes, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(image_bytes).decode()},
    }


def parse_model(model: type[BaseModel], data: dict) -> BaseModel:
    try:
        return model.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError
        raise LLMError(f"Structured output failed validation: {exc}") from exc
