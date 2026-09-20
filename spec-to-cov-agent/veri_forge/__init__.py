"""veri-forge — Agentic hardware verification pipeline.

Runs a 16-stage DV pipeline from design spec to full coverage closure:
  Spec → RTL → Lint → Review → Properties → Formal → LEC
       → Testplan → RefModel → UVM VIP → cocotb VIP
       → Tests → Simulation → FSDB → CRAVS Debug → Coverage Closure

Quick start:
  from veri_forge.models import RunConfig
  from veri_forge.orchestrator import VeriForgeOrchestrator

  config = RunConfig(spec_path="spec.md", top="my_dut", out_dir="vf_out")
  ctx = VeriForgeOrchestrator(config).run()

Or from the CLI:
  veri-forge run --spec spec.md --top my_dut --sim verilator
"""

__version__ = "0.1.0"
