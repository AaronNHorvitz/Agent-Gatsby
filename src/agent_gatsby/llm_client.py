"""Local LLM invocation helpers for Agent Gatsby.

This module abstracts the small set of model transports used by the pipeline.
It supports both OpenAI-compatible and native Ollama chat calls, applies shared
retry and validation behavior, and raises a structured validation error when a
model response is syntactically present but contract-invalid.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
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
    """Raised when a model response fails stage-specific validation.

    Attributes
    ----------
    response_text : str
        Raw model response text that failed validation.
    """

    def __init__(self, message: str, response_text: str) -> None:
        """Initialize the validation error with the raw invalid response.

        Parameters
        ----------
        message : str
            Human-readable validation failure message.
        response_text : str
            Raw model response text that failed validation.

        Returns
        -------
        None
        """

        super().__init__(message)
        self.response_text = response_text


def build_client(config: AppConfig) -> OpenAI:
    """Build the OpenAI-compatible client from configuration.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    OpenAI
        Client configured for the repository's local endpoint.
    """

    return OpenAI(
        base_url=str(config.require_mapping_value("models", "endpoint")),
        api_key=str(config.require_mapping_value("models", "api_key")),
    )


def extract_message_text(response: Any) -> str:
    """Extract message text from an OpenAI-compatible response object.

    Parameters
    ----------
    response : Any
        Chat completion response object.

    Returns
    -------
    str
        Concatenated response text.
    """

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
    """Extract reasoning text when a response transport exposes it.

    Parameters
    ----------
    response : Any
        Chat completion response object.

    Returns
    -------
    str
        Concatenated reasoning text, or an empty string when unavailable.
    """

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
    """Build a compact log description for a completion response.

    Parameters
    ----------
    response : Any
        Chat completion response object.

    Returns
    -------
    str
        Short summary including finish reason and reasoning-text length.
    """

    finish_reason = getattr(response.choices[0], "finish_reason", None) or "unknown"
    reasoning_text = extract_reasoning_text(response)
    return f"finish_reason={finish_reason}, reasoning_len={len(reasoning_text)}"


def derive_native_ollama_endpoint(config: AppConfig) -> str:
    """Derive the native Ollama base URL from the configured endpoint.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    str
        Base URL suitable for native Ollama chat requests.
    """

    parsed = urlparse(str(config.require_mapping_value("models", "endpoint")))
    path = parsed.path or ""
    if path.endswith("/v1"):
        path = path[:-3]
    path = path.rstrip("/")
    return urlunparse(parsed._replace(path=path))


def resolve_transport(config: AppConfig, transport_override: str | None) -> str:
    """Resolve the transport name for a model invocation.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    transport_override : str or None
        Optional transport override for the current call.

    Returns
    -------
    str
        Resolved transport identifier.
    """

    if transport_override:
        return transport_override

    provider = str(config.models.get("provider", "")).strip()
    if provider == "ollama_openai_compatible":
        return OPENAI_COMPATIBLE_TRANSPORT
    if provider == NATIVE_OLLAMA_CHAT_TRANSPORT:
        return NATIVE_OLLAMA_CHAT_TRANSPORT
    return OPENAI_COMPATIBLE_TRANSPORT


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 format.

    Returns
    -------
    str
        Timestamp suffixed with ``Z``.
    """

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def llm_metrics_enabled(config: AppConfig) -> bool:
    """Check whether per-call LLM metrics should be written to disk.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    bool
        ``True`` when LLM call metrics are enabled.
    """

    return bool(config.llm_metrics.get("enabled", False))


def write_llm_call_metric(config: AppConfig, metric: dict[str, Any]) -> None:
    """Append one LLM call metric record to the configured JSONL file.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    metric : dict of str to Any
        Metric payload to append.

    Returns
    -------
    None
    """

    if not llm_metrics_enabled(config):
        return

    output_path = config.llm_metrics_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metric, ensure_ascii=False) + "\n")


