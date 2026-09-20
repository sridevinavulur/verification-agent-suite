"""Deterministic register-map front ends: JSON, YAML, CSV, Markdown table.

Every parser produces a normalized :class:`RegisterMap`. Access-type tokens are
mapped onto the closed :class:`AccessType` enum via :data:`ACCESS_ALIASES`; an
unrecognized token raises :class:`ParseError` rather than being silently
coerced or invented.

The parsers are intentionally strict about *structure* (so malformed input is
caught) but liberal about *notation* (hex ``0x..``, decimal, ``msb:lsb`` ranges,
``[msb:lsb]`` bracketed ranges, blank/reserved cells).
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

import yaml

from .models import AccessType, Field_, Register, RegisterMap

__all__ = ["ParseError", "load_register_map", "parse_map_text", "ACCESS_ALIASES"]


class ParseError(ValueError):
    """Raised when a register-map source cannot be normalized."""


# Map common source tokens onto the closed AccessType enum. Case-insensitive.
ACCESS_ALIASES: dict[str, AccessType] = {
    "ro": AccessType.RO,
    "r": AccessType.RO,
    "read-only": AccessType.RO,
    "readonly": AccessType.RO,
    "rw": AccessType.RW,
    "read-write": AccessType.RW,
    "readwrite": AccessType.RW,
    "rw1": AccessType.RW,
    "wo": AccessType.WO,
    "w": AccessType.WO,
    "write-only": AccessType.WO,
    "writeonly": AccessType.WO,
    "w1c": AccessType.W1C,
    "rw1c": AccessType.W1C,
    "wc": AccessType.W1C,
    "write-1-clear": AccessType.W1C,
    "w1s": AccessType.W1S,
    "rw1s": AccessType.W1S,
    "ws": AccessType.W1S,
    "write-1-set": AccessType.W1S,
    "rc": AccessType.RC,
    "read-clear": AccessType.RC,
    "reserved": AccessType.RESERVED,
    "rsvd": AccessType.RESERVED,
    "res": AccessType.RESERVED,
}


def _parse_int(value: Any, *, ctx: str) -> int:
    """Parse an int from int/hex-string/decimal-string. Empty -> 0."""
    if value is None:
        return 0
    if isinstance(value, bool):  # guard: bool is an int subclass
        raise ParseError(f"{ctx}: boolean is not a valid integer")
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if s == "" or s.lower() in {"-", "n/a", "na", "none"}:
        return 0
    s = s.replace("_", "")
    try:
        if s.lower().startswith("0x"):
            return int(s, 16)
        if s.lower().endswith("h"):
            return int(s[:-1], 16)
        if re.fullmatch(r"[0-9]+'h[0-9a-fA-F]+", s):  # SV literal 8'hFF
            return int(s.split("h", 1)[1], 16)
        return int(s, 10)
    except ValueError as exc:  # noqa: TRY003
        raise ParseError(f"{ctx}: cannot parse integer from {value!r}") from exc


def _parse_access(value: Any, *, ctx: str) -> AccessType:
    if value is None:
        raise ParseError(f"{ctx}: missing access type")
    token = str(value).strip().lower()
    if token == "":
        raise ParseError(f"{ctx}: empty access type")
    if token not in ACCESS_ALIASES:
        raise ParseError(
            f"{ctx}: unknown access type {value!r} (not in supported set "
            f"{sorted({a.value for a in AccessType})}); the tool will not invent semantics"
        )
    return ACCESS_ALIASES[token]


_RANGE_RE = re.compile(r"^\[?\s*(\d+)\s*:\s*(\d+)\s*\]?$")


def _parse_bit_range(
    *,
    bits: Any = None,
    offset: Any = None,
    width: Any = None,
    ctx: str,
) -> tuple[int, int]:
    """Return ``(bit_offset, bit_width)`` from various notations.

    Accepts either an explicit ``offset``+``width`` pair, or a ``bits`` string
    like ``"7:0"``, ``"[7:0]"``, or a single-bit ``"5"``.
    """
    if offset is not None or width is not None:
        off = _parse_int(offset, ctx=f"{ctx} bit_offset")
        wid = _parse_int(width, ctx=f"{ctx} bit_width") if width is not None else 1
        if wid < 1:
            raise ParseError(f"{ctx}: bit_width must be >= 1")
        return off, wid
    if bits is None:
        raise ParseError(f"{ctx}: no bit range specified")
    s = str(bits).strip()
    m = _RANGE_RE.match(s)
    if m:
        msb, lsb = int(m.group(1)), int(m.group(2))
        if msb < lsb:
            msb, lsb = lsb, msb
        return lsb, msb - lsb + 1
    if re.fullmatch(r"\d+", s):
        return int(s), 1
    raise ParseError(f"{ctx}: cannot parse bit range from {bits!r}")


def _fields_from_list(raw_fields: Any, *, reg_ctx: str) -> list[Field_]:
    if raw_fields is None:
        return []
    if not isinstance(raw_fields, list):
        raise ParseError(f"{reg_ctx}: 'fields' must be a list")
    out: list[Field_] = []
    for i, rf in enumerate(raw_fields):
        if not isinstance(rf, dict):
            raise ParseError(f"{reg_ctx} field[{i}]: must be a mapping")
        fctx = f"{reg_ctx} field {rf.get('name', i)!r}"
        offset, width = _parse_bit_range(
            bits=rf.get("bits"),
            offset=rf.get("bit_offset", rf.get("offset")),
            width=rf.get("bit_width", rf.get("width")),
            ctx=fctx,
        )
        out.append(
            Field_(
                name=str(rf["name"]) if "name" in rf else f"field_{i}",
                bit_offset=offset,
                bit_width=width,
                access=_parse_access(rf.get("access"), ctx=fctx),
                reset_value=_parse_int(rf.get("reset", rf.get("reset_value", 0)), ctx=fctx),
                description=str(rf.get("description", "")),
                side_effect=str(rf.get("side_effect", "")),
                interrupt_related=bool(rf.get("interrupt_related", False)),
            )
        )
    return out


def _map_from_dict(data: dict[str, Any], *, source_format: str) -> RegisterMap:
    if "registers" not in data:
        raise ParseError("register map must contain a 'registers' list")
    raw_regs = data["registers"]
    if not isinstance(raw_regs, list):
        raise ParseError("'registers' must be a list")
    registers: list[Register] = []
    for i, rr in enumerate(raw_regs):
        if not isinstance(rr, dict):
            raise ParseError(f"register[{i}]: must be a mapping")
        rctx = f"register {rr.get('name', i)!r}"
        if "name" not in rr:
            raise ParseError(f"register[{i}]: missing 'name'")
        if "address" not in rr and "offset" not in rr:
            raise ParseError(f"{rctx}: missing 'address'/'offset'")
        fields = _fields_from_list(rr.get("fields"), reg_ctx=rctx)
        # If register-level access absent, default RW unless single reserved field.
        access = (
            _parse_access(rr.get("access"), ctx=rctx)
            if rr.get("access") is not None
            else AccessType.RW
        )
        registers.append(
            Register(
                name=str(rr["name"]),
                address=_parse_int(rr.get("address", rr.get("offset")), ctx=rctx),
                width_bits=_parse_int(rr.get("width_bits", rr.get("width", 32)), ctx=rctx),
                access=access,
                reset_value=_parse_int(rr.get("reset", rr.get("reset_value", 0)), ctx=rctx),
                description=str(rr.get("description", "")),
                fields=fields,
            )
        )
    return RegisterMap(
        name=str(data.get("name", "csr_block")),
        data_width_bits=_parse_int(data.get("data_width_bits", 32), ctx="data_width_bits"),
        address_unit_bytes=_parse_int(
            data.get("address_unit_bytes", 1), ctx="address_unit_bytes"
        ),
        registers=registers,
        source_format=source_format,
    )


# --------------------------------------------------------------------------- CSV


_CSV_ALIASES = {
    "register": "register",
    "reg": "register",
    "name": "register",
    "field": "field",
    "field_name": "field",
    "address": "address",
    "offset": "address",
    "addr": "address",
    "bits": "bits",
    "bit_range": "bits",
    "range": "bits",
    "access": "access",
    "type": "access",
    "reset": "reset",
    "reset_value": "reset",
    "width": "width",
    "description": "description",
    "desc": "description",
}


def _parse_csv(text: str) -> RegisterMap:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ParseError("CSV has no header row")
    # normalize headers
    header_map = {}
    for h in reader.fieldnames:
        key = h.strip().lower().replace(" ", "_")
        header_map[h] = _CSV_ALIASES.get(key, key)
    if "register" not in header_map.values():
        raise ParseError("CSV must have a register/name column")

    # group rows by register; each row may be a register row or a field row
    regs: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for lineno, row in enumerate(reader, start=2):
        norm = {header_map[k]: (v or "").strip() for k, v in row.items() if k is not None}
        reg_name = norm.get("register", "")
        if reg_name == "":
            raise ParseError(f"CSV line {lineno}: empty register name")
        if reg_name not in regs:
            regs[reg_name] = {
                "name": reg_name,
                "address": norm.get("address", ""),
                "width_bits": norm.get("width", "32") or "32",
                "reset": norm.get("reset", "0") or "0",
                "description": norm.get("description", ""),
                "fields": [],
            }
            order.append(reg_name)
            # A row with an address but no field name is the register-defining row.
        field_name = norm.get("field", "")
        if field_name:
            regs[reg_name]["fields"].append(
                {
                    "name": field_name,
                    "bits": norm.get("bits", ""),
                    "access": norm.get("access", "RW"),
                    "reset": norm.get("reset", "0") or "0",
                    "description": norm.get("description", ""),
                }
            )
        else:
            # register-level row; capture access at register scope
            if norm.get("access"):
                regs[reg_name]["access"] = norm["access"]
    data = {"registers": [regs[n] for n in order]}
    return _map_from_dict(data, source_format="csv")


# ---------------------------------------------------------------------- Markdown


def _split_md_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_md_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells) if cells else False


def _parse_markdown(text: str) -> RegisterMap:
    """Parse the first GitHub-style pipe table found in the Markdown."""
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        raise ParseError("no Markdown pipe table found")
    header = _split_md_row(lines[0])
    sep = _split_md_row(lines[1])
    if not _is_md_separator(sep):
        raise ParseError("Markdown table missing separator row (---)")
    header_norm = [_CSV_ALIASES.get(h.strip().lower().replace(" ", "_"), h) for h in header]
    if "register" not in header_norm:
        raise ParseError("Markdown table must have a register/name column")
    body = lines[2:]
    # reuse CSV grouping semantics by re-emitting rows as CSV
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header_norm)
    for ln in body:
        cells = _split_md_row(ln)
        if len(cells) != len(header_norm):
            # pad/truncate defensively
            cells = (cells + [""] * len(header_norm))[: len(header_norm)]
        writer.writerow(cells)
    return _parse_csv(buf.getvalue())


def _with_format(m: RegisterMap, fmt: str) -> RegisterMap:
    m.source_format = fmt
    return m


# --------------------------------------------------------------------- dispatch


def parse_map_text(text: str, fmt: str) -> RegisterMap:
    """Parse register-map ``text`` given an explicit format string."""
    fmt = fmt.lower()
    if fmt == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParseError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ParseError("top-level JSON must be an object")
        return _map_from_dict(data, source_format="json")
    if fmt in {"yaml", "yml"}:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ParseError(f"invalid YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise ParseError("top-level YAML must be a mapping")
        return _map_from_dict(data, source_format="yaml")
    if fmt == "csv":
        return _parse_csv(text)
    if fmt in {"md", "markdown"}:
        return _with_format(_parse_markdown(text), "markdown")
    raise ParseError(f"unsupported format {fmt!r}")


_EXT_TO_FMT = {
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".csv": "csv",
    ".md": "markdown",
    ".markdown": "markdown",
}


def load_register_map(path: str | Path, fmt: str | None = None) -> RegisterMap:
    """Load and normalize a register map from ``path`` (format inferred from ext)."""
    p = Path(path)
    if fmt is None:
        fmt = _EXT_TO_FMT.get(p.suffix.lower())
        if fmt is None:
            raise ParseError(
                f"cannot infer format from extension {p.suffix!r}; pass fmt= explicitly"
            )
    text = p.read_text(encoding="utf-8")
    m = parse_map_text(text, fmt)
    m.source_file = str(p)
    return m
