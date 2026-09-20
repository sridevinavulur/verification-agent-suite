# spec-to-cov-agent

> Formerly `veri-forge`. End-to-end reference pipeline kept alongside the bounded
> single-purpose tools in this workspace. Its deterministic building blocks (Verilator/cocotb
> coverage parsing, sim runner, HTML dashboard, waveform/CRAVS debug) are reused by those
> tools; its LLM-generates-RTL and auto-closure-loop stages are intentionally *not* adopted
> there, per the pack's deterministic-first, human-gated discipline.

Agentic hardware verification pipeline. Give it a design spec; it runs 16 stages to reach coverage closure.

```
Spec → RTL → Lint → Review → Properties → Formal → LEC
     → Testplan → RefModel → UVM VIP → cocotb VIP
     → Tests → Simulation → FSDB Analysis → CRAVS Debug → Coverage Closure
```

Coverage closure loop repeats stages 12–16 until your line/toggle/branch targets are met.

---

## Quick Start

```bash
pip install -e ".[dev]"

# Run on any design spec
veri-forge run --spec path/to/your_design.md --top your_dut_name

# With existing RTL
veri-forge run --spec spec.md --top dut --rtl-dir rtl/ --sim verilator

# Skip stages you don't need (e.g. formal=6, LEC=7, UVM=10)
veri-forge run --spec spec.md --top dut --skip 6,7,10 --max-iter 3
```

**Output** (in `vf_out/run_<timestamp>/`):

```
vf_out/run_1700000000/
├── dashboard.html          # HTML report with coverage, bugs, unreachability
├── run_summary.json        # Machine-readable summary
├── s01_spec_parser/        # Parsed spec JSON
├── s08_testplan/           # Generated test plan
├── s11_cocotb_vip/         # Generated BFMs
├── s12_test_gen/           # Generated cocotb tests
├── s13_simulation/         # Sim logs + coverage.dat
├── s15_debug_analyzer/     # CRAVS bug reports
├── s16_coverage_closure/   # Coverage metrics + unreachability analysis
└── ...
```

---

## Requirements

| Tool | Required | Notes |
|------|----------|-------|
| Python ≥ 3.10 | Yes | |
| `pip install ".[llm]"` (or your LLM provider SDK) + `pydantic` | Yes (for LLM stages) | LLM + schema validation |
| `pip install cocotb` | Yes | Simulation BFM framework |
| Verilator ≥ 5.x | Yes (default sim) | `apt install verilator` |
| VCS or Xcelium | Optional | Set `VCS_HOME` or `XCELIUM_HOME` |
| JasperGold | Optional | Set `JASPER_HOME` for formal |
| SymbiYosys | Optional | `pip install sby` for open formal |
| CRAVS | Optional | Set `CRAVS_PATH` for enhanced debug |

```bash
# LLM stages are provider-neutral. Point LLM_PROVIDER at an installed provider
# SDK module and supply credentials via generic env vars:
export LLM_PROVIDER="your_provider_sdk_module"   # e.g. the module name of your LLM SDK
export LLM_API_KEY="..."
export LLM_BASE_URL="https://your-gateway"       # optional proxy/gateway
export LLM_MODEL_REVIEW="review-model"           # optional model override
export LLM_MODEL_GEN="gen-model"                 # optional model override
export CRAVS_PATH="/path/to/cravs"               # optional external debug engine
export JASPER_HOME="/path/to/jaspergold"         # optional
```

---

## Coverage Closure Loop

The pipeline iterates stages 12–16 until coverage goals are met:

```
Iteration 0:  Tests → Sim → FSDB → CRAVS → Coverage Analysis → [89.2% line, 76.1% toggle]
Iteration 1:  Targeted Tests → Sim → FSDB → CRAVS → Coverage Analysis → [91.4% line, 80.7% toggle]
Iteration 2:  ✓ GOALS MET
```

**Unreachability analysis** classifies uncovered toggle transitions so you know which ones are genuinely coverable vs. architecturally impossible:

| Category | Example |
|----------|---------|
| `hardwired_constant` | `PREADY` always tied to 1 |
| `dead_code` | `tx_frame[95:48]` declared 96b, only 48b used |
| `counter_ceiling` | `to_cnt` never reaches `TIMEOUT_MAX=1023` |
| `architectural_limit` | `clksel=1` mode not exercised |
| `spec_gap` | Behavior undefined when `ack≥4` |

Unreachable transitions are excluded from the effective coverage ceiling and surfaced in the dashboard.

---

## CRAVS Integration

CRAVS is an optional external multi-agent root-cause analysis engine for simulation failures:

```
cravs.LOG_ANALYZER      → parse failure events
cravs.PROTOCOL_EXPERT   → identify protocol violations
cravs.TIMING_ANALYZER   → find timing-related root causes
cravs.WAVEFORM_ANALYZER → correlate waveform evidence
cravs.FSDB_CORRELATOR   → FSDB signal tracing
```

Set `CRAVS_PATH` to the directory containing `cravs_core.py`. Falls back to LLM-only analysis if CRAVS is unavailable.

---

## Python API

```python
from veri_forge.models import RunConfig
from veri_forge.orchestrator import VeriForgeOrchestrator

config = RunConfig(
    spec_path="my_design_spec.md",
    top="my_dut",
    rtl_dir="rtl/",
    simulator="verilator",
    target_line_pct=90.0,
    target_toggle_pct=80.0,
    target_branch_pct=85.0,
    max_iter=5,
    skip_stages=[7, 10],   # skip LEC, UVM VIP
)

ctx = VeriForgeOrchestrator(config).run()

print(f"Dashboard: {ctx.run_dir}/dashboard.html")
print(f"Bugs found: {len(ctx.bugs)}")
print(f"Final coverage history: {ctx.coverage_history[-1]}")
```

---

## Stage Reference

| # | Name | Description |
|---|------|-------------|
| 1 | `spec_parser` | Parse design spec (YAML/Markdown/text/PDF) |
| 2 | `rtl_designer` | Generate RTL skeleton or discover existing files |
| 3 | `lint_runner` | Verilator `--lint-only` |
| 4 | `rtl_reviewer` | LLM structural code review |
| 5 | `property_gen` | Generate SVA properties |
| 6 | `formal` | JasperGold / SymbiYosys formal verification |
| 7 | `lec` | Logic Equivalence Check (Formality) |
| 8 | `testplan_gen` | Generate test plan from parsed spec |
| 9 | `ref_model_gen` | Generate Python golden reference model |
| 10 | `uvm_vip_gen` | Generate UVM VIP (requires VCS/Xcelium) |
| 11 | `cocotb_vip_gen` | Generate cocotb BFMs for all interfaces |
| 12 | `test_gen` | Generate / update cocotb test file |
| 13 | `simulation` | Run Verilator / VCS / Xcelium + collect coverage |
| 14 | `fsdb_analyzer` | Analyze logs and waveforms |
| 15 | `debug_analyzer` | **CRAVS** multi-agent root-cause analysis |
| 16 | `coverage_closure` | Parse coverage, classify unreachable, decide iterate/done |

---

## Reusing this package

This package is self-contained with no Docker/PostgreSQL/Redis dependencies.
Copy the `veri_forge/` directory and `pyproject.toml` into a target repo and install.
