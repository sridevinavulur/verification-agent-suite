from __future__ import annotations

from pathlib import Path

import pytest

from coverage_closure_agent.io import load_inputs, load_labels
from coverage_closure_agent.models import SampleLabels, TriageInputs

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def toy_inputs() -> TriageInputs:
    return load_inputs(EXAMPLES / "toy_benchmark.json")


@pytest.fixture
def toy_labels() -> SampleLabels:
    return load_labels(EXAMPLES / "toy_labels.json")
