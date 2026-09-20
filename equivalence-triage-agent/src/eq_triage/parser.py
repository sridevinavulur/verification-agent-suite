"""Parsers / mocked tool adapters.

Two input paths:

1. :func:`parse_equivalence_log` -- a *real* line-oriented parser for a small,
   documented equivalence-checker log format (the ``EQLOG/1`` format, modeled on
   the textual reports LEC tools emit). This is a MOCK adapter in the sense that
   it targets a synthetic-but-representative format rather than any proprietary
   tool, but the parsing logic is genuine.

2. :func:`load_manifest` -- consumes the canonical RTL Intent Manifest JSON
   (``rtl-intent-ingestor/schemas/manifest.schema.json``) *or* a compact local
   ``DesignManifest`` JSON, and normalizes to :class:`DesignManifest`.

The ``EQLOG/1`` format (see examples/):

    EQLOG/1
    tool: <name>
    tool_version: <v>
    reference: <design_name>
    revised: <design_name>
    status: EQUIVALENT | NOT_EQUIVALENT | INCONCLUSIVE | TIMEOUT | ERROR | ABORTED
    compare_points: <matched>/<total>
    config: <key> = <ref_value> | <rev_value>
    mismatch: <name> kind=<kind> ref=<sig>[w<width>] rev=<sig>[w<width>] \
        fanin=<s1,s2,...>
    cex: <compare_point> @<time> <signal> ref=<v> rev=<v>
    msg: <free text>

Order is not significant except that ``cex:`` lines attach to the most recently
declared ``mismatch:`` with a matching compare point (or by explicit name).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import (
    CexVector,
    ConfigDelta,
    Counterexample,
    DesignManifest,
    EquivalenceLog,
    EquivalenceStatus,
    MismatchKind,
    MismatchPoint,
    ResetInfo,
    ResetPolarity,
    ResetSync,
)


class LogParseError(ValueError):
    """Raised on malformed EQLOG input."""


_KV_RE = re.compile(r"(\w+)=((?:'[^']*')|(?:\"[^\"]*\")|(?:\{[^}]*\})|(?:[^\s]+))")


def _parse_sig_width(token: str) -> tuple[str, int | None]:
    """Parse ``name`` or ``name[wN]`` -> (name, width|None)."""
    m = re.match(r"^(.*?)(?:\[w(\d+)\])?$", token)
    if not m:
        return token, None
    name = m.group(1)
    width = int(m.group(2)) if m.group(2) else None
    return name, width


def _parse_kind(value: str) -> MismatchKind:
    try:
        return MismatchKind(value)
    except ValueError:
        return MismatchKind.UNKNOWN


def parse_equivalence_log(text: str, source_path: str | None = None) -> EquivalenceLog:
    """Parse an ``EQLOG/1`` textual equivalence report into a typed model."""
    lines = text.splitlines()
    if not lines or not lines[0].strip().startswith("EQLOG/1"):
        raise LogParseError("Not an EQLOG/1 file (missing 'EQLOG/1' header).")

    header: dict[str, str] = {}
    mismatches: dict[str, MismatchPoint] = {}
    order: list[str] = []
    config_deltas: list[ConfigDelta] = []
    messages: list[str] = []
    matched = total = 0

    for raw in lines[1:]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise LogParseError(f"Malformed line (no ':'): {raw!r}")
        tag, _, rest = line.partition(":")
        tag = tag.strip()
        rest = rest.strip()

        if tag in {"tool", "tool_version", "reference", "revised", "status"}:
            header[tag] = rest
        elif tag == "compare_points":
            m = re.match(r"(\d+)\s*/\s*(\d+)", rest)
            if not m:
                raise LogParseError(f"Bad compare_points line: {rest!r}")
            matched, total = int(m.group(1)), int(m.group(2))
        elif tag == "config":
            # <key> = <ref> | <rev>
            m = re.match(r"(.+?)\s*=\s*(.*?)\s*\|\s*(.*)$", rest)
            if not m:
                raise LogParseError(f"Bad config line: {rest!r}")
            config_deltas.append(
                ConfigDelta(
                    key=m.group(1).strip(),
                    reference_value=m.group(2).strip() or None,
                    revised_value=m.group(3).strip() or None,
                )
            )
        elif tag == "mismatch":
            mp = _parse_mismatch(rest)
            mismatches[mp.name] = mp
            order.append(mp.name)
        elif tag == "cex":
            _parse_cex(rest, mismatches)
        elif tag == "msg":
            messages.append(rest)
        else:
            raise LogParseError(f"Unknown tag {tag!r} in line: {raw!r}")

    for req in ("tool", "reference", "revised", "status"):
        if req not in header:
            raise LogParseError(f"Missing required header field: {req}")

    try:
        status = EquivalenceStatus(header["status"])
    except ValueError as exc:
        raise LogParseError(f"Unknown status: {header['status']!r}") from exc

    return EquivalenceLog(
        tool=header["tool"],
        tool_version=header.get("tool_version", "unknown"),
        status=status,
        reference_design=header["reference"],
        revised_design=header["revised"],
        compare_points_total=total,
        compare_points_matched=matched,
        mismatches=[mismatches[n] for n in order],
        config_deltas=config_deltas,
        raw_log_path=source_path,
        messages=messages,
    )


def _parse_mismatch(rest: str) -> MismatchPoint:
    """Parse the body of a ``mismatch:`` line."""
    parts = rest.split(None, 1)
    if not parts:
        raise LogParseError("Empty mismatch line.")
    name = parts[0]
    kv = dict(_KV_RE.findall(parts[1])) if len(parts) > 1 else {}

    kind = _parse_kind(kv.get("kind", "unknown"))
    ref_sig = ref_w = rev_sig = rev_w = None
    if "ref" in kv:
        ref_sig, ref_w = _parse_sig_width(kv["ref"])
    if "rev" in kv:
        rev_sig, rev_w = _parse_sig_width(kv["rev"])
    fanin: list[str] = []
    if "fanin" in kv:
        fanin = [s for s in kv["fanin"].strip("'\"").split(",") if s]

    return MismatchPoint(
        name=name,
        kind=kind,
        ref_signal=ref_sig,
        rev_signal=rev_sig,
        ref_width=ref_w,
        rev_width=rev_w,
        fanin_signals=fanin,
    )


def _parse_cex(rest: str, mismatches: dict[str, MismatchPoint]) -> None:
    """Parse a ``cex:`` line and attach it to its compare point."""
    m = re.match(
        r"(?P<cp>\S+)\s+@(?P<t>\d+)\s+(?P<sig>\S+)"
        r"(?:\s+ref=(?P<ref>\S+))?(?:\s+rev=(?P<rev>\S+))?",
        rest,
    )
    if not m:
        raise LogParseError(f"Bad cex line: {rest!r}")
    cp = m.group("cp")
    if cp not in mismatches:
        raise LogParseError(f"cex references unknown compare point: {cp!r}")
    mp = mismatches[cp]
    if mp.counterexample is None:
        mp.counterexample = Counterexample(compare_point=cp)
    time = int(m.group("t"))
    vec = CexVector(
        signal=m.group("sig"),
        time=time,
        ref_value=m.group("ref"),
        rev_value=m.group("rev"),
    )
    mp.counterexample.vectors.append(vec)
    if vec.differs and (
        mp.counterexample.first_diff_time is None
        or time < mp.counterexample.first_diff_time
    ):
        mp.counterexample.first_diff_time = time


# --------------------------------------------------------------------------- #
# Manifest loading (canonical RTL Intent Manifest OR compact local form)      #
# --------------------------------------------------------------------------- #


def load_equivalence_log(path: Path) -> EquivalenceLog:
    return parse_equivalence_log(path.read_text(), source_path=str(path))


def load_manifest(path: Path) -> DesignManifest:
    """Load a manifest JSON, accepting either the compact local form or the
    canonical RTL Intent Manifest and normalizing to :class:`DesignManifest`."""
    data = json.loads(path.read_text())
    return normalize_manifest(data)


def normalize_manifest(data: dict) -> DesignManifest:
    """Normalize a raw manifest dict into a :class:`DesignManifest`.

    Detection:
    * If ``modules``/``parser`` keys are present -> canonical RTL Intent
      Manifest; extract widths / reset from it.
    * Otherwise treat as the compact local ``DesignManifest`` JSON.
    """
    if "modules" in data or "parser" in data:
        return _from_canonical_manifest(data)
    return DesignManifest.model_validate(data)


def _range_width(rng: dict | None) -> int | None:
    """Best-effort numeric width from a canonical ``Range`` (msb:lsb strings)."""
    if not rng:
        return 1
    try:
        msb = int(str(rng["msb"]).strip())
        lsb = int(str(rng["lsb"]).strip())
        return abs(msb - lsb) + 1
    except (ValueError, KeyError):
        return None  # parameterized width; not resolvable here


def _from_canonical_manifest(data: dict) -> DesignManifest:
    top = data.get("top")
    widths: dict[str, int] = {}
    reset = ResetInfo()

    for module in data.get("modules", []):
        for port in module.get("ports", []):
            w = _range_width(port.get("range"))
            if w is not None:
                widths[port["name"]] = w
        for net in module.get("nets", []):
            w = _range_width(net.get("range"))
            if w is not None:
                widths[net["name"]] = w
        # Take the highest-confidence reset candidate across modules.
        best_conf = -1.0
        for rc in module.get("reset_candidates", []):
            conf = float(rc.get("confidence", 0.0))
            if conf > best_conf:
                best_conf = conf
                reset = ResetInfo(
                    signal=rc.get("signal"),
                    polarity=_map_polarity(rc.get("polarity", "unknown")),
                    sync=_map_sync(rc.get("sync", "unknown")),
                )

    return DesignManifest(top=top, signal_widths=widths, reset=reset)


def _map_polarity(v: str) -> ResetPolarity:
    try:
        return ResetPolarity(v)
    except ValueError:
        return ResetPolarity.UNKNOWN


def _map_sync(v: str) -> ResetSync:
    try:
        return ResetSync(v)
    except ValueError:
        return ResetSync.UNKNOWN
