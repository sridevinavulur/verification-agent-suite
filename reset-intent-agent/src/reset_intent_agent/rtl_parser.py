"""A constrained Verilog/SystemVerilog subset parser focused on reset topology.

Scope (deliberately narrow but real):
    * ``module`` / ``endmodule`` boundaries and module name
    * ANSI and non-ANSI ``input``/``output``/``inout`` port declarations
    * ``always @(...)`` / ``always_ff`` / ``always_comb`` blocks with sensitivity
      lists, including ``posedge``/``negedge`` edges
    * ``if (...) ... else`` structure inside always blocks (one level of reset
      guard detection)
    * nonblocking (``<=``) assignments -> registers and their reset values
    * comment and string stripping

This is NOT a full SystemVerilog parser. Anything it does not understand is
reported via :class:`ParsedModule.unsupported` rather than silently dropped.

The parser produces a structural model (:class:`ParsedModule`) consumed by
:mod:`analyzer`. It performs no semantic inference about reset polarity -- that
lives in the analyzer and is always evidence-backed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import SourceLocation


# --------------------------------------------------------------------------- #
# Structural records (plain dataclasses; analyzer converts to Pydantic models)
# --------------------------------------------------------------------------- #
@dataclass
class SensitivityItem:
    signal: str
    edge: str | None  # "posedge" | "negedge" | None


@dataclass
class NbAssign:
    """A nonblocking assignment (register write)."""

    lhs: str
    rhs: str
    location: SourceLocation
    # True if this assignment is the "reset value" branch of an if/else guard
    under_reset: bool = False
    reset_signal: str | None = None
    reset_active_expr: str | None = None  # the exact guard text, e.g. "!rst_n"


@dataclass
class AlwaysBlock:
    index: int
    sensitivity: list[SensitivityItem]
    location: SourceLocation
    assigns: list[NbAssign] = field(default_factory=list)
    # signals appearing in reset guard conditions of this block
    reset_guards: list[str] = field(default_factory=list)
    # raw guard expressions in order
    guard_exprs: list[str] = field(default_factory=list)
    is_edge_sensitive: bool = False


@dataclass
class Port:
    name: str
    direction: str  # input/output/inout
    location: SourceLocation


@dataclass
class Unsupported:
    kind: str
    detail: str
    location: SourceLocation | None = None


@dataclass
class ParsedModule:
    name: str
    location: SourceLocation
    ports: list[Port] = field(default_factory=list)
    always_blocks: list[AlwaysBlock] = field(default_factory=list)
    unsupported: list[Unsupported] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Lexical preprocessing
# --------------------------------------------------------------------------- #
_LINE_COMMENT = re.compile(r"//[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(text: str) -> str:
    """Replace comments with equal-length whitespace to preserve offsets."""

    def _blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    text = _BLOCK_COMMENT.sub(_blank, text)
    text = _LINE_COMMENT.sub(_blank, text)
    return text


def _line_col(text: str, offset: int) -> tuple[int, int]:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    col = offset - (prefix.rfind("\n")) if "\n" in prefix else offset + 1
    return line, col


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
_MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_]\w*)\b")
_ALWAYS_RE = re.compile(r"\balways(_ff|_comb|_latch)?\b")
_SENS_RE = re.compile(r"@\s*\(([^)]*)\)")
_SENS_STAR_RE = re.compile(r"@\s*\*")
_PORT_DECL_RE = re.compile(
    r"\b(input|output|inout)\b\s*(?:wire|reg|logic|signed|\s)*"
    r"(?:\[[^\]]*\])?\s*([A-Za-z_]\w*)"
)
_EDGE_ITEM_RE = re.compile(r"(posedge|negedge)?\s*([A-Za-z_]\w*)")
# LHS: an identifier with an optional bit/part select (e.g. q, mem[i], q[3:0]).
# Deliberately does NOT span whitespace/keywords so `begin\n q <= ..` yields `q`.
_NB_RE = re.compile(
    r"([A-Za-z_]\w*(?:\s*\[[^\]]*\])?)\s*<=\s*([^;]+);"
)
_IF_RE = re.compile(r"\bif\s*\(")


def parse_text(text: str, filename: str) -> list[ParsedModule]:
    """Parse a Verilog/SV source string into structural module records."""
    clean = _strip_comments(text)
    modules: list[ParsedModule] = []

    for mmatch in _MODULE_RE.finditer(clean):
        name = mmatch.group(1)
        start = mmatch.start()
        end = _find_endmodule(clean, mmatch.end())
        body = clean[start:end]
        line, col = _line_col(clean, start)
        mod = ParsedModule(
            name=name,
            location=SourceLocation(file=filename, line=line, col=col),
        )
        _parse_ports(body, start, clean, filename, mod)
        _parse_always_blocks(body, start, clean, filename, mod)
        modules.append(mod)

    if not modules:
        # no module found at all -- report it
        line, col = 1, 1
        modules_unsupported = ParsedModule(
            name="<none>",
            location=SourceLocation(file=filename, line=line, col=col),
        )
        modules_unsupported.unsupported.append(
            Unsupported(kind="no_module", detail="No `module` declaration found.")
        )
        return [modules_unsupported]

    return modules


def _find_endmodule(text: str, from_idx: int) -> int:
    m = re.search(r"\bendmodule\b", text[from_idx:])
    if m:
        return from_idx + m.end()
    return len(text)


def _parse_ports(
    body: str, base: int, full: str, filename: str, mod: ParsedModule
) -> None:
    seen: set[str] = set()
    for m in _PORT_DECL_RE.finditer(body):
        direction, name = m.group(1), m.group(2)
        if name in seen:
            continue
        seen.add(name)
        line, col = _line_col(full, base + m.start(2))
        mod.ports.append(
            Port(
                name=name,
                direction=direction,
                location=SourceLocation(file=filename, line=line, col=col),
            )
        )


def _parse_always_blocks(
    body: str, base: int, full: str, filename: str, mod: ParsedModule
) -> None:
    index = 0
    for am in _ALWAYS_RE.finditer(body):
        kind_suffix = am.group(1)  # _ff/_comb/_latch/None
        after = am.end()

        sensitivity: list[SensitivityItem] = []
        is_edge = False

        # sensitivity list
        sens_region = body[after : after + 200]
        star = _SENS_STAR_RE.match(sens_region.lstrip())
        sens_match = _SENS_RE.search(sens_region)
        if star and (not sens_match or star.start() < sens_match.start()):
            pass  # combinational @*
        elif sens_match:
            inner = sens_match.group(1)
            for part in re.split(r"\bor\b|,", inner):
                part = part.strip()
                if not part:
                    continue
                em = _EDGE_ITEM_RE.match(part)
                if em:
                    edge = em.group(1)
                    sig = em.group(2)
                    sensitivity.append(SensitivityItem(signal=sig, edge=edge))
                    if edge:
                        is_edge = True
        elif kind_suffix == "_comb":
            pass
        elif kind_suffix == "_latch":
            mod.unsupported.append(
                Unsupported(
                    kind="always_latch",
                    detail="always_latch blocks are not modelled for reset analysis.",
                )
            )
            continue

        if kind_suffix == "_ff":
            is_edge = True

        # find block body span
        blk_start = after
        blk_end = _block_end(body, after)
        blk_body = body[blk_start:blk_end]

        line, col = _line_col(full, base + am.start())
        block = AlwaysBlock(
            index=index,
            sensitivity=sensitivity,
            location=SourceLocation(file=filename, line=line, col=col),
            is_edge_sensitive=is_edge,
        )
        _parse_block_body(blk_body, base + blk_start, full, filename, block)
        mod.always_blocks.append(block)
        index += 1


def _block_end(body: str, start: int) -> int:
    """Find the end of the procedural block starting at/after ``start``.

    Handles a ``begin``/``end`` span (with nesting) or a single statement
    terminated by ``;``.
    """
    i = start
    n = len(body)
    # skip sensitivity list up to first begin or statement
    depth = 0
    # find first 'begin' or ';'
    begin_m = re.search(r"\bbegin\b", body[start:])
    semi = body.find(";", start)
    if begin_m and (semi == -1 or start + begin_m.start() < semi):
        i = start + begin_m.end()
        depth = 1
        while i < n and depth > 0:
            bm = re.search(r"\bbegin\b", body[i:])
            em = re.search(r"\bend\b", body[i:])
            if em is None:
                return n
            if bm is not None and bm.start() < em.start():
                depth += 1
                i += bm.end()
            else:
                depth -= 1
                i += em.end()
        return i
    if semi != -1:
        # Single-statement always. If an `if ... ; else ...` chain follows,
        # keep consuming `; else <stmt> ;` so the else branch is not truncated.
        end = semi + 1
        while True:
            rest = body[end:]
            m = re.match(r"\s*\belse\b", rest)
            if not m:
                break
            next_semi = body.find(";", end + m.end())
            if next_semi == -1:
                return n
            # a nested `else if (..) ..;` may chain further
            end = next_semi + 1
        return end
    return n


def _parse_block_body(
    blk: str, base: int, full: str, filename: str, block: AlwaysBlock
) -> None:
    """Extract reset guards and nonblocking assignments.

    Detects the common reset idiom in an edge-sensitive block::

        if (<reset_guard>) begin <reg> <= <reset_value>; ... end
        else               begin <reg> <= <next_value>;  ... end

    Only the *first* ``if`` in an edge-sensitive block is treated as the reset
    guard, and only assignments whose RHS is a constant are attributed as reset
    values (a reset branch initialises state to constants). ``else if`` guards
    such as ``else if (en)`` are therefore NOT mistaken for resets. The guard
    expression is captured verbatim (e.g. ``!rst_n``, ``rst``); polarity is
    decided later in the analyzer, never here.
    """
    # Only the first if-guard in an edge-sensitive block is the reset guard.
    if block.is_edge_sensitive:
        first_if = _IF_RE.search(blk)
        if first_if is not None:
            cond = _balanced_paren(blk, first_if.end() - 1)
            if cond is not None:
                guard_text, cond_end = cond
                block.guard_exprs.append(guard_text.strip())
                reset_sig = _primary_reset_signal(guard_text)
                if reset_sig and reset_sig not in block.reset_guards:
                    block.reset_guards.append(reset_sig)
                # Reset-branch body ends at the matching 'else' (or block end).
                branch = _reset_branch_region(blk, cond_end)
                for nb in _NB_RE.finditer(branch):
                    lhs = _clean_lhs(nb.group(1))
                    rhs = nb.group(2).strip()
                    if not _is_constant(rhs):
                        continue
                    off = cond_end + nb.start()
                    line, col = _line_col(full, base + off)
                    block.assigns.append(
                        NbAssign(
                            lhs=lhs,
                            rhs=rhs,
                            location=SourceLocation(file=filename, line=line, col=col),
                            under_reset=True,
                            reset_signal=reset_sig,
                            reset_active_expr=guard_text.strip(),
                        )
                    )

    # All nonblocking assigns (dedup against ones already captured as reset).
    captured = {(a.lhs, a.rhs) for a in block.assigns}
    for m in _NB_RE.finditer(blk):
        lhs = _clean_lhs(m.group(1))
        rhs = m.group(2).strip()
        if (lhs, rhs) in captured:
            continue
        line, col = _line_col(full, base + m.start())
        block.assigns.append(
            NbAssign(
                lhs=lhs,
                rhs=rhs,
                location=SourceLocation(file=filename, line=line, col=col),
            )
        )


_CONST_RE = re.compile(r"\d+\s*'[bBhHdDoO][0-9a-fA-FxXzZ_]+|\d+|'[01]")


def _is_constant(rhs: str) -> bool:
    return bool(_CONST_RE.fullmatch(rhs.strip()))


def _reset_branch_region(blk: str, cond_end: int) -> str:
    """Return the text of the reset (then) branch, up to the matching else.

    Handles both ``if (..) begin ... end else`` and single-statement
    ``if (..) x <= 0; else`` forms.
    """
    rest = blk[cond_end:]
    begin_m = re.search(r"\bbegin\b", rest)
    semi = rest.find(";")
    # Single statement branch
    if not begin_m or (semi != -1 and semi < begin_m.start()):
        return rest[: semi + 1] if semi != -1 else rest
    # begin/end branch: find matching end
    i = begin_m.end()
    depth = 1
    while i < len(rest) and depth > 0:
        bm = re.search(r"\bbegin\b", rest[i:])
        em = re.search(r"\bend\b", rest[i:])
        if em is None:
            return rest
        if bm is not None and bm.start() < em.start():
            depth += 1
            i += bm.end()
        else:
            depth -= 1
            i += em.end()
    return rest[:i]


def _balanced_paren(text: str, open_idx: int) -> tuple[str, int] | None:
    """Return (inner_text, index_after_close) for a paren opened at open_idx."""
    assert text[open_idx] == "("
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i + 1
    return None


_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_KEYWORDS = {"posedge", "negedge", "or", "and", "if", "else", "begin", "end"}


def _signals_in_expr(expr: str) -> list[str]:
    out: list[str] = []
    for m in _IDENT_RE.finditer(expr):
        tok = m.group(0)
        if tok in _KEYWORDS:
            continue
        if tok not in out:
            out.append(tok)
    return out


def _primary_reset_signal(guard_text: str) -> str | None:
    """Pick the single most likely reset signal named in a guard expression.

    Heuristic: prefer an identifier whose name looks reset-like; otherwise the
    first identifier. This only selects *which signal name* -- polarity is
    decided separately with explicit evidence.
    """
    sigs = _signals_in_expr(guard_text)
    if not sigs:
        return None
    for s in sigs:
        if looks_like_reset_name(s):
            return s
    return sigs[0]


def _clean_lhs(raw: str) -> str:
    raw = raw.strip()
    # strip bit/part selects to get the base register name
    m = _IDENT_RE.match(raw)
    return m.group(0) if m else raw


# --------------------------------------------------------------------------- #
# Naming heuristics (shared with analyzer)
# --------------------------------------------------------------------------- #
_RESET_NAME_RE = re.compile(r"(^|_)(rst|reset|nrst|rstn|resetn|arst|srst)(_|n|\b)", re.I)


def looks_like_reset_name(name: str) -> bool:
    return bool(_RESET_NAME_RE.search(name)) or name.lower() in {"rst", "reset"}
