"""Central LLM entry point — provider-neutral.

Single place for:
  - Client construction (honoring LLM_BASE_URL for proxy/gateway setups)
  - Model tier resolution (review tier / gen tier, via env vars)
  - structured_call() — forced tool-use returning schema-validated output
  - simple_call() — plain text completion for prompts that don't need a schema

The provider SDK is an OPTIONAL, lazily-imported backend. It is resolved from
the LLM_PROVIDER env var (a Python module name exposing a messages API compatible
with the calls below). No provider is required to import this package or to run
the deterministic pipeline stages.
"""
from __future__ import annotations

import importlib
import os
import time
from typing import Any, Dict, Optional, Type, Union

__all__ = [
    "MODEL_REVIEW",
    "MODEL_GEN",
    "model_for",
    "get_client",
    "structured_call",
    "simple_call",
]

# Generic, non-branded default model identifiers. Override via env vars.
MODEL_REVIEW = os.getenv("LLM_MODEL_REVIEW", "review-model")
MODEL_GEN    = os.getenv("LLM_MODEL_GEN",    "gen-model")

_TIER_ENV = {
    "review": ("LLM_MODEL_REVIEW", MODEL_REVIEW),
    "gen":    ("LLM_MODEL_GEN",    MODEL_GEN),
}

# Name of the provider SDK module to import lazily. Set to whichever
# OpenAI-compatible / provider client package is installed in your environment.
_PROVIDER_ENV = "LLM_PROVIDER"


def model_for(tier: str) -> str:
    env_var, default = _TIER_ENV.get(tier, ("", MODEL_GEN))
    return os.getenv(env_var, default)


def _load_provider():
    """Lazily import the configured LLM provider module.

    Raises a clear error if none is configured/installed.
    """
    provider = os.getenv(_PROVIDER_ENV)
    if not provider:
        raise RuntimeError(
            "No LLM provider configured — set LLM_PROVIDER / LLM_API_KEY. "
            "LLM_PROVIDER must name an installed provider SDK module exposing a "
            "messages API (client.messages.create(...))."
        )
    try:
        return importlib.import_module(provider)
    except ImportError as exc:
        raise RuntimeError(
            f"LLM provider module {provider!r} could not be imported. "
            "Install the provider SDK or set LLM_PROVIDER to an available module. "
            "(No LLM provider configured — set LLM_PROVIDER / LLM_API_KEY.)"
        ) from exc


def get_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    """Construct an LLM client from the configured provider.

    The provider module is expected to expose a client factory. This helper
    tries a couple of common construction patterns and passes api_key / base_url
    through when supported.
    """
    provider = _load_provider()
    key = api_key or os.getenv("LLM_API_KEY")
    url = base_url or os.getenv("LLM_BASE_URL")
    if not key:
        raise RuntimeError(
            "No LLM provider configured — set LLM_PROVIDER / LLM_API_KEY. "
            "Export LLM_API_KEY or pass api_key= to get_client()."
        )
    kwargs: Dict[str, Any] = {"api_key": key}
    if url:
        kwargs["base_url"] = url

    # Try common client factory conventions exposed by provider SDKs.
    # A provider-specific factory name can be supplied via LLM_CLIENT_CLASS.
    candidates = []
    override = os.getenv("LLM_CLIENT_CLASS")
    if override:
        candidates.append(override)
    candidates += ["Client", "LLM"]
    factory = None
    for attr in candidates:
        factory = getattr(provider, attr, None)
        if factory is not None:
            break
    if factory is None:
        raise RuntimeError(
            f"Provider module {provider.__name__!r} exposes no known client factory "
            "(expected a top-level Client/LLM class)."
        )
    return factory(**kwargs)


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    return not (isinstance(status, int) and 400 <= status < 500)


def structured_call(
    system: str,
    user: str,
    schema: Union[Dict[str, Any], Type[Any]],
    *,
    tier: str = "gen",
    model: Optional[str] = None,
    client: Optional[Any] = None,
    tool_name: str = "emit_output",
    max_tokens: int = 8192,
    max_retries: int = 3,
    backoff_base: float = 1.0,
    cache_system: bool = True,
) -> Any:
    """Call the LLM and return schema-validated structured output via forced tool use."""
    resolved_model = model or model_for(tier)
    _is_pydantic = isinstance(schema, type) and hasattr(schema, "model_json_schema")
    json_schema = schema.model_json_schema() if _is_pydantic else schema

    system_param: Any = (
        [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        if cache_system else system
    )
    tool = {
        "name": tool_name,
        "description": "Emit the structured result conforming to the schema.",
        "input_schema": json_schema,
    }
    if client is None:
        client = get_client()

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=resolved_model,
                max_tokens=max_tokens,
                system=system_param,
                messages=[{"role": "user", "content": user}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc) or attempt == max_retries - 1:
                raise
            time.sleep(backoff_base * (2 ** attempt))

    if last_exc:
        raise last_exc

    if getattr(msg, "stop_reason", None) == "max_tokens":
        raise ValueError(f"Response hit max_tokens={max_tokens}; output truncated.")

    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            data = block.input
            return schema(**data) if _is_pydantic else data

    raise ValueError(f"No tool_use block for tool {tool_name!r} in response.")


def simple_call(
    system: str,
    user: str,
    *,
    tier: str = "gen",
    model: Optional[str] = None,
    client: Optional[Any] = None,
    max_tokens: int = 8192,
    max_retries: int = 3,
) -> str:
    """Plain text completion — returns the assistant's text response."""
    resolved_model = model or model_for(tier)
    if client is None:
        client = get_client()

    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=resolved_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(
                getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
            )
        except Exception as exc:
            if not _is_retryable(exc) or attempt == max_retries - 1:
                raise
            time.sleep(1.0 * (2 ** attempt))
    return ""
