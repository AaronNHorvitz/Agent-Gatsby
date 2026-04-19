"""
Minimal local LLM client wrapper for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

from agent_gatsby.config import AppConfig

LOGGER = logging.getLogger(__name__)

ResponseValidator = Callable[[str], None]
OPENAI_COMPATIBLE_TRANSPORT = "openai_compatible"
NATIVE_OLLAMA_CHAT_TRANSPORT = "ollama_native_chat"


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


def extract_reasoning_text(response: Any) -> str:
    reasoning = getattr(response.choices[0].message, "reasoning", None)
    if isinstance(reasoning, str):
        return reasoning
    if isinstance(reasoning, list):
        chunks: list[str] = []
        for item in reasoning:
            if isinstance(item, dict) and "text" in item:
                chunks.append(str(item["text"]))
            elif hasattr(item, "text"):
                chunks.append(str(item.text))
        return "".join(chunks)
    return str(reasoning or "")


def describe_response(response: Any) -> str:
    finish_reason = getattr(response.choices[0], "finish_reason", None) or "unknown"
    reasoning_text = extract_reasoning_text(response)
    return f"finish_reason={finish_reason}, reasoning_len={len(reasoning_text)}"


def derive_native_ollama_endpoint(config: AppConfig) -> str:
    parsed = urlparse(str(config.require_mapping_value("models", "endpoint")))
    path = parsed.path or ""
    if path.endswith("/v1"):
        path = path[:-3]
    path = path.rstrip("/")
    return urlunparse(parsed._replace(path=path))


def resolve_transport(config: AppConfig, transport_override: str | None) -> str:
    if transport_override:
        return transport_override

    provider = str(config.models.get("provider", "")).strip()
    if provider == "ollama_openai_compatible":
        return OPENAI_COMPATIBLE_TRANSPORT
    if provider == NATIVE_OLLAMA_CHAT_TRANSPORT:
        return NATIVE_OLLAMA_CHAT_TRANSPORT
    return OPENAI_COMPATIBLE_TRANSPORT


def invoke_openai_compatible_completion(
    config: AppConfig,
    *,
    target_model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int,
) -> tuple[str, str]:
    client = build_client(config)
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
    return extract_message_text(response).strip(), describe_response(response)


def invoke_native_ollama_chat_completion(
    config: AppConfig,
    *,
    target_model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int,
) -> tuple[str, str]:
    endpoint = derive_native_ollama_endpoint(config) + "/api/chat"
    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": float(config.llm_defaults.get("temperature", 0.2)),
            "top_p": float(config.llm_defaults.get("top_p", 0.9)),
            "num_predict": int(config.llm_defaults.get("max_tokens", 4096)),
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw_payload = json.loads(response.read().decode("utf-8"))

    message = raw_payload.get("message", {})
    response_text = str(message.get("content", raw_payload.get("response", "")) or "").strip()
    finish_reason = raw_payload.get("done_reason", "unknown")
    return response_text, f"finish_reason={finish_reason}, reasoning_len=0"


def invoke_text_completion(
    config: AppConfig,
    *,
    stage_name: str,
    system_prompt: str,
    user_prompt: str,
    output_path: str | None = None,
    model_name: str | None = None,
    response_validator: ResponseValidator | None = None,
    transport_override: str | None = None,
) -> str:
    target_model = model_name or config.model_name_for("primary_reasoner")
    timeout_seconds = int(config.models.get("timeout_seconds", 180))
    max_retries = int(config.models.get("max_retries", 0))
    retry_backoff_seconds = int(config.models.get("retry_backoff_seconds", 1))
    transport = resolve_transport(config, transport_override)

    last_exception: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            LOGGER.info(
                "LLM call stage=%s attempt=%d model=%s transport=%s output=%s",
                stage_name,
                attempt,
                target_model,
                transport,
                output_path or "(none)",
            )
            if transport == OPENAI_COMPATIBLE_TRANSPORT:
                response_text, response_description = invoke_openai_compatible_completion(
                    config,
                    target_model=target_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    timeout_seconds=timeout_seconds,
                )
            elif transport == NATIVE_OLLAMA_CHAT_TRANSPORT:
                response_text, response_description = invoke_native_ollama_chat_completion(
                    config,
                    target_model=target_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    timeout_seconds=timeout_seconds,
                )
            else:
                raise ValueError(f"Unsupported LLM transport: {transport}")

            if not response_text:
                raise LLMResponseValidationError(
                    f"Model returned empty content ({response_description})",
                    response_text,
                )

            if response_validator is not None:
                try:
                    response_validator(response_text)
                except ValueError as exc:
                    raise LLMResponseValidationError(str(exc), response_text) from exc

            return response_text
        except (
            APIConnectionError,
            APIError,
            APITimeoutError,
            RateLimitError,
            HTTPError,
            URLError,
            LLMResponseValidationError,
        ) as exc:
            last_exception = exc
            if attempt > max_retries:
                break
            LOGGER.warning("LLM call failed at stage=%s attempt=%d: %s", stage_name, attempt, exc)
            time.sleep(retry_backoff_seconds)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError(f"LLM call failed without a captured exception for stage {stage_name}")
