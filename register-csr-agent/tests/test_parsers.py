"""Parser tests: JSON/YAML/CSV/Markdown normalize to the same manifest, plus
notation handling and strict error behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from register_csr_agent.models import AccessType
from register_csr_agent.parsers import ParseError, load_register_map, parse_map_text

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "register_maps"


def test_json_and_yaml_agree():
    j = load_register_map(EXAMPLES / "timer_block.json")
    y = load_register_map(EXAMPLES / "timer_block.yaml")
    # both should have CTRL/LOAD/COUNT; yaml adds STATUS
    j_names = {r.name for r in j.registers}
    assert {"CTRL", "LOAD", "COUNT"} <= j_names
    ctrl_j = next(r for r in j.registers if r.name == "CTRL")
    ctrl_y = next(r for r in y.registers if r.name == "CTRL")
    assert ctrl_j.address == ctrl_y.address == 0
    assert {f.name for f in ctrl_j.fields} == {"ENABLE", "MODE", "RSVD"}


def test_hex_and_range_notation():
    m = load_register_map(EXAMPLES / "timer_block.json")
    load = next(r for r in m.registers if r.name == "LOAD")
    assert load.reset_value == 0xFFFFFFFF
    ctrl = next(r for r in m.registers if r.name == "CTRL")
    mode = next(f for f in ctrl.fields if f.name == "MODE")
    assert (mode.bit_offset, mode.bit_width) == (1, 2)


def test_csv_grouping_and_fields():
    m = load_register_map(EXAMPLES / "gpio_block.csv")
    assert {r.name for r in m.registers} == {"DATA", "DIR", "INT_STAT"}
    stat = next(r for r in m.registers if r.name == "INT_STAT")
    pending = stat.fields[0]
    assert pending.name == "PENDING"
    assert pending.access == AccessType.W1C
    assert pending.bit_width == 16


def test_markdown_table_parse():
    m = load_register_map(EXAMPLES / "uart_block.md")
    assert {r.name for r in m.registers} == {"TXDATA", "RXDATA", "STATUS"}
    status = next(r for r in m.registers if r.name == "STATUS")
    txempty = next(f for f in status.fields if f.name == "TXEMPTY")
    assert txempty.reset_value == 1
    assert txempty.access == AccessType.RO


def test_access_alias_mapping():
    m = parse_map_text(
        '{"registers":[{"name":"R","address":0,"access":"read-only","reset":0}]}',
        "json",
    )
    assert m.registers[0].access == AccessType.RO


def test_unknown_access_rejected():
    with pytest.raises(ParseError, match="unknown access type"):
        parse_map_text(
            '{"registers":[{"name":"R","address":0,"access":"MAGIC","reset":0}]}',
            "json",
        )


def test_missing_address_rejected():
    with pytest.raises(ParseError, match="missing"):
        parse_map_text('{"registers":[{"name":"R","reset":0}]}', "json")


def test_field_reset_overflow_rejected():
    # 2-bit field with reset 0x7 should fail model validation surfaced as error
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        parse_map_text(
            '{"registers":[{"name":"R","address":0,"fields":['
            '{"name":"F","bits":"1:0","access":"RW","reset":"0x7"}]}]}',
            "json",
        )
