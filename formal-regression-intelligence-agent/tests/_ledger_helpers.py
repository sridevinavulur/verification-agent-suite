"""Shared test helpers (importable as a top-level module by pytest)."""

from __future__ import annotations

import hashlib

from formal_regression_intelligence.models import RunRecord


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def make_record(
    *,
    run_id: str,
    benchmark: str = "bench",
    config_id: str = "cfg-a",
    seed: int = 1,
    status: str = "PASS",
    wall: float = 10.0,
    mem: float = 300.0,
    return_code: int | None = None,
    design_sha: str | None = None,
    property_sha: str | None = None,
    minute: int = 0,
) -> RunRecord:
    """Build a valid RunRecord with sensible provenance defaults for tests."""
    dsha = design_sha or _sha(f"d:{benchmark}")
    psha = property_sha or _sha(f"p:{benchmark}")
    rc = return_code if return_code is not None else (0 if status == "PASS" else 1)
    return RunRecord.model_validate(
        {
            "run_id": run_id,
            "plan_id": "plan-t",
            "benchmark_id": benchmark,
            "design_sha": dsha,
            "property_sha": psha,
            "input_hash": _sha(f"{dsha}|{psha}|{config_id}"),
            "tool_name": "mock-formal-backend",
            "tool_version": "0.1.0-mock",
            "config_id": config_id,
            "catalog_version": "cat-v1",
            "seed": seed,
            "start_time": f"2026-09-01T10:{minute:02d}:00+00:00",
            "end_time": f"2026-09-01T10:{minute:02d}:30+00:00",
            "cpu_time_s": round(wall * 1.1, 3),
            "wall_time_s": wall,
            "peak_memory_mb": mem,
            "return_code": rc,
            "status": status,
        }
    )
