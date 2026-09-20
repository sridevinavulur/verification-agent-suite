"""Finite, versioned configuration catalog.

The catalog is the *only* source of executable configurations. Both the
deterministic planner and every policy select IDs from here; nothing outside the
catalog can be planned or run. Bumping ``CATALOG_VERSION`` is how the team evolves
the approved set while keeping old run records reproducible/attributable.
"""

from __future__ import annotations

from .models import (
    EngineFamily,
    PartitionStrategy,
    PreprocessingLevel,
    SolverConfig,
)

CATALOG_VERSION = "2026.09.1"


def _c(
    config_id: str,
    engine: EngineFamily,
    bmc_depth: int,
    timeout_s: int,
    memory_cap_mb: int,
    preprocessing: PreprocessingLevel,
    partition: PartitionStrategy,
) -> SolverConfig:
    return SolverConfig(
        config_id=config_id,
        catalog_version=CATALOG_VERSION,
        engine=engine,
        bmc_depth=bmc_depth,
        timeout_s=timeout_s,
        memory_cap_mb=memory_cap_mb,
        preprocessing=preprocessing,
        partition_strategy=partition,
    )


# Fixed engine catalog x fixed BMC depths x fixed timeout tiers x fixed
# preprocessing choices. Kept small and human-auditable on purpose.
_CONFIGS: list[SolverConfig] = [
    # --- BMC tiers (shallow -> deep) ---
    _c("bmc_shallow", EngineFamily.BMC, 20, 30, 2048,
       PreprocessingLevel.LIGHT, PartitionStrategy.MONOLITHIC),
    _c("bmc_mid", EngineFamily.BMC, 60, 120, 4096,
       PreprocessingLevel.LIGHT, PartitionStrategy.COI_SLICE),
    _c("bmc_deep", EngineFamily.BMC, 150, 600, 8192,
       PreprocessingLevel.AGGRESSIVE, PartitionStrategy.COI_SLICE),
    # --- k-induction (good for invariants that hold) ---
    _c("kind_mid", EngineFamily.KINDUCTION, 40, 120, 4096,
       PreprocessingLevel.LIGHT, PartitionStrategy.COI_SLICE),
    _c("kind_deep", EngineFamily.KINDUCTION, 120, 600, 8192,
       PreprocessingLevel.AGGRESSIVE, PartitionStrategy.HIERARCHY),
    # --- PDR/IC3-style (unbounded, memory-hungry) ---
    _c("pdr_std", EngineFamily.PDR, 1, 600, 8192,
       PreprocessingLevel.AGGRESSIVE, PartitionStrategy.COI_SLICE),
    _c("pdr_big", EngineFamily.PDR, 1, 1800, 16384,
       PreprocessingLevel.AGGRESSIVE, PartitionStrategy.HIERARCHY),
    # --- interpolation (fast when it works, brittle otherwise) ---
    _c("interp_std", EngineFamily.INTERPOLATION, 80, 300, 8192,
       PreprocessingLevel.LIGHT, PartitionStrategy.COI_SLICE),
]

_BY_ID: dict[str, SolverConfig] = {c.config_id: c for c in _CONFIGS}


def all_configs() -> list[SolverConfig]:
    """Return the catalog in a stable, deterministic order."""
    return list(_CONFIGS)


def config_ids() -> list[str]:
    return [c.config_id for c in _CONFIGS]


def get_config(config_id: str) -> SolverConfig:
    try:
        return _BY_ID[config_id]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(
            f"config_id '{config_id}' is not in catalog {CATALOG_VERSION}"
        ) from exc


def is_valid_config(config_id: str) -> bool:
    return config_id in _BY_ID
