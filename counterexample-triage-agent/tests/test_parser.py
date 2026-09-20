"""Tests for the VCD and JSON trace parsers."""

import pytest

from cx_triage.parser import VCDParseError, load_json_trace, parse_vcd

MINIMAL_VCD = """
$timescale 1ns $end
$scope module tb $end
$var wire 1 ! clk $end
$var reg 4 " count [3:0] $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
b0000 "
$end
#5
1!
b0001 "
#10
0!
#15
1!
b0010 "
"""


def test_parse_vcd_basic_structure():
    wt = parse_vcd(MINIMAL_VCD)
    assert wt.timescale == "1ns"
    assert set(wt.signals) == {"tb.clk", "tb.count"}
    assert wt.signals["tb.count"].width == 4
    assert wt.end_time == 15


def test_parse_vcd_scalar_and_vector_values():
    wt = parse_vcd(MINIMAL_VCD)
    clk = wt.signal("tb.clk")
    assert clk.value_at(0) == "0"
    assert clk.value_at(5) == "1"
    assert clk.value_at(12) == "0"  # held from t=10
    count = wt.signal("tb.count")
    assert count.value_at(0) == "0000"
    assert count.value_at(5) == "0001"
    assert count.value_at(15) == "0010"


def test_parse_vcd_scope_qualification():
    wt = parse_vcd(MINIMAL_VCD)
    # Names are fully qualified by scope.
    assert "tb.clk" in wt.signals
    assert "clk" not in wt.signals


def test_parse_vcd_x_z_normalized():
    vcd = (
        "$timescale 1ns $end\n$scope module t $end\n"
        "$var wire 1 ! a $end\n$upscope $end\n$enddefinitions $end\n"
        "#0\nx!\n#5\nz!\n#10\n1!\n"
    )
    wt = parse_vcd(vcd)
    a = wt.signal("t.a")
    assert a.value_at(0) == "x"
    assert a.value_at(5) == "z"
    assert a.value_at(10) == "1"


def test_parse_vcd_real_values_skipped_not_crash():
    vcd = (
        "$timescale 1ns $end\n$scope module t $end\n"
        "$var real 64 ! r $end\n$var wire 1 \" a $end\n"
        "$upscope $end\n$enddefinitions $end\n"
        "#0\nr3.14 !\n1\"\n"
    )
    wt = parse_vcd(vcd)
    # Real-valued signal produced no samples; wire still parsed.
    assert wt.signal("t.a").value_at(0) == "1"


def test_parse_vcd_bad_timestamp_raises():
    vcd = (
        "$timescale 1ns $end\n$scope module t $end\n$var wire 1 ! a $end\n"
        "$upscope $end\n$enddefinitions $end\n#notanumber\n1!\n"
    )
    with pytest.raises(VCDParseError):
        parse_vcd(vcd)


def test_parse_vcd_malformed_var_raises():
    vcd = "$timescale 1ns $end\n$var wire 1 ! $end\n$enddefinitions $end\n"
    with pytest.raises(VCDParseError):
        parse_vcd(vcd)


def test_json_trace_roundtrip():
    obj = {
        "timescale": "1ns",
        "signals": {
            "tb.a": {"width": 1, "samples": [[0, "0"], [5, "1"]]},
            "tb.b": {"width": 4, "samples": [[0, "0000"], [5, "0001"]]},
        },
    }
    wt = load_json_trace(obj)
    assert wt.signal("tb.a").value_at(5) == "1"
    assert wt.signal("tb.b").value_at(5) == "0001"
    assert wt.end_time == 5


def test_vcd_and_json_traces_equivalent(examples_dir):
    from cx_triage.parser import parse_vcd_file

    vcd = parse_vcd_file(examples_dir / "toy_counter" / "counter_fail.vcd")
    js = load_json_trace(examples_dir / "toy_counter" / "counter_fail.json")
    assert vcd.model_dump() == js.model_dump()
