"""Abstract parser-adapter contract.

An adapter turns raw RTL source text into a list of ``Module`` records plus a
list of ``UnresolvedConstruct`` records and a ``ParserInfo`` descriptor. It does
NOT compute cross-module hierarchy, clock/reset heuristics, or provenance -
those are assembled by :mod:`rtl_intent.manifest` so every adapter produces a
consistent manifest.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..models import Module, ParserInfo, UnresolvedConstruct


@dataclass
class ParseResult:
    """Per-file parse output from an adapter."""

    modules: list[Module] = field(default_factory=list)
    unresolved: list[UnresolvedConstruct] = field(default_factory=list)


class ParserAdapter(ABC):
    """Frontend interface. Later backends (Slang, tree-sitter) implement this."""

    name: str = "abstract"
    version: str = "0.0.0"

    @abstractmethod
    def parse_text(self, text: str, *, filename: str) -> ParseResult:
        """Parse a single source file's text."""
        raise NotImplementedError

    @abstractmethod
    def info(self) -> ParserInfo:
        """Describe what this adapter supports and does not support."""
        raise NotImplementedError
