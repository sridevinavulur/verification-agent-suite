"""Shared context object passed to every deterministic check."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..models import ParsedProperty, RtlIntentManifest


class CheckContext(BaseModel):
    """Everything a check may read. Checks must not mutate this object."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    prop: ParsedProperty
    manifest: RtlIntentManifest | None = None
    requirement_ids: set[str] = set()
    # Requirement IDs that the SVA file claims to cover, keyed by property name.
    traced: dict[str, str] = {}
