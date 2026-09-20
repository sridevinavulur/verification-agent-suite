"""veri-forge CLI entry point.

Usage:
  veri-forge run --spec path/to/spec.md --top my_dut [options]
  veri-forge run --spec spec.md --rtl-dir rtl/ --top dut --sim verilator
  veri-forge run --spec spec.yaml --top dut --skip 3,6,7 --max-iter 3
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_run(args: argparse.Namespace) -> int:
    from .models import RunConfig
    from .orchestrator import VeriForgeOrchestrator

    skip = []
    if args.skip:
        skip = [int(s.strip()) for s in args.skip.split(",") if s.strip()]

    config = RunConfig(
        spec_path=Path(args.spec),
        rtl_dir=Path(args.rtl_dir) if args.rtl_dir else None,
        top=args.top or "",
        out_dir=Path(args.out_dir),
        simulator=args.sim,
        target_line_pct=args.target_line,
        target_toggle_pct=args.target_toggle,
        target_branch_pct=args.target_branch,
        target_coverage=args.target_overall,
        max_iter=args.max_iter,
        skip_stages=skip,
    )

    # Resolve RTL files from rtl_dir
    rtl_files = []
    if config.rtl_dir and config.rtl_dir.exists():
        for ext in ("*.v", "*.sv", "*.vhd"):
            rtl_files.extend(str(f) for f in config.rtl_dir.rglob(ext))

    _configure_logging(args.verbose)
    logger = logging.getLogger("veri-forge")
    logger.info("Starting veri-forge run")
    logger.info("  Spec: %s", args.spec)
    logger.info("  Top:  %s", args.top or "(auto-detect)")
    logger.info("  Sim:  %s", args.sim)

    orch = VeriForgeOrchestrator(config)

    # Pre-populate RTL files if found
    try:
        from .llm.client import get_client
        client = get_client()
    except Exception:
        client = None

    ctx = orch.run(llm_client=client)

    # Inject pre-discovered RTL files
    if rtl_files and not ctx.rtl_files:
        ctx.rtl_files = rtl_files

    # Print summary
    summary_file = ctx.run_dir / "run_summary.json"
    if summary_file.exists():
        summary = json.loads(summary_file.read_text())
        print("\n" + "=" * 60)
        print(f"  veri-forge run complete: {ctx.run_dir}")
        print(f"  Tests: {summary['tests']['passed']}/{summary['tests']['passed']+summary['tests']['failed']} passed")
        cov = summary.get("coverage", {})
        print(f"  Coverage: line={cov.get('line_pct',0):.1f}%  toggle={cov.get('toggle_pct',0):.1f}%  branch={cov.get('branch_pct',0):.1f}%")
        print(f"  Bugs: {summary.get('bugs_total',0)} total, closure={cov.get('closure','n/a')}")
        print(f"  Dashboard: {ctx.run_dir}/dashboard.html")
        print("=" * 60 + "\n")

    # Return non-zero if any stage failed
    failed_stages = [r for r in ctx.stage_results if r.status == "fail"]
    return 1 if failed_stages else 0


def cmd_info(args: argparse.Namespace) -> int:
    """Print information about available stages and tools."""
    print("veri-forge — Agentic Hardware Verification Pipeline")
    print()
    print("16-Stage Pipeline:")
    stages = [
        (1,  "spec_parser",       "Parse design specification (YAML/Markdown/PDF)"),
        (2,  "rtl_designer",      "Generate RTL skeleton from spec (if no RTL provided)"),
        (3,  "lint_runner",       "Verilator lint check"),
        (4,  "rtl_reviewer",      "LLM structural code review"),
        (5,  "property_gen",      "Generate SVA properties from spec"),
        (6,  "formal",            "Run JasperGold / SymbiYosys formal verification"),
        (7,  "lec",               "Logic Equivalence Check (LEC)"),
        (8,  "testplan_gen",      "Generate test plan from parsed spec"),
        (9,  "ref_model_gen",     "Generate Python golden reference model"),
        (10, "uvm_vip_gen",       "Generate UVM VIP stubs"),
        (11, "cocotb_vip_gen",    "Generate cocotb BFMs for all interfaces"),
        (12, "test_gen",          "Generate cocotb test file from test plan"),
        (13, "simulation",        "Run Verilator / VCS / Xcelium simulation"),
        (14, "fsdb_analyzer",     "Analyze simulation logs and waveforms"),
        (15, "debug_analyzer",    "CRAVS multi-agent root-cause analysis"),
        (16, "coverage_closure",  "Parse coverage, classify unreachable, iterate"),
    ]
    for n, name, desc in stages:
        print(f"  {n:2d}. {name:<22} {desc}")
    print()
    print("Coverage closure loop: stages 12 → 16, repeated until goals met or max_iter reached")
    print("CRAVS integration: set CRAVS_PATH to cravs_core.py directory, or install cravs package")
    print()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="veri-forge",
        description="Agentic hardware verification pipeline — spec to coverage closure",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the full DV pipeline")
    run_p.add_argument("--spec",           required=True, help="Design spec file (.md/.yaml/.txt/.pdf)")
    run_p.add_argument("--top",            default="",    help="DUT top module name")
    run_p.add_argument("--rtl-dir",        default=None,  help="Directory containing RTL source files")
    run_p.add_argument("--out-dir",        default="vf_out", help="Output directory (default: vf_out)")
    run_p.add_argument("--sim",            default="verilator", choices=["verilator","vcs","xcelium"],
                       help="Simulator backend (default: verilator)")
    run_p.add_argument("--target-line",    type=float, default=90.0, help="Line coverage target %%")
    run_p.add_argument("--target-toggle",  type=float, default=80.0, help="Toggle coverage target %%")
    run_p.add_argument("--target-branch",  type=float, default=85.0, help="Branch coverage target %%")
    run_p.add_argument("--target-overall", type=float, default=90.0, help="Overall coverage target for closure loop")
    run_p.add_argument("--max-iter",       type=int,   default=5,    help="Max coverage closure iterations")
    run_p.add_argument("--skip",           default="", help="Comma-separated stage numbers to skip (e.g. 6,7,10)")
    run_p.add_argument("--verbose",        action="store_true", help="Verbose logging")

    info_p = sub.add_parser("info", help="Show pipeline stage info")
    info_p.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    if args.command == "run":
        sys.exit(cmd_run(args))
    elif args.command == "info":
        sys.exit(cmd_info(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
