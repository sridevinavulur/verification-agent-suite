"""Export JSON Schema for the public Pydantic contracts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import RegisterMap, RtlSymbolTable, VerificationPackage

_EXPORTS = {
    "register_map.schema.json": RegisterMap,
    "rtl_symbols.schema.json": RtlSymbolTable,
    "verification_package.schema.json": VerificationPackage,
}


def export_all(out_dir: str | Path) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fname, model in _EXPORTS.items():
        p = out_dir / fname
        p.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        written.append(p)
    return written
