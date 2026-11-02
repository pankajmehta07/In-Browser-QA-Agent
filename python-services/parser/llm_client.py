import asyncio
import math
import os
import time
from collections import deque
from dataclasses import dataclass, field

from openai import AsyncOpenAI, RateLimitError

from utils.logger import log_info


@dataclass
class LLMProvider:
    name: str
    label: str
    key_env: str
    model_env: str
    default_model: str
    base_url: str
    tokens_per_minute: int | None
    requests_per_minute: int | None
    max_input_tokens: int
    max_output_tokens: int
    token_param: str
    reasoning_effort: str | None
    _requests: deque = field(default_factory=deque, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def model(self) -> str:
        return os.getenv(self.model_env) or self.default_model

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.key_env) or None


# Limits reflect each provider's free tier for the default model.
PROVIDERS: dict[str, LLMProvider] = {
    "google": LLMProvider(
        name="google",
        label="Google AI Studio",
        key_env="GEMINI_API_KEY",
        model_env="GEMINI_MODEL",
        default_model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        tokens_per_minute=250_000,
        requests_per_minute=10,
        max_input_tokens=30_000,
        max_output_tokens=4096,
        token_param="max_tokens",
        reasoning_effort="low",
    ),
    "groq": LLMProvider(
        name="groq",
        label="Groq",
        key_env="GROQ_API_KEY",
        model_env="GROQ_MODEL",
        default_model="openai/gpt-oss-120b",
        base_url="https://api.groq.com/openai/v1",
        tokens_per_minute=8000,
        requests_per_minute=30,
        max_input_tokens=6000,
        max_output_tokens=2000,
        token_param="max_completion_tokens",
        reasoning_effort="low",
    ),
    "nvidia": LLMProvider(
        name="nvidia",
        label="NVIDIA",
        key_env="NVIDIA_API_KEY",
        model_env="NVIDIA_MODEL",
        default_model="meta/llama-3.3-70b-instruct",
        base_url="https://integrate.api.nvidia.com/v1",
        tokens_per_minute=None,
        requests_per_minute=40,
        max_input_tokens=30_000,
        max_output_tokens=2000,
        token_param="max_tokens",
        reasoning_effort=None,
    ),
}

_active_provider = os.getenv("LLM_PROVIDER", "groq")


def set_provider(name: str) -> LLMProvider:
    """Select the provider for all later LLM calls; raise if it is unknown or has no key."""
    global _active_provider
    provider = PROVIDERS.get(name)
    if provider is None:
        raise RuntimeError(f"Unknown LLM provider '{name}'. Choose one of: {', '.join(PROVIDERS)}.")
    if not provider.api_key:
        raise RuntimeError(f"{provider.key_env} is not set. Add it to .env to use {provider.label}.")
    _active_provider = name
    return provider


def get_provider() -> LLMProvider:
    provider = PROVIDERS.get(_active_provider)
    if provider is None:
        raise RuntimeError(f"Unknown LLM provider '{_active_provider}'.")
    return provider


def estimate_input_tokens(messages: list[dict[str, str]]) -> int:
    return 256 + sum(
        16 + math.ceil(
            (len(message["role"].encode("utf-8")) + len(message["content"].encode("utf-8"))) / 3
        )
        for message in messages
    )


def _budget_wait(provider: LLMProvider, reserved_tokens: int) -> float:
    now = time.monotonic()
    while provider._requests and now - provider._requests[0][0] >= 60:
        provider._requests.popleft()
    if not provider._requests:
        return 0.0
    over_requests = (
        provider.requests_per_minute is not None
        and len(provider._requests) >= provider.requests_per_minute
    )
    over_tokens = (
        provider.tokens_per_minute is not None
        and sum(tokens for _, tokens in provider._requests) + reserved_tokens > provider.tokens_per_minute
    )
    if over_requests or over_tokens:
        return max(0.1, 60 - (now - provider._requests[0][0]))
    return 0.0


async def budgeted_completion(
    messages: list[dict[str, str]],
    max_completion_tokens: int | None = None,
    **options,
):
    provider = get_provider()
    api_key = provider.api_key
    if not api_key:
        raise RuntimeError(f"{provider.key_env} is not set in the environment.")

    max_completion_tokens = max_completion_tokens or provider.max_output_tokens
    input_tokens = estimate_input_tokens(messages)
    reserved_tokens = input_tokens + max_completion_tokens
    if input_tokens > provider.max_input_tokens or (
        provider.tokens_per_minute is not None and reserved_tokens > provider.tokens_per_minute
    ):
        raise ValueError(f"{provider.label} request exceeds the estimated per-request token limit.")

    request_options = {provider.token_param: max_completion_tokens, **options}
    if provider.reasoning_effort:
        request_options["reasoning_effort"] = provider.reasoning_effort

    async with provider._lock:
        async with AsyncOpenAI(api_key=api_key, base_url=provider.base_url, max_retries=0) as client:
            for attempt in range(2):
                while (wait_seconds := _budget_wait(provider, reserved_tokens)) > 0:
                    log_info(f"{provider.label} rate budget reached; waiting {wait_seconds:.1f}s before the next request...")
                    await asyncio.sleep(wait_seconds)

                request_time = time.monotonic()
                provider._requests.append((request_time, reserved_tokens))
                try:
                    response = await client.chat.completions.create(
                        model=provider.model,
                        messages=messages,
                        **request_options,
                    )
                except RateLimitError as error:
                    if attempt:
                        raise
                    try:
                        wait_seconds = max(0.1, float(error.response.headers.get("retry-after", "60")))
                    except (TypeError, ValueError):
                        wait_seconds = 60.0
                    log_info(f"{provider.label} rate limit reached; waiting {wait_seconds:.1f}s before one retry...")
                    await asyncio.sleep(wait_seconds)
                    continue
                except BaseException:
                    if provider._requests and provider._requests[-1][0] == request_time:
                        provider._requests.pop()
                    raise

                if response.usage is not None:
                    prompt_details = getattr(response.usage, "prompt_tokens_details", None)
                    cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
                    accounted_tokens = max(0, (response.usage.total_tokens or 0) - cached_tokens)
                    provider._requests[-1] = (request_time, accounted_tokens + 256)
                    log_info(
                        f"{provider.label} usage: "
                        f"prompt_tokens={response.usage.prompt_tokens}, "
                        f"cached_prompt_tokens={cached_tokens}, "
                        f"completion_tokens={response.usage.completion_tokens}, "
                        f"rate_budget_tokens={accounted_tokens}"
                    )
                return response
    raise RuntimeError(f"{provider.label} request could not be completed within the rate limit.")
