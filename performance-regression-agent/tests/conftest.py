"""Shared fixtures."""

from __future__ import annotations

import pytest

from perf_regression_agent.benchmark import build_dataset
from perf_regression_agent.detector import analyze
from perf_regression_agent.models import TelemetryDataset


@pytest.fixture(scope="session")
def dataset() -> TelemetryDataset:
    return build_dataset()


@pytest.fixture(scope="session")
def report(dataset: TelemetryDataset):
    return analyze(dataset)
