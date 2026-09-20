"""Loading helpers for the Coverage Closure Agent.

The agent ingests a single JSON bundle (the mock coverage format plus the four
companion manifests). Keeping loading in one place makes the CLI thin and gives
tests a stable entry point.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import SampleLabels, TriageInputs


def load_inputs(path: str | Path) -> TriageInputs:
    """Load and validate a :class:`TriageInputs` bundle from a JSON file."""
    data = json.loads(Path(path).read_text())
    return TriageInputs.model_validate(data)


def load_labels(path: str | Path) -> SampleLabels:
    """Load ground-truth sample labels used for metric evaluation."""
    data = json.loads(Path(path).read_text())
    return SampleLabels.model_validate(data)
