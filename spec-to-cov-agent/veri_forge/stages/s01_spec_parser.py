"""Stage 1 — Spec Parser.

Reads any hardware spec (YAML, JSON, Markdown, plain text) and extracts:
- Protocol name/version, interface signals, transactions, registers.
Uses LLM for unstructured inputs (markdown/text).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from ..models import RunContext, StageResult

logger = logging.getLogger(__name__)

_SYSTEM = """You are a hardware specification parser. Extract structured information from the
provided hardware IP specification. Return JSON with fields:
- protocol: {name, version}
- interfaces: [{name, role, signals: [{name, direction, width, description}], clocks, resets}]
- transactions: [{name, description, initiator, target, data_fields}]
- registers: [{name, offset, width, access, reset_value, description}]
- timing: {clock_freq_mhz, setup_cycles, hold_cycles}
- fsms: [{name, states: [{name, transitions: [{condition, next_state}]}]}]
- constraints: [string]
Output ONLY valid JSON."""


class SpecParser:
    def run(self, ctx: RunContext) -> StageResult:
        stage_dir = ctx.stage_dir(1, "spec_parser")
        spec_path = Path(ctx.config.spec_path)

        if not spec_path.exists():
            return StageResult(stage=1, name="spec_parser", status="fail",
                               summary=f"Spec file not found: {spec_path}")

        suffix = spec_path.suffix.lower()
        spec_text = spec_path.read_text(errors="replace")

        parsed: Dict[str, Any] = {}

        if suffix in (".yaml", ".yml"):
            import yaml
            try:
                parsed = yaml.safe_load(spec_text) or {}
            except Exception as e:
                parsed = {"raw_text": spec_text, "parse_error": str(e)}
        elif suffix == ".json":
            try:
                parsed = json.loads(spec_text)
            except Exception as e:
                parsed = {"raw_text": spec_text, "parse_error": str(e)}
        else:
            parsed = self._parse_with_llm(spec_text)

        parsed.setdefault("_source", str(spec_path))
        parsed.setdefault("_raw_text", spec_text[:8000])

        ctx.parsed_spec = parsed
        out_file = stage_dir / "parsed_spec.json"
        out_file.write_text(json.dumps(parsed, indent=2, default=str))

        n_interfaces = len(parsed.get("interfaces", []))
        n_registers = len(parsed.get("registers", []))
        n_transactions = len(parsed.get("transactions", []))

        return StageResult(
            stage=1, name="spec_parser", status="pass",
            summary=(f"Parsed spec: {n_interfaces} interface(s), "
                     f"{n_registers} register(s), {n_transactions} transaction(s)"),
            artifacts={"parsed_spec": str(out_file)},
            data={"n_interfaces": n_interfaces, "n_registers": n_registers},
        )

    def _parse_with_llm(self, text: str) -> Dict[str, Any]:
        from ..llm.client import simple_call
        try:
            raw = simple_call(system=_SYSTEM, user=text[:12000], tier="gen", max_tokens=4096)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            logger.warning("LLM spec parse failed: %s", e)
        return {"raw_text": text[:2000]}
