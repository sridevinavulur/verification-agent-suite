"""Deterministic waveform parsing.

Two loaders are provided:

* :func:`parse_vcd` -- a real VCD parser for the common subset (``$timescale``,
  ``$scope``/``$upscope``, ``$var`` for ``wire``/``reg``, ``$enddefinitions``,
  ``#<time>`` timestamps, scalar changes ``0!``/``1!``/``x!``/``z!`` and vector
  changes ``b<bits> !``). Real-valued (``r...``) dumps are skipped with a note.
* :func:`load_json_trace` -- a simple JSON trace format that is easy to author
  for CI fixtures.

Neither loader executes anything or reaches the network. Parsing is a pure
transformation of text into a :class:`~cx_triage.models.WaveTrace`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import SignalTrace, WaveTrace, WaveValue


class VCDParseError(ValueError):
    """Raised when a VCD file violates the supported subset in a fatal way."""


def _normalize_scalar(char: str) -> str:
    c = char.lower()
    if c in ("0", "1", "x", "z"):
        return c
    # Treat unknown scalar codes conservatively as 'x'.
    return "x"


def parse_vcd(text: str) -> WaveTrace:
    """Parse the common subset of VCD into a :class:`WaveTrace`.

    The parser is intentionally strict about structure but tolerant of unknown
    directives it can safely ignore. Unsupported constructs never crash the run;
    they are simply not represented (real-valued signals, e.g.).
    """
    timescale = "1ns"
    # code -> fully-qualified signal name
    code_to_name: dict[str, str] = {}
    code_to_width: dict[str, int] = {}
    signals: dict[str, SignalTrace] = {}
    scope_stack: list[str] = []

    current_time = 0
    end_time = 0

    def ensure_signal(code: str) -> SignalTrace | None:
        name = code_to_name.get(code)
        if name is None:
            return None
        sig = signals.get(name)
        if sig is None:
            sig = SignalTrace(name=name, width=code_to_width.get(code, 1))
            signals[name] = sig
        return sig

    def record(code: str, value: str) -> None:
        sig = ensure_signal(code)
        if sig is None:
            return
        # Collapse duplicate consecutive samples to keep the trace minimal.
        if sig.samples and sig.samples[-1].time == current_time:
            sig.samples[-1] = WaveValue(time=current_time, value=value)
        elif sig.samples and sig.samples[-1].value == value:
            return
        else:
            sig.samples.append(WaveValue(time=current_time, value=value))

    lines = text.splitlines()
    i = 0
    in_definitions = True
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue

        if in_definitions:
            if line.startswith("$timescale"):
                # $timescale 1ns $end  OR spread across tokens/lines
                body = line[len("$timescale"):]
                while "$end" not in body:
                    if i >= len(lines):
                        break
                    body += " " + lines[i].strip()
                    i += 1
                body = body.replace("$end", "").strip()
                if body:
                    timescale = body
                continue
            if line.startswith("$scope"):
                parts = line.split()
                # $scope module dut $end
                if len(parts) >= 3:
                    scope_stack.append(parts[2])
                continue
            if line.startswith("$upscope"):
                if scope_stack:
                    scope_stack.pop()
                continue
            if line.startswith("$var"):
                # $var wire 1 ! clk $end  |  $var reg 4 " count [3:0] $end
                parts = line.split()
                # $var <type> <width> <code> <name> [range] $end
                if len(parts) < 6 or parts[-1] != "$end" or parts[4] == "$end":
                    raise VCDParseError(f"Malformed $var: {line!r}")
                width = int(parts[2])
                code = parts[3]
                base_name = parts[4]
                fq = ".".join(scope_stack + [base_name]) if scope_stack else base_name
                code_to_name[code] = fq
                code_to_width[code] = width
                continue
            if line.startswith("$enddefinitions"):
                in_definitions = False
                continue
            if line.startswith("$dumpvars") or line.startswith("$dumpall"):
                in_definitions = False
                continue
            # $version, $date, $comment, other -- ignore in definitions.
            continue

        # Value-change section.
        if line.startswith("#"):
            try:
                current_time = int(line[1:])
            except ValueError as exc:
                raise VCDParseError(f"Bad timestamp: {line!r}") from exc
            end_time = max(end_time, current_time)
            continue
        if line in ("$dumpvars", "$dumpall", "$dumpon", "$dumpoff", "$end"):
            continue
        if line.startswith("$"):
            # Directive within value section (e.g. $comment ... $end). Skip line.
            continue

        c0 = line[0]
        if c0 in "01xzXZ":
            # Scalar change: value char immediately followed by code.
            value = _normalize_scalar(c0)
            code = line[1:].strip()
            record(code, value)
        elif c0 in "bB":
            # Vector change: b<bits> <code>
            parts = line.split()
            if len(parts) < 2:
                continue
            bits = parts[0][1:]
            code = parts[1]
            record(code, bits)
        elif c0 in "rR":
            # Real-valued dumps unsupported; skip silently (documented limitation).
            continue
        # Anything else is ignored.

    # Ensure sample ordering is stable/ascending.
    for sig in signals.values():
        sig.samples.sort(key=lambda s: s.time)

    return WaveTrace(timescale=timescale, signals=signals, end_time=end_time)


def parse_vcd_file(path: str | Path) -> WaveTrace:
    return parse_vcd(Path(path).read_text())


def load_json_trace(data: dict | str | Path) -> WaveTrace:
    """Load the simple JSON trace format.

    Schema::

        {
          "timescale": "1ns",
          "signals": {
            "dut.clk":   {"width": 1, "samples": [[0,"0"],[5,"1"], ...]},
            "dut.count": {"width": 4, "samples": [[0,"0000"], ...]}
          }
        }
    """
    if isinstance(data, (str, Path)):
        p = Path(data)
        if p.exists():
            obj = json.loads(p.read_text())
        else:
            obj = json.loads(str(data))
    else:
        obj = data

    signals: dict[str, SignalTrace] = {}
    end_time = 0
    for name, spec in obj.get("signals", {}).items():
        width = int(spec.get("width", 1))
        samples = [WaveValue(time=int(t), value=str(v)) for t, v in spec.get("samples", [])]
        samples.sort(key=lambda s: s.time)
        if samples:
            end_time = max(end_time, samples[-1].time)
        signals[name] = SignalTrace(name=name, width=width, samples=samples)

    return WaveTrace(
        timescale=obj.get("timescale", "1ns"),
        signals=signals,
        end_time=end_time,
    )
