import logging
import math
import os
from dataclasses import dataclass

import litellm
from litellm import Router
from litellm.router import RetryPolicy

from utils.logger import log_info, log_warning


REQUEST_TIMEOUT_SECONDS = 90
litellm.drop_params = True  # drop options a fallback provider does not support
litellm.suppress_debug_info = True
# Fallbacks are reported by this module; LiteLLM's per-call warnings (e.g. Gemini 3 temperature deprecation) are noise here.
logging.getLogger("LiteLLM").setLevel(logging.ERROR)


@dataclass(frozen=True)
class LLMProvider:
    name: str
    label: str
    key_env: str
    model_env: str
    default_model: str
    default_fallback_model: str | None
    litellm_prefix: str
    requests_per_minute: int | None
    tokens_per_minute: int | None
    max_input_tokens: int
    max_output_tokens: int
    reasoning_effort: str | None

    @property
    def model(self) -> str:
        return os.getenv(self.model_env) or self.default_model

    @property
    def fallback_model(self) -> str | None:
        return os.getenv(self.model_env.replace("_MODEL", "_FALLBACK_MODEL")) or self.default_fallback_model

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
        default_model="gemini-3.6-flash",
        default_fallback_model="gemini-3.5-flash-lite",
        litellm_prefix="gemini",
        requests_per_minute=10,
        tokens_per_minute=250_000,
        max_input_tokens=30_000,
        # Gemini counts thinking tokens against this limit.
        max_output_tokens=4096,
        reasoning_effort="low",
    ),
    "groq": LLMProvider(
        name="groq",
        label="Groq",
        key_env="GROQ_API_KEY",
        model_env="GROQ_MODEL",
        default_model="openai/gpt-oss-120b",
        default_fallback_model="openai/gpt-oss-20b",
        litellm_prefix="groq",
        requests_per_minute=30,
        tokens_per_minute=8000,
        max_input_tokens=6000,
        max_output_tokens=2000,
        reasoning_effort="low",
    ),
    "nvidia": LLMProvider(
        name="nvidia",
        label="NVIDIA",
        key_env="NVIDIA_API_KEY",
        model_env="NVIDIA_MODEL",
        default_model="mistralai/mistral-large-4-1t-a52b",
        default_fallback_model="mistralai/mistral-large-4-1t-a52b",
        litellm_prefix="nvidia_nim",
        requests_per_minute=40,
        tokens_per_minute=None,
        max_input_tokens=30_000,
        max_output_tokens=2000,
        reasoning_effort=None,
    ),
}

_active_provider = os.getenv("LLM_PROVIDER", "groq")
_router: Router | None = None
_router_provider: str | None = None


def set_provider(name: str) -> LLMProvider:
    """Select the primary provider for all later LLM calls; raise if it is unknown or has no key."""
    global _active_provider, _router
    provider = PROVIDERS.get(name)
    if provider is None:
        raise RuntimeError(f"Unknown LLM provider '{name}'. Choose one of: {', '.join(PROVIDERS)}.")
    if not provider.api_key:
        raise RuntimeError(f"{provider.key_env} is not set. Add it to .env to use {provider.label}.")
    _active_provider = name
    _router = None
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


def _cross_provider_fallback_enabled() -> bool:
    return os.getenv("LLM_CROSS_PROVIDER_FALLBACK", "true").strip().lower() not in ("0", "false", "no")


def _deployment(group: str, provider: LLMProvider, model: str) -> dict:
    params = {
        "model": f"{provider.litellm_prefix}/{model}",
        "api_key": provider.api_key,
        "timeout": REQUEST_TIMEOUT_SECONDS,
        "max_tokens": provider.max_output_tokens,
    }
    if provider.reasoning_effort:
        params["reasoning_effort"] = provider.reasoning_effort
    if provider.requests_per_minute:
        params["rpm"] = provider.requests_per_minute
    if provider.tokens_per_minute:
        params["tpm"] = provider.tokens_per_minute
    return {
        "model_name": group,
        "litellm_params": params,
        "model_info": {"id": group, "max_input_tokens": provider.max_input_tokens},
    }


def _model_groups(primary: LLMProvider) -> list[tuple[str, LLMProvider, str]]:
    """Ordered (group, provider, model) chain: chosen provider first, then other configured providers."""
    providers = [primary]
    if _cross_provider_fallback_enabled():
        providers += [p for p in PROVIDERS.values() if p.name != primary.name and p.api_key]
    groups = []
    for provider in providers:
        groups.append((provider.name, provider, provider.model))
        if provider.fallback_model and provider.fallback_model != provider.model:
            groups.append((f"{provider.name}-fallback", provider, provider.fallback_model))
    return groups


def _build_router(primary: LLMProvider) -> Router:
    groups = _model_groups(primary)
    chain = [group for group, _, _ in groups[1:]]
    return Router(
        model_list=[_deployment(group, provider, model) for group, provider, model in groups],
        fallbacks=[{primary.name: chain}] if chain else [],
        context_window_fallbacks=[{primary.name: chain}] if chain else [],
        enable_pre_call_checks=True,
        retry_policy=RetryPolicy(
            AuthenticationErrorRetries=0,
            BadRequestErrorRetries=0,
            NotFoundErrorRetries=0,
            # A model that timed out is unlikely to answer faster on retry.
            TimeoutErrorRetries=0,
            RateLimitErrorRetries=1,
            InternalServerErrorRetries=2,
            ServiceUnavailableErrorRetries=2,
            DefaultRetries=1,
        ),
        allowed_fails=1,
        cooldown_time=30,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def _get_router() -> tuple[Router, LLMProvider]:
    global _router, _router_provider
    provider = get_provider()
    if not provider.api_key:
        raise RuntimeError(f"{provider.key_env} is not set in the environment.")
    if _router is None or _router_provider != provider.name:
        _router, _router_provider = _build_router(provider), provider.name
        chain = " -> ".join(f"{p.label} ({model})" for _, p, model in _model_groups(provider))
        log_info(f"LLM routing order: {chain}")
    return _router, provider


async def budgeted_completion(messages: list[dict[str, str]], **options):
    """Complete a chat request on the chosen provider, retrying and falling back via LiteLLM."""
    router, provider = _get_router()
    if estimate_input_tokens(messages) > provider.max_input_tokens:
        raise ValueError(f"{provider.label} request exceeds the estimated per-request token limit.")

    try:
        response = await router.acompletion(model=provider.name, messages=messages, **options)
    except Exception as error:
        raise RuntimeError(
            f"All configured LLM providers failed: {error}. Try again later or choose another provider."
        ) from error

    served_by = (getattr(response, "_hidden_params", None) or {}).get("model_id") or provider.name
    if served_by != provider.name:
        log_warning(f"{provider.label} ({provider.model}) was unavailable; answered by fallback '{served_by}' ({response.model}).")
    if response.usage is not None:
        prompt_details = getattr(response.usage, "prompt_tokens_details", None)
        cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
        log_info(
            f"LLM usage ({served_by}): "
            f"prompt_tokens={response.usage.prompt_tokens}, "
            f"cached_prompt_tokens={cached_tokens}, "
            f"completion_tokens={response.usage.completion_tokens}"
        )
    return response
