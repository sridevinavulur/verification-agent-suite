"""A deliberately small, constrained Verilog parser.

This is NOT a general Verilog frontend. It extracts exactly the structural facts
FormalFlow-Scout needs to build a dependency graph, from a synthesizable subset:

* ``module`` / ``endmodule`` with ANSI or non-ANSI port lists
* ``input`` / ``output`` / ``inout`` ports (with optional ``[msb:lsb]``)
* ``wire`` / ``reg`` / ``logic`` declarations
* continuous ``assign lhs = rhs;``
* ``always @(...)`` blocks: edge-sensitive (``posedge``/``negedge``) => sequential,
  ``@*`` / ``always_comb`` => combinational
* blocking (``=``) and nonblocking (``<=``) assignments inside blocks
* simple ``if (rst) ... else ...`` reset detection inside sequential blocks

Everything it cannot parse is recorded as an ``UnresolvedNote`` rather than
silently dropped, so no structural dependency is lost without a warning. If a
construct is dropped silently the COI could become unsound; we surface it.

RHS identifier extraction is purely lexical (word tokens that are not Verilog
keywords or numbers). This over-approximates dependencies (it may include a
name that is actually a function or macro), which keeps the COI *sound* - we
never miss a real dependency, we may only add a spurious one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_KEYWORDS = frozenset(
    {
        "module",
        "endmodule",
        "input",
        "output",
        "inout",
        "wire",
        "reg",
        "logic",
        "assign",
        "always",
        "always_ff",
        "always_comb",
        "always_latch",
        "begin",
        "end",
        "if",
        "else",
        "posedge",
        "negedge",
        "or",
        "and",
        "not",
        "case",
        "endcase",
        "default",
        "parameter",
        "localparam",
        "generate",
        "endgenerate",
        "for",
        "integer",
        "genvar",
        "signed",
        "unsigned",
    }
)

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9$]*")
_NUM_RE = re.compile(r"^\d*'[bBoOdDhH]?[0-9a-fA-FxXzZ_]+$|^\d+$")


@dataclass
class UnresolvedNote:
    kind: str
    detail: str
    line: int


@dataclass
class ParsedPort:
    name: str
    direction: str  # input | output | inout
    line: int


@dataclass
class ParsedNet:
    name: str
    net_kind: str  # wire | reg | logic
    line: int


@dataclass
class ParsedAssign:
    lhs: str
    rhs_signals: list[str]
    line: int


@dataclass
class ParsedProcAssign:
    lhs: str
    rhs_signals: list[str]
    nonblocking: bool
    line: int


@dataclass
class ParsedProcedure:
    is_sequential: bool
    clock: str | None
    reset: str | None
    reset_edge: str | None  # posedge/negedge of reset in sensitivity list
    assigns: list[ParsedProcAssign]
    line: int


@dataclass
class ParsedInstance:
    module: str
    name: str
    connections: list[tuple[str | None, str]]  # (formal, actual)
    line: int


@dataclass
class ParsedModule:
    name: str
    line: int
    ports: list[ParsedPort] = field(default_factory=list)
    nets: list[ParsedNet] = field(default_factory=list)
    assigns: list[ParsedAssign] = field(default_factory=list)
    procedures: list[ParsedProcedure] = field(default_factory=list)
    instances: list[ParsedInstance] = field(default_factory=list)


@dataclass
class ParseResult:
    modules: list[ParsedModule] = field(default_factory=list)
    unresolved: list[UnresolvedNote] = field(default_factory=list)
    file: str = "<memory>"


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _rhs_identifiers(expr: str) -> list[str]:
    """Extract candidate signal identifiers from an RHS expression.

    Deterministic order = first-appearance order, deduplicated. Drops keywords,
    numeric literals, and Verilog system tasks (``$...``).
    """
    out: list[str] = []
    seen: set[str] = set()
    # Strip sized Verilog literals (e.g. 8'hFF, 4'd0, 1'b1) so their base/value
    # parts are not mistaken for signal identifiers.
    expr = re.sub(r"\b\d+'[bBoOdDhH][0-9a-fA-FxXzZ_]+", " ", expr)
    expr = re.sub(r"'[bBoOdDhH][0-9a-fA-FxXzZ_]+", " ", expr)
    for m in _IDENT_RE.finditer(expr):
        tok = m.group(0)
        if tok in _KEYWORDS or tok in seen:
            continue
        if _NUM_RE.match(tok):
            continue
        # A width prefix like 8'hFF matches NUM regex; a bare 'h... won't be ident.
        seen.add(tok)
        out.append(tok)
    return out


def _base_name(lhs: str) -> str:
    """Strip bit/part selects and concatenation braces from an LHS target."""
    lhs = lhs.strip()
    m = _IDENT_RE.match(lhs)
    return m.group(0) if m else lhs


def parse_verilog(text: str, file: str = "<memory>") -> ParseResult:
    """Parse the constrained subset. Returns modules + unresolved notes."""
    result = ParseResult(file=file)
    src = _strip_comments(text)
    lines = src.split("\n")

    i = 0
    n = len(lines)
    current: ParsedModule | None = None

    def line_no(idx: int) -> int:
        return idx + 1

    while i < n:
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            i += 1
            continue

        mod_m = re.match(r"module\s+([A-Za-z_]\w*)", stripped)
        if mod_m and current is None:
            header_line = line_no(i)
            current = ParsedModule(name=mod_m.group(1), line=header_line)
            # Consume the header (port list) until the ';' that ends it.
            header, i = _consume_until_semicolon(lines, i)
            _parse_ansi_ports(header, current, header_line)
            continue

        if stripped.startswith("endmodule"):
            if current is not None:
                result.modules.append(current)
                current = None
            i += 1
            continue

        if current is None:
            # Stray content outside a module.
            result.unresolved.append(
                UnresolvedNote("outside_module", stripped[:60], line_no(i))
            )
            i += 1
            continue

        # Port / net declarations (may be multi-name, e.g. "wire a, b, c;").
        decl_m = re.match(
            r"(input|output|inout)\s+(?:(wire|reg|logic)\s+)?(?:signed\s+)?(?:\[[^\]]*\]\s*)?(.+?);?$",
            stripped,
        )
        if decl_m and stripped.endswith(";"):
            direction = decl_m.group(1)
            netk = decl_m.group(2) or "wire"
            names = _split_names(decl_m.group(3))
            for nm in names:
                current.ports.append(ParsedPort(nm, direction, line_no(i)))
                if decl_m.group(2):
                    current.nets.append(ParsedNet(nm, netk, line_no(i)))
            i += 1
            continue

        net_m = re.match(
            r"(wire|reg|logic)\s+(?:signed\s+)?(?:\[[^\]]*\]\s*)?(.+?);$", stripped
        )
        if net_m:
            netk = net_m.group(1)
            for nm in _split_names(net_m.group(2)):
                # Skip if it also has an inline assign (wire x = y;)
                if "=" in nm:
                    lhs, rhs = nm.split("=", 1)
                    lhs_n = _base_name(lhs)
                    current.nets.append(ParsedNet(lhs_n, netk, line_no(i)))
                    current.assigns.append(
                        ParsedAssign(lhs_n, _rhs_identifiers(rhs), line_no(i))
                    )
                else:
                    current.nets.append(ParsedNet(_base_name(nm), netk, line_no(i)))
            i += 1
            continue

        assign_m = re.match(r"assign\s+(.+?)\s*=\s*(.+?);$", stripped)
        if assign_m:
            lhs = _base_name(assign_m.group(1))
            current.assigns.append(
                ParsedAssign(lhs, _rhs_identifiers(assign_m.group(2)), line_no(i))
            )
            i += 1
            continue

        if re.match(r"(always(_ff|_comb|_latch)?)\b", stripped):
            proc, i = _parse_always(lines, i)
            if proc is not None:
                current.procedures.append(proc)
            else:
                result.unresolved.append(
                    UnresolvedNote("always_block", stripped[:60], line_no(i))
                )
                i += 1
            continue

        inst = _try_parse_instance(stripped, line_no(i))
        if inst is not None:
            current.instances.append(inst)
            i += 1
            continue

        if stripped.startswith(("parameter", "localparam", "genvar", "integer")):
            i += 1
            continue

        # Unhandled but non-empty line inside a module.
        result.unresolved.append(
            UnresolvedNote("unparsed_line", stripped[:60], line_no(i))
        )
        i += 1

    if current is not None:  # missing endmodule
        result.modules.append(current)
        result.unresolved.append(
            UnresolvedNote("missing_endmodule", current.name, current.line)
        )
    return result


def _split_names(blob: str) -> list[str]:
    return [p.strip() for p in blob.split(",") if p.strip()]


def _consume_until_semicolon(lines: list[str], start: int) -> tuple[str, int]:
    buf: list[str] = []
    i = start
    while i < len(lines):
        buf.append(lines[i])
        if ";" in lines[i]:
            i += 1
            break
        i += 1
    return " ".join(buf), i


def _parse_ansi_ports(header: str, mod: ParsedModule, line: int) -> None:
    """Extract ANSI-style ports from a module header, if present."""
    pm = re.search(r"\((.*)\)", header, flags=re.S)
    if not pm:
        return
    inner = pm.group(1)
    for chunk in inner.split(","):
        c = chunk.strip()
        dm = re.match(
            r"(input|output|inout)\s+(?:wire|reg|logic|signed|unsigned|\s)*(?:\[[^\]]*\]\s*)?([A-Za-z_]\w*)",
            c,
        )
        if dm:
            mod.ports.append(ParsedPort(dm.group(2), dm.group(1), line))


def _parse_always(lines: list[str], start: int) -> tuple[ParsedProcedure | None, int]:
    """Parse an always block starting at ``start``. Returns (proc, next_index)."""
    # Gather the sensitivity list (may span lines up to the first 'begin' or ';').
    header_buf: list[str] = []
    i = start
    depth_found_body = False
    while i < len(lines):
        header_buf.append(lines[i])
        joined = " ".join(header_buf)
        if "begin" in lines[i] or (")" in joined and "@" in joined) or ";" in lines[i]:
            depth_found_body = True
            break
        # always_comb with no @()
        if re.match(r"always_comb\b", lines[start].strip()):
            depth_found_body = True
            break
        i += 1
    if not depth_found_body:
        return None, start

    header = " ".join(header_buf)
    is_seq = False
    clock: str | None = None
    reset: str | None = None
    reset_edge: str | None = None

    sens_m = re.search(r"@\s*\((.*?)\)", header, flags=re.S)
    if re.match(r"always_comb\b", lines[start].strip()):
        is_seq = False
    elif sens_m:
        sens = sens_m.group(1)
        if "*" in sens:
            is_seq = False
        else:
            edges = re.findall(r"(posedge|negedge)\s+([A-Za-z_]\w*)", sens)
            if edges:
                is_seq = True
                # Heuristic: clock is first edge signal; a second edge signal is
                # treated as an async reset.
                clock = edges[0][1]
                for edge_kind, sig in edges[1:]:
                    reset = sig
                    reset_edge = edge_kind
                    break
            else:
                is_seq = False
    else:
        is_seq = False

    # Now consume the body. If the header line contains 'begin', extract the
    # begin..end block; otherwise a single statement follows the sensitivity.
    header_text = " ".join(header_buf)
    has_begin = "begin" in header_text
    if has_begin:
        body_lines = _extract_body(lines, i)
        j = _find_block_end(lines, i)
    else:
        # Single-statement always: the statement is the remainder after ')'.
        stmt = header_text.split(")", 1)[-1] if ")" in header_text else ""
        body_lines = [stmt]
        j = i + 1

    reset_from_if, assigns = _parse_body_statements(body_lines)
    if reset is None and reset_from_if is not None:
        reset = reset_from_if

    proc = ParsedProcedure(
        is_sequential=is_seq,
        clock=clock,
        reset=reset,
        reset_edge=reset_edge,
        assigns=assigns,
        line=start + 1,
    )
    return proc, j


def _find_block_end(lines: list[str], begin_line_idx: int) -> int:
    """Return index just past the 'end' matching the first 'begin' at/after idx."""
    depth = 0
    i = begin_line_idx
    started = False
    while i < len(lines):
        toks = re.findall(r"\b(begin|end|endcase|endgenerate)\b", lines[i])
        for t in toks:
            if t == "begin":
                depth += 1
                started = True
            elif t == "end":
                depth -= 1
        if started and depth <= 0:
            return i + 1
        i += 1
    return i


def _extract_body(lines: list[str], begin_line_idx: int) -> list[str]:
    end_idx = _find_block_end(lines, begin_line_idx)
    body: list[str] = []
    for k in range(begin_line_idx, min(end_idx, len(lines))):
        ln = lines[k]
        if k == begin_line_idx and "begin" in ln:
            ln = ln.split("begin", 1)[1]
        body.append(ln)
    return body


_CTRL_PREFIX_RE = re.compile(
    r"^\s*(?:begin\b|end\b|if\s*\([^)]*\)|else\b|for\s*\([^)]*\)|case\b|endcase\b|default\s*:)"
)


def _strip_control_prefixes(stmt: str) -> str:
    """Repeatedly remove leading control-flow keywords/conditions from a stmt.

    Turns ``if (rst) reg_a <= 0`` into ``reg_a <= 0`` and ``else reg_a <= din``
    into ``reg_a <= din`` so the assignment target is the real signal, not a
    keyword. Non-greedy so nested ``if..else`` on one line still works.
    """
    prev = None
    while prev != stmt:
        prev = stmt
        m = _CTRL_PREFIX_RE.match(stmt)
        if m:
            stmt = stmt[m.end():]
    return stmt.strip()


def _parse_body_statements(
    body_lines: list[str],
) -> tuple[str | None, list[ParsedProcAssign]]:
    """Extract assignments and a synchronous-reset signal from a block body.

    The body is joined and split on ``;`` so that multiple statements sharing a
    line (``if (rst) x <= 0; else x <= y;``) are handled. Leading control-flow
    keywords are stripped so the assignment target is always a real signal.
    """
    assigns: list[ParsedProcAssign] = []
    sync_reset: str | None = None
    joined = " ".join(body_lines)

    # Collect identifiers from ALL branch conditions (if / else if / case
    # selectors). Every assignment in the block is made to depend on them: an
    # assignment reached only under a guard genuinely depends on that guard, and
    # over-approximating (all assigns depend on all guards) keeps the COI SOUND -
    # we never drop a real control dependency. Silently dropping guard signals
    # would make the COI an unsound under-approximation.
    guard_signals: list[str] = []
    guard_seen: set[str] = set()
    for cm in re.finditer(r"(?:if|case)\s*\(([^)]*)\)", joined):
        for g in _rhs_identifiers(cm.group(1)):
            if g not in guard_seen:
                guard_seen.add(g)
                guard_signals.append(g)

    # Detect the first "if (rst-like)" condition anywhere in the body.
    for ifm in re.finditer(r"if\s*\(\s*(!?)\s*([A-Za-z_]\w*)", joined):
        cand = ifm.group(2)
        if re.search(r"rst|reset|clr|clear", cand, re.I):
            sync_reset = cand
            break

    def _merge_guards(rhs: list[str]) -> list[str]:
        merged = list(rhs)
        rhs_set = set(rhs)
        for g in guard_signals:
            if g not in rhs_set:
                merged.append(g)
        return merged

    for raw_stmt in joined.split(";"):
        stmt = _strip_control_prefixes(raw_stmt)
        if not stmt or "=" not in stmt:
            continue
        nb = re.match(r"([A-Za-z_][\w.\[\]:\-+ ]*?)\s*<=\s*(.+)$", stmt)
        bl = re.match(r"([A-Za-z_][\w.\[\]:\-+ ]*?)\s*=\s*(.+)$", stmt)
        if nb:
            lhs = _base_name(nb.group(1))
            if lhs in _KEYWORDS:
                continue
            rhs = _merge_guards(_rhs_identifiers(nb.group(2)))
            assigns.append(ParsedProcAssign(lhs, rhs, True, 1))
        elif bl:
            lhs = _base_name(bl.group(1))
            if lhs in _KEYWORDS:
                continue
            rhs = _merge_guards(_rhs_identifiers(bl.group(2)))
            assigns.append(ParsedProcAssign(lhs, rhs, False, 1))
    return sync_reset, assigns


def _try_parse_instance(stripped: str, line: int) -> ParsedInstance | None:
    """Parse ``ModName inst_name (.p(a), .q(b));`` (named connections)."""
    m = re.match(
        r"([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\((.*)\)\s*;$", stripped
    )
    if not m:
        return None
    modname, instname, conns = m.group(1), m.group(2), m.group(3)
    if modname in _KEYWORDS:
        return None
    connections: list[tuple[str | None, str]] = []
    for cm in re.finditer(r"\.\s*([A-Za-z_]\w*)\s*\(\s*([^)]*?)\s*\)", conns):
        formal = cm.group(1)
        actual_expr = cm.group(2).strip()
        actual = _base_name(actual_expr) if actual_expr else ""
        if actual:
            connections.append((formal, actual))
    if not connections and conns.strip():
        # Positional connections - record actuals only.
        for a in _split_names(conns):
            connections.append((None, _base_name(a)))
    return ParsedInstance(modname, instname, connections, line)
