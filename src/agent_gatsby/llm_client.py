"""
Minimal local LLM client wrapper for Agent Gatsby.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

from agent_gatsby.config import AppConfig

LOGGER = logging.getLogger(__name__)

ResponseValidator = Callable[[str], None]


class LLMResponseValidationError(ValueError):
    def __init__(self, message: str, response_text: str) -> None:
        super().__init__(message)
        self.response_text = response_text


def build_client(config: AppConfig) -> OpenAI:
    return OpenAI(
        base_url=str(config.require_mapping_value("models", "endpoint")),
        api_key=str(config.require_mapping_value("models", "api_key")),
    )


def extract_message_text(response: Any) -> str:
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                chunks.append(str(item["text"]))
            elif hasattr(item, "text"):
                chunks.append(str(item.text))
        return "".join(chunks)
    return str(content or "")


def invoke_text_completion(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    user_prompt: str,
    output_path: str | None = None,
    model_name: str | None = None,
    response_validator: ResponseValidator | None = None,
) -> str:
    client = build_client(config)
    target_model = model_name or config.model_name_for("primary_reasoner")
    timeout_seconds = int(config.models.get("timeout_seconds", 180))
    max_retries = int(config.models.get("max_retries", 0))
    retry_backoff_seconds = int(config.models.get("retry_backoff_seconds", 1))

    last_exception: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            LOGGER.info(
                "LLM call stage=%s attempt=%d model=%s output=%s",
                stage_name,
                attempt,
                target_model,
                output_path or "(none)",
            )
            response = client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=float(config.llm_defaults.get("temperature", 0.2)),
                top_p=float(config.llm_defaults.get("top_p", 0.9)),
                max_tokens=int(config.llm_defaults.get("max_tokens", 4096)),
                timeout=timeout_seconds,
            )
            response_text = extract_message_text(response).strip()
            if not response_text:
                raise LLMResponseValidationError("Model returned empty content", response_text)

            if response_validator is not None:
                try:
                    response_validator(response_text)
                except ValueError as exc:
                    raise LLMResponseValidationError(str(exc), response_text) from exc

            return response_text
        except (APIConnectionError, APIError, APITimeoutError, RateLimitError, LLMResponseValidationError) as exc:
            last_exception = exc
            if attempt > max_retries:
                break
            LOGGER.warning("LLM call failed at stage=%s attempt=%d: %s", stage_name, attempt, exc)
            time.sleep(retry_backoff_seconds)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError(f"LLM call failed without a captured exception for stage {stage_name}")
