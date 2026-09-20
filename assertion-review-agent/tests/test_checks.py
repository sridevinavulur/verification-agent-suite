"""Targeted tests for individual deterministic checks."""

from __future__ import annotations

from pathlib import Path

from assertion_review.models import CheckId, RtlIntentManifest, Severity
from assertion_review.review import review_text

REPO = Path(__file__).resolve().parent.parent
HANDSHAKE_MANIFEST = RtlIntentManifest.model_validate_json(
    (REPO / "examples" / "manifests" / "handshake.manifest.json").read_text()
)
FIFO_MANIFEST = RtlIntentManifest.model_validate_json(
    (REPO / "examples" / "manifests" / "fifo.manifest.json").read_text()
)


def check_ids(text, manifest=None, requirement_ids=None):
    report = review_text(text, manifest=manifest, requirement_ids=requirement_ids)
    return {f.check_id for f in report.findings}


def find(text, cid, manifest=None):
    report = review_text(text, manifest=manifest)
    return [f for f in report.findings if f.check_id == cid]


def test_missing_clock():
    assert CheckId.MISSING_CLOCK in check_ids("L: assert property (a |-> b);")


def test_missing_disable_iff_warns_with_reset_candidate():
    ids = check_ids(
        "L: assert property (@(posedge clk) a |-> b);", manifest=HANDSHAKE_MANIFEST
    )
    assert CheckId.MISSING_DISABLE_IFF in ids


def test_reset_polarity_active_low_unnegated_is_error():
    # rst_n active-low used un-negated -> ERROR.
    fs = find(
        "L: assert property (@(posedge clk) disable iff (rst_n) req |=> grant);",
        CheckId.RESET_POLARITY_RISK,
        manifest=HANDSHAKE_MANIFEST,
    )
    assert fs and fs[0].severity == Severity.ERROR


def test_reset_polarity_active_low_negated_is_clean():
    fs = find(
        "L: assert property (@(posedge clk) disable iff (!rst_n) req |=> grant);",
        CheckId.RESET_POLARITY_RISK,
        manifest=HANDSHAKE_MANIFEST,
    )
    assert fs == []


def test_reset_polarity_active_high_negated_is_error():
    fs = find(
        "L: assert property (@(posedge clk) disable iff (!rst) full |-> !push);",
        CheckId.RESET_POLARITY_RISK,
        manifest=FIFO_MANIFEST,
    )
    assert fs and fs[0].severity == Severity.ERROR


def test_implication_style_risk():
    assert CheckId.IMPLICATION_STYLE_RISK in check_ids(
        "L: assert property (@(posedge clk) a |-> ##1 b);"
    )


def test_unbounded_temporal_dollar():
    assert CheckId.UNBOUNDED_TEMPORAL in check_ids(
        "L: assert property (@(posedge clk) a |-> ##[0:$] b);"
    )


def test_weak_consequent_constant_true():
    fs = find(
        "L: assert property (@(posedge clk) a |-> 1'b1);", CheckId.WEAK_CONSEQUENT
    )
    assert fs and fs[0].severity == Severity.ERROR


def test_antecedent_equals_consequent():
    fs = find(
        "L: assert property (@(posedge clk) req |-> req);",
        CheckId.ANTECEDENT_IN_CONSEQUENT,
    )
    assert fs and fs[0].severity == Severity.ERROR


def test_trivially_passing_constant_body():
    fs = find("L: assert property (@(posedge clk) 1'b1);", CheckId.TRIVIALLY_PASSING)
    assert fs and fs[0].severity == Severity.ERROR


def test_trivially_passing_false_antecedent():
    fs = find(
        "L: assert property (@(posedge clk) 1'b0 |-> x);", CheckId.TRIVIALLY_PASSING
    )
    assert fs and fs[0].severity == Severity.ERROR


def test_assume_constrains_output_is_error():
    # ack is an output in the handshake manifest.
    fs = find(
        "L: assume property (@(posedge clk) ack == 1'b0);",
        CheckId.ASSUME_CONSTRAINS_OUTPUT,
        manifest=HANDSHAKE_MANIFEST,
    )
    assert fs and fs[0].severity == Severity.ERROR


def test_assume_on_input_is_ok():
    fs = find(
        "L: assume property (@(posedge clk) req == 1'b0);",
        CheckId.ASSUME_CONSTRAINS_OUTPUT,
        manifest=HANDSHAKE_MANIFEST,
    )
    assert fs == []


def test_undeclared_signal():
    fs = find(
        "L: assert property (@(posedge clk) disable iff (!rst_n) nope |-> ack);",
        CheckId.UNDECLARED_SIGNAL,
        manifest=HANDSHAKE_MANIFEST,
    )
    assert any("nope" in f.message for f in fs)


def test_width_mismatch():
    # data is 8-bit; compare against 4-bit literal.
    fs = find(
        "L: assert property (@(posedge clk) disable iff (!rst_n) req |-> data == 4'hA);",
        CheckId.WIDTH_MISMATCH,
        manifest=HANDSHAKE_MANIFEST,
    )
    assert fs and fs[0].severity == Severity.WARNING


def test_name_semantics_generic_name():
    ids = check_ids("p1: assert property (@(posedge clk) disable iff (rst) a |-> b);")
    assert CheckId.NAME_SEMANTICS in ids


def test_name_semantics_good_name_clean():
    fs = find(
        "req_gets_grant: assert property (@(posedge clk) disable iff (rst) req |-> grant);",
        CheckId.NAME_SEMANTICS,
    )
    assert fs == []


def test_traceability_tag_recognized():
    src = (
        "// @requirement: REQ-1\n"
        "good_name_req: assert property (@(posedge clk) disable iff (rst) req |-> grant);\n"
    )
    fs = [f for f in review_text(src).findings if f.check_id == CheckId.REQ_TRACEABILITY]
    assert fs == []


def test_traceability_unknown_id_warns():
    src = (
        "// @requirement: REQ-UNKNOWN\n"
        "good_req: assert property (@(posedge clk) disable iff (rst) req |-> grant);\n"
    )
    report = review_text(src, requirement_ids={"REQ-1"})
    fs = [f for f in report.findings if f.check_id == CheckId.REQ_TRACEABILITY]
    assert fs and fs[0].severity == Severity.WARNING


def test_vacuity_risk_is_heuristic_only():
    fs = find(
        "L: assert property (@(posedge clk) (a && b && c && d) |-> e);",
        CheckId.VACUITY_RISK,
    )
    assert fs and fs[0].heuristic and fs[0].severity == Severity.INFO


def test_cover_property_skips_disable_iff_check():
    ids = check_ids("c: cover property (@(posedge clk) a ##1 b);", manifest=FIFO_MANIFEST)
    assert CheckId.MISSING_DISABLE_IFF not in ids
