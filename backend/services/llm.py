"""Single LLM entry point: per-agent provider routing, token accounting, mock mode.

Every agent that needs a language model call goes through this module --
never a provider SDK directly. Centralizing it means: (1) every agent has
one explicit provider/model route, (2) token usage is tracked in one place
for the Agent Timeline and cost budget, and (3) the whole pipeline can run
with LLM_MOCK_MODE=on so it remains testable without network access.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

import httpx

import config

logger = logging.getLogger(__name__)

_anthropic_client = None


class LLMError(RuntimeError):
    """Raised when a real (non-mocked) completion fails after all retries."""


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    task: str
    input_tokens: int
    output_tokens: int
    duration_ms: float
    mocked: bool = False


def _route_for_task(task: str) -> tuple[str, str]:
    route = config.LLM_ROUTES.get(task)
    if route is None:
        raise LLMError(f"Unknown LLM task '{task}' -- add it to config.LLM_ROUTES")
    provider = route["provider"].strip().lower()
    model = route["model"].strip()
    if provider not in {"nvidia", "groq", "openrouter", "anthropic"}:
        raise LLMError(f"Unsupported provider '{provider}' for task '{task}'")
    if not model:
        raise LLMError(f"Missing model for task '{task}'")
    return provider, model


def _provider_config(provider: str) -> tuple[str, str, dict[str, str]]:
    if provider == "nvidia":
        return config.NVIDIA_API_KEY, config.NVIDIA_BASE_URL, {}
    if provider == "groq":
        return config.GROQ_API_KEY, config.GROQ_BASE_URL, {}
    if provider == "openrouter":
        headers = {
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "FinOps Explain AI",
        }
        return config.OPENROUTER_API_KEY, config.OPENROUTER_BASE_URL, headers
    if provider == "anthropic":
        return config.ANTHROPIC_API_KEY, "", {}
    raise LLMError(f"Unsupported provider '{provider}'")


def _complete_openai_compatible(
    *,
    provider: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
) -> tuple[str, int, int]:
    api_key, base_url, extra_headers = _provider_config(provider)
    if not api_key:
        raise LLMError(f"{provider.upper()}_API_KEY is required for task routed to provider '{provider}'")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **extra_headers,
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }

    # Nemotron (and other reasoning-capable) models default to chain-of-
    # thought "thinking" mode that writes its reasoning directly into
    # `content` (no separate reasoning field, unlike Groq's gpt-oss
    # models). On a real, non-trivial prompt this burns the entire
    # max_tokens budget on reasoning before the model ever reaches the
    # structured answer -- confirmed live twice: the analyst prompt hit
    # finish_reason="length" on NVIDIA's direct NIM endpoint at 4096
    # tokens with pure chain-of-thought text and zero JSON output, and
    # separately the report_writer's board-update call did the same via
    # OpenRouter at 320 tokens. The two endpoints need two different
    # toggles for the same underlying behavior:
    if provider == "nvidia":
        # NIM/vLLM-standard chat-template toggle. Response time for the
        # analyst prompt dropped from 50s (truncated, unusable) to 19s
        # (complete, valid JSON) with this set.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    elif provider == "openrouter":
        # OpenRouter does not forward chat_template_kwargs to the
        # underlying provider -- confirmed live (still truncated at
        # finish_reason="length" with pure chain-of-thought text even
        # with that field set). OpenRouter's own unified `reasoning`
        # control is the field it actually honors, and is safely ignored
        # for any routed model that doesn't support reasoning control.
        payload["reasoning"] = {"enabled": False}

    with httpx.Client(timeout=config.LLM_TIMEOUT_SECONDS) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def _complete_anthropic(*, model: str, system: str, user: str, max_tokens: int) -> tuple[str, int, int]:
    global _anthropic_client
    if not config.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is required for task routed to provider 'anthropic'")
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic(
            api_key=config.ANTHROPIC_API_KEY, timeout=config.LLM_TIMEOUT_SECONDS
        )
    response = _anthropic_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return text, response.usage.input_tokens, response.usage.output_tokens


def complete(
    *,
    task: str,
    system: str,
    user: str,
    max_tokens: int | None = None,
    mock_fn: Callable[[], str] | None = None,
) -> LLMResponse:
    """Run one LLM completion for a named task.

    Routing is explicit and non-fallback: config.LLM_ROUTES chooses exactly
    one provider/model per agent task. Retries, if enabled, retry that same
    provider only.
    """
    provider, model = _route_for_task(task)

    start = time.perf_counter()

    if config.LLM_MOCK_MODE:
        text = mock_fn() if mock_fn is not None else f"[mock:{task}] no mock_fn supplied"
        duration_ms = (time.perf_counter() - start) * 1000
        logger.debug("llm.complete task=%s provider=%s model=%s MOCKED", task, provider, model)
        return LLMResponse(
            text=text,
            model=model,
            provider=provider,
            task=task,
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
            mocked=True,
        )

    last_error: Exception | None = None
    for attempt in range(1, config.LLM_MAX_RETRIES + 2):
        try:
            if provider == "anthropic":
                text, input_tokens, output_tokens = _complete_anthropic(
                    model=model,
                    system=system,
                    user=user,
                    max_tokens=max_tokens or config.LLM_MAX_TOKENS,
                )
            else:
                text, input_tokens, output_tokens = _complete_openai_compatible(
                    provider=provider,
                    model=model,
                    system=system,
                    user=user,
                    max_tokens=max_tokens or config.LLM_MAX_TOKENS,
                )
            duration_ms = (time.perf_counter() - start) * 1000
            return LLMResponse(
                text=text,
                model=model,
                provider=provider,
                task=task,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                mocked=False,
            )
        except Exception as exc:  # noqa: BLE001 - broad on purpose, retried below
            last_error = exc
            logger.warning(
                "llm.complete task=%s provider=%s model=%s attempt=%d failed: %s",
                task,
                provider,
                model,
                attempt,
                exc,
            )
            if attempt <= config.LLM_MAX_RETRIES:
                time.sleep(min(2**attempt, 8))

    raise LLMError(
        f"LLM call for task '{task}' failed on provider '{provider}' model '{model}' after retries"
    ) from last_error


def record_usage(token_usage: dict[str, int], response: LLMResponse) -> None:
    """Accumulate a response's token cost into RunState['token_usage'] in place."""
    token_usage["input_tokens"] = token_usage.get("input_tokens", 0) + response.input_tokens
    token_usage["output_tokens"] = token_usage.get("output_tokens", 0) + response.output_tokens
    key = f"{response.task}_calls"
    token_usage[key] = token_usage.get(key, 0) + 1
    provider_key = f"{response.provider}_calls"
    token_usage[provider_key] = token_usage.get(provider_key, 0) + 1
