"""Parser adapter interface + registry.

The frontend is pluggable so that a Slang / tree-sitter / Surelog-UHDM backend
can be slotted in later without changing downstream code. v0.1 ships exactly one
working adapter: the built-in constrained-Verilog parser.
"""

from __future__ import annotations

from .base import ParserAdapter, ParseResult
from .builtin import BuiltinVerilogAdapter

_REGISTRY: dict[str, type[ParserAdapter]] = {
    "builtin": BuiltinVerilogAdapter,
}


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


def get_adapter(name: str) -> ParserAdapter:
    """Instantiate a registered adapter by name.

    Raises ``KeyError`` (surfaced by the CLI as a clean error) if unknown.
    """
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:  # pragma: no cover - trivial
        raise KeyError(
            f"unknown parser adapter {name!r}; available: {available_adapters()}"
        ) from exc
    return cls()


__all__ = [
    "ParserAdapter",
    "ParseResult",
    "BuiltinVerilogAdapter",
    "available_adapters",
    "get_adapter",
]
