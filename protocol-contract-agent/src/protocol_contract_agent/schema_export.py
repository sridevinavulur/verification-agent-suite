"""Export JSON Schema for the public Pydantic contracts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ContractRequest, ProtocolContract, RtlManifest

_SCHEMAS = {
    "protocol_contract.schema.json": ProtocolContract,
    "contract_request.schema.json": ContractRequest,
    "rtl_manifest_view.schema.json": RtlManifest,
}


def export_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fname, model in _SCHEMAS.items():
        path = out_dir / fname
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written
