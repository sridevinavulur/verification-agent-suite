"""Verification Plan Agent - deterministic verification-plan draft generator.

Consumes a structured spec, an interface glossary and an RTL Intent Manifest,
and produces a reviewable verification-plan draft with traceability and an
explicit human-approval workflow. Mock LLM only; no network calls.
"""

from __future__ import annotations

__version__ = "0.1.0"
