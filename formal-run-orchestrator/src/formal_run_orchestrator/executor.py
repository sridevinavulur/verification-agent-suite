"""Mocked execution worker.

Produces deterministic pseudo-runs: no real formal tool is invoked. Given a
(benchmark, config, seed) triple the mock is a pure function -- same inputs yield
the same RawResult -- so the whole pipeline is reproducible in CI.

The mock's "physics" is a transparent, documented model, NOT a claim about any real
solver. It exists so the ledger/classifier/summarize/compare paths can be exercised
end-to-end and so policies can be compared offline.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from .catalog import get_config, is_valid_config
from .classifier import RawResult, classify
from .ledger import machine_metadata
from .models import (
    BenchmarkItem,
    EngineFamily,
    PartitionStrategy,
    PreprocessingLevel,
    RunRecord,
    RunStatus,
    SolverConfig,
    ValidationStatus,
)

TOOL_NAME = "mock-formal-backend"
TOOL_VERSION = "0.1.0-mock"


def _seeded_unit(*parts: str) -> float:
    """Deterministic pseudo-random value in [0, 1) from string parts (no global RNG)."""
    h = hashlib.sha256("::".join(parts).encode()).hexdigest()
    return int(h[:16], 16) / float(1 << 64)


def _effective_depth(cfg: SolverConfig) -> int:
    """Unbounded engines behave as if they can reach large depths."""
    if cfg.engine in (EngineFamily.PDR, EngineFamily.INTERPOLATION):
        return max(cfg.bmc_depth, 10_000)
    return cfg.bmc_depth


def _preprocess_speedup(level: PreprocessingLevel) -> float:
    return {
        PreprocessingLevel.NONE: 1.0,
        PreprocessingLevel.LIGHT: 0.85,
        PreprocessingLevel.AGGRESSIVE: 0.65,
    }[level]


def _partition_speedup(strategy: PartitionStrategy) -> float:
    return {
        PartitionStrategy.MONOLITHIC: 1.0,
        PartitionStrategy.COI_SLICE: 0.7,
        PartitionStrategy.HIERARCHY: 0.55,
    }[strategy]


def simulate(item: BenchmarkItem, cfg: SolverConfig, seed: int) -> RawResult:
    """Deterministic mock of a formal run. Pure function of (item, cfg, seed).

    Model summary (documented, not a real solver):
      * A "cost" grows with intrinsic difficulty, COI size, and depth-to-resolve,
        and shrinks with preprocessing/partitioning and deeper BMC bounds.
      * If cost fits in the timeout budget, the tool concludes: it returns the toy
        ground-truth verdict (holds -> PASS-able, else counterexample -> FAIL).
      * If cost exceeds the budget, no conclusion is reached -> TIMEOUT.
      * A small, seed-stable fraction of runs inject a tool ERROR (e.g. mem cap hit).
    """
    salt = f"{item.benchmark_id}|{cfg.config_id}|{seed}"

    depth = _effective_depth(cfg)
    depth_ok = depth >= item.max_depth_hint

    # Base cost in seconds. Deterministic; scaled by difficulty and structure.
    base = (
        5.0
        + 400.0 * item.intrinsic_difficulty
        + 0.20 * item.coi_size
        + 0.05 * item.register_count
    )
    # Engines that must reach the resolving depth pay if the bound is too shallow.
    if not depth_ok:
        base *= 3.0

    # Engine affinity: k-induction/PDR are better at *holding* properties;
    # BMC is better at *finding shallow counterexamples*.
    if item.is_holds and cfg.engine in (EngineFamily.KINDUCTION, EngineFamily.PDR):
        base *= 0.6
    if (not item.is_holds) and cfg.engine is EngineFamily.BMC and depth_ok:
        base *= 0.5

    speedup = _preprocess_speedup(cfg.preprocessing) * _partition_speedup(cfg.partition_strategy)
    # +-25% deterministic jitter from the seed.
    jitter = 0.75 + 0.5 * _seeded_unit(salt, "jitter")
    cost = base * speedup * jitter

    # Memory model: grows with COI and depth; aggressive preprocessing costs memory.
    mem = (
        128.0
        + 0.9 * item.coi_size
        + 1.5 * depth
        + (256.0 if cfg.preprocessing is PreprocessingLevel.AGGRESSIVE else 0.0)
    )

    # Rare deterministic tool error (e.g. exceeded memory cap or backend crash).
    mem_overflow = mem > cfg.memory_cap_mb
    err_roll = _seeded_unit(salt, "err")
    tool_error = mem_overflow or err_roll < 0.03

    if tool_error:
        # Errors still consume some wall time but reach no conclusion.
        wall = min(cost * 0.3, float(cfg.timeout_s))
        return RawResult(
            return_code=1,
            wall_time_s=round(wall, 3),
            timeout_s=float(cfg.timeout_s),
            reached_conclusion=False,
            conclusion_holds=None,
            tool_reported_error=True,
        )

    if cost <= cfg.timeout_s and depth_ok:
        # Concluded within budget with an adequate bound.
        wall = round(cost, 3)
        return RawResult(
            return_code=0,
            wall_time_s=wall,
            timeout_s=float(cfg.timeout_s),
            reached_conclusion=True,
            conclusion_holds=item.is_holds,
            tool_reported_error=False,
        )

    if cost <= cfg.timeout_s and not depth_ok:
        # BMC exhausted its (too shallow) bound without a conclusion: INCONCLUSIVE,
        # not a pass. (A bounded proof to depth N says nothing beyond N.)
        wall = round(cost, 3)
        return RawResult(
            return_code=0,
            wall_time_s=wall,
            timeout_s=float(cfg.timeout_s),
            reached_conclusion=False,
            conclusion_holds=None,
            tool_reported_error=False,
        )

    # Ran out of time budget.
    return RawResult(
        return_code=124,  # conventional timeout return code
        wall_time_s=float(cfg.timeout_s),
        timeout_s=float(cfg.timeout_s),
        reached_conclusion=False,
        conclusion_holds=None,
        tool_reported_error=False,
    )


def _input_hash(item: BenchmarkItem, cfg: SolverConfig) -> str:
    payload = "|".join(
        [item.design_sha, item.property_sha, cfg.config_id, cfg.catalog_version]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def execute(
    item: BenchmarkItem,
    config_id: str,
    seed: int,
    *,
    plan_id: str,
    run_id: str,
    rationale: str,
    artifact_dir: str | None = None,
) -> RunRecord:
    """Run one mocked execution and build a fully-provenanced RunRecord.

    Validates the config against the catalog first; an unknown config yields an
    ERROR run with ``validation_status=INVALID_CONFIG`` rather than crashing, so
    invalid policy choices are recorded and penalized rather than hidden.
    """
    machine = machine_metadata()
    start = datetime.now(UTC)

    if not is_valid_config(config_id):
        end = start + timedelta(seconds=0.0)
        return RunRecord(
            run_id=run_id,
            plan_id=plan_id,
            benchmark_id=item.benchmark_id,
            design_sha=item.design_sha,
            property_sha=item.property_sha,
            input_hash=hashlib.sha256(f"invalid:{config_id}".encode()).hexdigest(),
            tool_name=TOOL_NAME,
            tool_version=TOOL_VERSION,
            config_id=config_id,
            catalog_version="unknown",
            command_line=f"<rejected: config '{config_id}' not in catalog>",
            seed=seed,
            machine=machine,
            start_time=start,
            end_time=end,
            cpu_time_s=0.0,
            wall_time_s=0.0,
            peak_memory_mb=0.0,
            return_code=2,
            status=RunStatus.ERROR,
            validation_status=ValidationStatus.INVALID_CONFIG,
            rationale=rationale,
            artifact_path=None,
            artifact_hash=None,
        )

    cfg = get_config(config_id)
    raw = simulate(item, cfg, seed)
    status = classify(raw)

    # CPU time modeled as slightly above wall (some parallel search overhead).
    cpu_time = round(raw.wall_time_s * (1.1 + 0.2 * _seeded_unit(item.benchmark_id, "cpu")), 3)
    mem = round(
        128.0 + 0.9 * item.coi_size + 1.5 * _effective_depth(cfg)
        + (256.0 if cfg.preprocessing is PreprocessingLevel.AGGRESSIVE else 0.0),
        1,
    )
    end = start + timedelta(seconds=raw.wall_time_s)

    artifact_path = None
    artifact_hash = None
    if artifact_dir is not None:
        # Deterministic mock artifact content (log stub) + content hash.
        content = (
            f"# mock formal log\nrun_id={run_id}\nstatus={status.value}\n"
            f"config={cfg.config_id}\nwall_s={raw.wall_time_s}\n"
        )
        from pathlib import Path

        p = Path(artifact_dir) / f"{run_id}.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        artifact_path = str(p)
        artifact_hash = hashlib.sha256(content.encode()).hexdigest()

    return RunRecord(
        run_id=run_id,
        plan_id=plan_id,
        benchmark_id=item.benchmark_id,
        design_sha=item.design_sha,
        property_sha=item.property_sha,
        input_hash=_input_hash(item, cfg),
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        config_id=cfg.config_id,
        catalog_version=cfg.catalog_version,
        command_line=cfg.command_line(item.design_name, item.property.property_id),
        seed=seed,
        machine=machine,
        start_time=start,
        end_time=end,
        cpu_time_s=cpu_time,
        wall_time_s=raw.wall_time_s,
        peak_memory_mb=mem,
        return_code=raw.return_code,
        status=status,
        validation_status=ValidationStatus.VALID,
        rationale=rationale,
        artifact_path=artifact_path,
        artifact_hash=artifact_hash,
    )
