"""Generate the public sample run-ledger fixture and the golden report.

Deterministic: no randomness, no timestamps beyond fixed strings. The ledger is
hand-designed so that every analysis in ``analysis.py`` fires at least once:

  * failure cluster       : fifo_underflow fails on 3 configs (same property/RC)
  * timeout cluster        : cfg-bmc-shallow times out on 3 benchmarks
  * duplicate jobs         : counter+cfg-kind run twice with the SAME seed (exact)
  * runtime regression     : arbiter+cfg-pdr baseline ~10s, latest ~60s
  * memory regression      : arbiter+cfg-pdr latest peak memory ~5x baseline
  * config sensitivity     : fifo_overflow solved by some configs, timed out by another
  * reproducibility warning: handshake+cfg-kind flips PASS/FAIL across seeds

The run-record shape mirrors formal-run-orchestrator's RunRecord contract.

Usage:  python scripts/make_fixtures.py
Writes: examples/sample_ledger.jsonl and examples/golden_report.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

MACHINE = {
    "hostname": "ci-runner-01",
    "platform": "linux-x86_64",
    "python_version": "3.13.0",
    "cpu_count": 8,
}
CATALOG_VERSION = "cat-v1"
TOOL = "mock-formal-backend"
TOOL_VERSION = "0.1.0-mock"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


DESIGN_SHA = {
    "counter": sha("design:counter"),
    "arbiter": sha("design:arbiter"),
    "fifo_overflow": sha("design:fifo_overflow"),
    "fifo_underflow": sha("design:fifo_underflow"),
    "handshake": sha("design:handshake"),
}
PROP_SHA = {
    "counter": sha("prop:counter_wrap"),
    "arbiter": sha("prop:arbiter_onehot"),
    "fifo_overflow": sha("prop:no_overflow"),
    "fifo_underflow": sha("prop:no_underflow"),
    "handshake": sha("prop:req_grant"),
}

_counter = 0


def rec(
    *,
    benchmark: str,
    config_id: str,
    seed: int,
    status: str,
    wall: float,
    mem: float,
    return_code: int,
    minute: int,
) -> dict:
    global _counter
    _counter += 1
    rid = f"run-{_counter:03d}"
    dsha = DESIGN_SHA[benchmark]
    psha = PROP_SHA[benchmark]
    input_hash = sha(f"{dsha}|{psha}|{config_id}|{CATALOG_VERSION}")
    start = f"2026-09-01T10:{minute:02d}:00+00:00"
    end = f"2026-09-01T10:{minute:02d}:{min(int(wall), 59):02d}+00:00"
    return {
        "schema_version": "0.1.0",
        "run_id": rid,
        "plan_id": "plan-001",
        "benchmark_id": benchmark,
        "design_sha": dsha,
        "property_sha": psha,
        "input_hash": input_hash,
        "tool_name": TOOL,
        "tool_version": TOOL_VERSION,
        "config_id": config_id,
        "catalog_version": CATALOG_VERSION,
        "seed": seed,
        "start_time": start,
        "end_time": end,
        "cpu_time_s": round(wall * 1.1, 3),
        "wall_time_s": wall,
        "peak_memory_mb": mem,
        "return_code": return_code,
        "status": status,
    }


def build() -> list[dict]:
    r: list[dict] = []
    m = 0

    def nxt() -> int:
        nonlocal m
        m += 1
        return m

    # --- counter: stable PASS baseline + an EXACT duplicate (same seed) ---------
    for seed in (1, 2, 3):
        r.append(rec(benchmark="counter", config_id="cfg-kind", seed=seed,
                     status="PASS", wall=8.0 + seed * 0.1, mem=300.0, return_code=0, minute=nxt()))
    # exact duplicate: seed 1 re-run identically -> duplicate_jobs (exact)
    r.append(rec(benchmark="counter", config_id="cfg-kind", seed=1,
                 status="PASS", wall=8.1, mem=300.0, return_code=0, minute=nxt()))

    # --- arbiter/cfg-pdr: stable baseline then runtime + memory regression ------
    for seed in (1, 2, 3, 4):
        r.append(rec(benchmark="arbiter", config_id="cfg-pdr", seed=seed,
                     status="PASS", wall=10.0 + seed * 0.2, mem=400.0 + seed, return_code=0,
                     minute=nxt()))
    # latest run: 6x runtime AND ~5x memory -> both regression alerts
    r.append(rec(benchmark="arbiter", config_id="cfg-pdr", seed=5,
                 status="PASS", wall=62.0, mem=2100.0, return_code=0, minute=nxt()))

    # --- fifo_underflow: FAIL on 3 configs, same property + return_code ----------
    for cfg in ("cfg-kind", "cfg-pdr", "cfg-bmc-deep"):
        r.append(rec(benchmark="fifo_underflow", config_id=cfg, seed=1,
                     status="FAIL", wall=12.0, mem=350.0, return_code=1, minute=nxt()))

    # --- cfg-bmc-shallow: TIMEOUT on 3 different benchmarks ----------------------
    for bench in ("arbiter", "fifo_overflow", "handshake"):
        r.append(rec(benchmark=bench, config_id="cfg-bmc-shallow", seed=1,
                     status="TIMEOUT", wall=120.0, mem=500.0, return_code=124, minute=nxt()))

    # --- fifo_overflow: config-sensitive (solved by some, timed out by another) --
    r.append(rec(benchmark="fifo_overflow", config_id="cfg-pdr", seed=1,
                 status="PASS", wall=15.0, mem=380.0, return_code=0, minute=nxt()))
    r.append(rec(benchmark="fifo_overflow", config_id="cfg-kind", seed=1,
                 status="PASS", wall=18.0, mem=390.0, return_code=0, minute=nxt()))
    # (cfg-bmc-shallow TIMEOUT for fifo_overflow already added above)

    # --- handshake/cfg-kind: FLAKY -> PASS/FAIL across seeds --------------------
    r.append(rec(benchmark="handshake", config_id="cfg-kind", seed=1,
                 status="PASS", wall=9.0, mem=310.0, return_code=0, minute=nxt()))
    r.append(rec(benchmark="handshake", config_id="cfg-kind", seed=2,
                 status="FAIL", wall=9.5, mem=312.0, return_code=1, minute=nxt()))
    r.append(rec(benchmark="handshake", config_id="cfg-kind", seed=3,
                 status="PASS", wall=9.2, mem=311.0, return_code=0, minute=nxt()))

    return r


def main() -> None:
    records = build()
    EXAMPLES.mkdir(exist_ok=True)
    ledger_path = EXAMPLES / "sample_ledger.jsonl"
    ledger_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    # Import here so the script also works pre-install via PYTHONPATH.
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from formal_regression_intelligence.analysis import Thresholds, analyze
    from formal_regression_intelligence.models import RunRecord

    runs = [RunRecord.model_validate(x) for x in records]
    report = analyze(runs, Thresholds())
    golden_path = EXAMPLES / "golden_report.json"
    golden_path.write_text(report.model_dump_json(indent=2) + "\n")

    print(f"wrote {ledger_path} ({len(records)} records)")
    print(f"wrote {golden_path} ({len(report.findings)} findings)")
    for f in report.findings:
        print(f"  {f.kind.value:<24} {f.severity.value:<6} {f.finding_id}")


if __name__ == "__main__":
    main()
