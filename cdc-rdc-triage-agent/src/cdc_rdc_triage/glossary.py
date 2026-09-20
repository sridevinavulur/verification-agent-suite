"""Optional synchronizer-cell glossary.

A glossary lets a team declare which module names are known synchronizer cells
(e.g. a standard-cell ``SYNC_2FF`` macro) so that instances of them count as
structural synchronizer evidence.  This is *declarative human input*, not
inference -- the tool trusts the glossary as an assertion by the user.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SyncCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str
    depth: int = Field(default=2, ge=1)
    data_in_port: str | None = None
    data_out_port: str | None = None
    description: str = ""


class Glossary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cells: list[SyncCell] = Field(default_factory=list)

    def cell_for_module(self, module: str) -> SyncCell | None:
        for c in self.cells:
            if c.module == module:
                return c
        return None

    @classmethod
    def empty(cls) -> Glossary:
        return cls(cells=[])

    @classmethod
    def load(cls, path: Path) -> Glossary:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)
