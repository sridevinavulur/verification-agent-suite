"""Assertion Review Agent -- deterministic static review of SVA properties."""

from __future__ import annotations

from .models import Finding, ReviewReport, ReviewScore, RtlIntentManifest, Severity
from .parser import parse_sva
from .review import review_file, review_text
from .rtl_intent_adapter import from_rtl_intent_manifest, load_manifest

__version__ = "0.1.0"

__all__ = [
    "Finding",
    "ReviewReport",
    "ReviewScore",
    "RtlIntentManifest",
    "Severity",
    "from_rtl_intent_manifest",
    "load_manifest",
    "parse_sva",
    "review_file",
    "review_text",
    "__version__",
]