def invoke_openai_compatible_completion(
    config: AppConfig,
    *,
    target_model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int,
) -> tuple[str, str]:
    """Invoke the configured OpenAI-compatible chat endpoint.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    target_model : str
        Model name for the request.
    system_prompt : str
        System prompt text.
    user_prompt : str
        User prompt text.
    timeout_seconds : int
        Request timeout in seconds.

    Returns
    -------
    tuple of (str, str)
        Response text and a compact response description for logging.
    """

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
    """Invoke the native Ollama chat API directly.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    target_model : str
        Model name for the request.
    system_prompt : str
        System prompt text.
    user_prompt : str
        User prompt text.
    timeout_seconds : int
        Request timeout in seconds.

    Returns
    -------
    tuple of (str, str)
        Response text and a compact response description for logging.
    """

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
    task_name: str | None = None,
    fallback_model_key: str = "primary_reasoner",
    response_validator: ResponseValidator | None = None,
    transport_override: str | None = None,
) -> str:
    """Invoke a model completion with retries and optional response validation.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    stage_name : str
        Pipeline stage label used for logging.
    system_prompt : str
        System prompt text.
    user_prompt : str
        User prompt text.
    output_path : str or None, optional
        Artifact path associated with the call for logging purposes.
    model_name : str or None, optional
        Explicit model name override.
    task_name : str or None, optional
        Canonical task name used for model routing and metrics.
    fallback_model_key : str, default="primary_reasoner"
        Baseline model key used when the task is not explicitly routed.
    response_validator : callable or None, optional
        Validator applied to the returned text before it is accepted.
    transport_override : str or None, optional
        Explicit transport override for the current call.

    Returns
    -------
    str
        Accepted response text.

    Raises
    ------
    APIConnectionError
        If the OpenAI-compatible client cannot connect.
    APIError
        If the OpenAI-compatible transport returns an API error.
    APITimeoutError
        If the OpenAI-compatible transport times out.
    HTTPError
        If the native Ollama request returns an HTTP error.
    LLMResponseValidationError
        If the response is empty or fails the supplied validator.
    RuntimeError
        If the retry loop exits without capturing a concrete exception.
    URLError
        If the native Ollama request fails at the URL layer.
    ValueError
        If an unsupported transport is requested.
    """

    routing_profile = config.active_model_routing_profile()
    resolved_model_key: str | None = None
    if model_name is not None:
        target_model = model_name
    elif task_name is not None:
        resolved_model_key = config.model_key_for_task(
            task_name,
            fallback_model_key=fallback_model_key,
        )
        target_model = config.model_name_for(resolved_model_key)
    else:
        resolved_model_key = fallback_model_key
        target_model = config.model_name_for(fallback_model_key)

    timeout_seconds = int(config.models.get("timeout_seconds", 180))
    max_retries = int(config.models.get("max_retries", 0))
    retry_backoff_seconds = int(config.models.get("retry_backoff_seconds", 1))
    transport = resolve_transport(config, transport_override)
    call_started_at = time.monotonic()

    last_exception: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            LOGGER.info(
                "LLM call stage=%s task=%s attempt=%d model=%s model_key=%s transport=%s output=%s",
                stage_name,
                task_name or "(default)",
                attempt,
                target_model,
                resolved_model_key or "(explicit)",
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

            try:
                write_llm_call_metric(
                    config,
                    {
                        "generated_at": utc_now_iso(),
                        "stage_name": stage_name,
                        "task_name": task_name or "",
                        "routing_profile": routing_profile,
                        "model_key": resolved_model_key or "",
                        "model_name": target_model,
                        "transport": transport,
                        "output_path": output_path or "",
                        "attempt_count": attempt,
                        "retry_count": attempt - 1,
                        "status": "passed",
                        "validator_enabled": response_validator is not None,
                        "output_length": len(response_text),
                        "duration_ms": round((time.monotonic() - call_started_at) * 1000, 3),
                    },
                )
            except Exception as metrics_exc:  # pragma: no cover - metrics should never break the call path
                LOGGER.warning("Failed to write LLM metrics for stage=%s: %s", stage_name, metrics_exc)

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

    try:
        write_llm_call_metric(
            config,
            {
                "generated_at": utc_now_iso(),
                "stage_name": stage_name,
                "task_name": task_name or "",
                "routing_profile": routing_profile,
                "model_key": resolved_model_key or "",
                "model_name": target_model,
                "transport": transport,
                "output_path": output_path or "",
                "attempt_count": max_retries + 1,
                "retry_count": max_retries,
                "status": "failed",
                "validator_enabled": response_validator is not None,
                "output_length": 0,
                "duration_ms": round((time.monotonic() - call_started_at) * 1000, 3),
                "error_type": type(last_exception).__name__ if last_exception is not None else "",
                "error_message": str(last_exception) if last_exception is not None else "",
            },
        )
    except Exception as metrics_exc:  # pragma: no cover - metrics should never break the call path
        LOGGER.warning("Failed to write LLM metrics for stage=%s: %s", stage_name, metrics_exc)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError(f"LLM call failed without a captured exception for stage {stage_name}")
