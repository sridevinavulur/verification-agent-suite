"""Finite, versioned approved experiment-configuration catalog.

The supervisor may ONLY select a config from this catalog. It cannot invent
engines, depths, or timeouts. Selecting outside the catalog is a hard error.
"""

from __future__ import annotations

from .models import ExperimentConfig

CATALOG_VERSION = "catalog-v0.1"

APPROVED_CONFIGS: dict[str, ExperimentConfig] = {
    "CFG-BMC-SHALLOW": ExperimentConfig(
        config_id="CFG-BMC-SHALLOW", engine="bmc", bmc_depth=20,
        timeout_s=60, preprocessing="basic",
    ),
    "CFG-BMC-DEEP": ExperimentConfig(
        config_id="CFG-BMC-DEEP", engine="bmc", bmc_depth=100,
        timeout_s=300, preprocessing="basic",
    ),
    "CFG-IND-BASIC": ExperimentConfig(
        config_id="CFG-IND-BASIC", engine="induction", bmc_depth=30,
        timeout_s=180, preprocessing="none",
    ),
}


class ConfigNotInCatalog(ValueError):
    """Raised when a config id is not in the approved catalog."""


def get_config(config_id: str) -> ExperimentConfig:
    if config_id not in APPROVED_CONFIGS:
        raise ConfigNotInCatalog(
            f"'{config_id}' is not in {CATALOG_VERSION}. "
            f"Approved: {sorted(APPROVED_CONFIGS)}."
        )
    return APPROVED_CONFIGS[config_id]


def default_config() -> ExperimentConfig:
    """Deterministic baseline pick."""
    return APPROVED_CONFIGS["CFG-BMC-SHALLOW"]
