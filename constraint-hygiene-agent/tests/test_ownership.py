from constraint_hygiene.analysis.ownership import classify_signals
from constraint_hygiene.models import Ownership
from constraint_hygiene.parsers.manifest import ManifestView, load_manifest


def test_classification_from_manifest(manifest_path):
    view = load_manifest(manifest_path)
    result = {c.signal: c.ownership for c in classify_signals(
        {"in_valid", "in_ready", "out_valid", "state", "fifo_count", "ghost"}, view
    )}
    assert result["in_valid"] is Ownership.ENVIRONMENT_INPUT
    assert result["in_ready"] is Ownership.DUT_OUTPUT
    assert result["out_valid"] is Ownership.DUT_OUTPUT
    assert result["state"] is Ownership.INTERNAL_STATE
    assert result["fifo_count"] is Ownership.INTERNAL_STATE
    assert result["ghost"] is Ownership.UNKNOWN


def test_no_manifest_is_all_unknown():
    view = ManifestView()  # not loaded
    result = classify_signals({"anything"}, view)
    assert result[0].ownership is Ownership.UNKNOWN
    assert "No RTL Intent Manifest" in result[0].rationale


def test_boundary_output_takes_precedence_over_register(manifest_path):
    # out_valid is both a top output port AND a register in the manifest.
    view = load_manifest(manifest_path)
    (c,) = classify_signals({"out_valid"}, view)
    assert c.ownership is Ownership.DUT_OUTPUT
