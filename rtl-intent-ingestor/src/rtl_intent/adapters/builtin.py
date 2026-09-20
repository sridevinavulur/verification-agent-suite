"""Built-in parser for the constrained synthesizable Verilog subset.

Supported (see ``SUPPORTED``):
* ``module``/``endmodule`` with ANSI or non-ANSI port lists
* ``#(parameter ...)`` and ``parameter``/``localparam`` declarations
* ``input``/``output``/``inout`` ports with optional ``wire/reg/logic`` and range
* ``wire``/``reg``/``logic`` net declarations (with range, comma lists)
* continuous ``assign lhs = rhs;``
* ``always`` / ``always_ff`` / ``always_comb`` blocks with sensitivity lists,
  ``begin/end`` bodies, blocking (``=``) and nonblocking (``<=``) assignments
* basic module instances ``Mod #(...) inst (.a(x), .b(y));`` and positional

NOT supported (each occurrence recorded as an UnresolvedConstruct so it is
visible in the manifest): generate blocks, functions/tasks, structs/unions,
interfaces, packages, casez/casex bodies (kept as opaque), typedefs, macros
beyond passthrough, SVA, and any construct the recognizer cannot classify.

The parser is deterministic and never guesses semantics. When it cannot make
sense of a region it records an ``UnresolvedConstruct`` and resynchronizes to
the next statement boundary.
"""

from __future__ import annotations

from ..lexer import Token, TokKind, tokenize
from ..models import (
    Assignment,
    ContinuousAssign,
    Instance,
    Module,
    Net,
    NetKind,
    Parameter,
    ParserInfo,
    Port,
    PortConnection,
    PortDirection,
    Procedure,
    ProcedureKind,
    Range,
    SensitivityEntry,
    SourceLocation,
    UnresolvedConstruct,
)
from .base import ParserAdapter, ParseResult

SUPPORTED = [
    "module/endmodule",
    "ANSI and non-ANSI port lists",
    "parameter/localparam",
    "input/output/inout ports with width",
    "wire/reg/logic declarations",
    "continuous assign",
    "always/always_ff/always_comb blocks",
    "blocking and nonblocking assignments",
    "basic module instances (named and positional)",
]

UNSUPPORTED = [
    "generate/for-generate blocks",
    "functions and tasks",
    "structs/unions/enums/typedefs",
    "interfaces/modports/packages",
    "SystemVerilog assertions (SVA)",
    "preprocessor macros beyond raw passthrough",
    "case/casez/casex statement bodies (recorded, body not modeled)",
    "hierarchical/dotted assignment targets",
    "parameter expression evaluation (ranges kept as text)",
]

# Keywords that can only begin a module-level construct; used to bound a
# begin-less always body so we never run past the block.
_MODULE_LEVEL_KEYWORDS = {
    "always",
    "always_ff",
    "always_comb",
    "always_latch",
    "assign",
    "endmodule",
    "module",
    "initial",
    "generate",
    "function",
    "task",
}

_NET_KEYWORDS = {"wire": NetKind.WIRE, "reg": NetKind.REG, "logic": NetKind.LOGIC}
_DIR_KEYWORDS = {
    "input": PortDirection.INPUT,
    "output": PortDirection.OUTPUT,
    "inout": PortDirection.INOUT,
}
# Verilog keywords that can begin a statement inside a module body but are NOT
# instance module names.
_STMT_KEYWORDS = {
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
    "parameter",
    "localparam",
    "initial",
    "generate",
    "endgenerate",
    "function",
    "task",
    "genvar",
    "integer",
    "typedef",
    "case",
    "casez",
    "casex",
    "if",
    "else",
    "for",
    "begin",
    "end",
}


class _Cursor:
    """Token cursor with small lookahead helpers."""

    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.pos = 0

    def peek(self, off: int = 0) -> Token:
        idx = self.pos + off
        if idx >= len(self.toks):
            return self.toks[-1]
        return self.toks[idx]

    def next(self) -> Token:
        t = self.peek()
        if self.pos < len(self.toks) - 1:
            self.pos += 1
        return t

    def at_end(self) -> bool:
        return self.peek().kind == TokKind.EOF

    def is_text(self, text: str, off: int = 0) -> bool:
        return self.peek(off).text == text

    def is_punct(self, text: str, off: int = 0) -> bool:
        t = self.peek(off)
        return t.kind == TokKind.PUNCT and t.text == text


def _loc(filename: str, start: Token, end: Token) -> SourceLocation:
    return SourceLocation(
        file=filename,
        line=start.line,
        col=start.col,
        end_line=end.end_line,
        end_col=max(end.end_col, start.col),
    )


class BuiltinVerilogAdapter(ParserAdapter):
    name = "builtin"
    version = "0.1.0"

    def info(self) -> ParserInfo:
        return ParserInfo(
            adapter=self.name,
            adapter_version=self.version,
            supported_constructs=list(SUPPORTED),
            unsupported_constructs=list(UNSUPPORTED),
        )

    def parse_text(self, text: str, *, filename: str) -> ParseResult:
        cur = _Cursor(tokenize(text, filename=filename))
        result = ParseResult()
        while not cur.at_end():
            if cur.is_text("module"):
                self._parse_module(cur, filename, result)
            else:
                # Skip stray tokens (e.g. `timescale, top-level typedefs) but
                # record non-trivial ones so nothing is silently dropped.
                t = cur.next()
                if t.text in {"`", "typedef", "package", "interface"}:
                    result.unresolved.append(
                        UnresolvedConstruct(
                            kind="top_level_construct",
                            detail=f"unsupported top-level token near '{t.text}'",
                            location=_loc(filename, t, t),
                        )
                    )
                    self._skip_to_semicolon_or_end(cur)
        return result

    # -- module ----------------------------------------------------------------

    def _parse_module(self, cur: _Cursor, filename: str, result: ParseResult) -> None:
        start = cur.next()  # 'module'
        name_tok = cur.next()
        if name_tok.kind != TokKind.IDENT:
            result.unresolved.append(
                UnresolvedConstruct(
                    kind="module_header",
                    detail="module keyword not followed by a name",
                    location=_loc(filename, start, name_tok),
                )
            )
            self._skip_to_text(cur, "endmodule")
            return

        module = Module(name=name_tok.text, location=_loc(filename, start, name_tok))

        # Optional parameter port list: #( ... )
        if cur.is_punct("#"):
            cur.next()
            if cur.is_punct("("):
                self._parse_param_list(cur, filename, module)

        # Optional ANSI/non-ANSI port list: ( ... )
        ansi_ports: dict[str, Port] = {}
        if cur.is_punct("("):
            ansi_ports = self._parse_port_list(cur, filename, module, result)

        # ';' ending the header
        if cur.is_punct(";"):
            cur.next()

        # Body until endmodule.
        self._parse_module_body(cur, filename, module, result, ansi_ports)

        # Ensure we consumed endmodule.
        if cur.is_text("endmodule"):
            cur.next()

        self._finalize_module(module)
        result.modules.append(module)

    def _parse_param_list(
        self, cur: _Cursor, filename: str, module: Module
    ) -> None:
        cur.next()  # '('
        depth = 1
        while not cur.at_end() and depth > 0:
            if cur.is_punct("("):
                depth += 1
                cur.next()
                continue
            if cur.is_punct(")"):
                depth -= 1
                cur.next()
                continue
            if cur.is_text("parameter") or cur.is_text("localparam"):
                self._parse_parameter_decl(cur, filename, module, inline=True)
                continue
            # A bare `NAME = default` inside #( ) is a parameter too.
            if cur.peek().kind == TokKind.IDENT and cur.is_punct("=", 1):
                self._consume_param_assignment(cur, filename, module, is_local=False)
                continue
            cur.next()

    def _parse_parameter_decl(
        self, cur: _Cursor, filename: str, module: Module, *, inline: bool
    ) -> None:
        kw = cur.next()  # parameter/localparam
        is_local = kw.text == "localparam"
        # Skip optional type/range tokens up to the first identifier '=' pair.
        # Collect one or more NAME = value entries separated by commas.
        while not cur.at_end():
            # skip a leading range [ .. ] or type keyword
            if cur.is_punct("["):
                self._skip_bracketed(cur)
                continue
            if cur.peek().kind == TokKind.IDENT and cur.is_punct("=", 1):
                self._consume_param_assignment(
                    cur, filename, module, is_local=is_local, kw=kw
                )
                if cur.is_punct(","):
                    cur.next()
                    continue
                break
            if cur.peek().kind == TokKind.IDENT and (
                cur.is_punct(",", 1) or cur.is_punct(";", 1) or cur.is_punct(")", 1)
            ):
                nm = cur.next()
                module.parameters.append(
                    Parameter(
                        name=nm.text,
                        default=None,
                        is_localparam=is_local,
                        location=_loc(filename, kw, nm),
                    )
                )
                if cur.is_punct(","):
                    cur.next()
                    continue
                break
            # a type keyword like 'integer' or 'logic' - skip it
            if cur.peek().kind == TokKind.IDENT:
                cur.next()
                continue
            break
        if not inline and cur.is_punct(";"):
            cur.next()

    def _consume_param_assignment(
        self,
        cur: _Cursor,
        filename: str,
        module: Module,
        *,
        is_local: bool,
        kw: Token | None = None,
    ) -> None:
        name_tok = cur.next()
        cur.next()  # '='
        value_toks = self._collect_expr(cur, stop={",", ")", ";"})
        default = _join(value_toks)
        end = value_toks[-1] if value_toks else name_tok
        start = kw if kw is not None else name_tok
        module.parameters.append(
            Parameter(
                name=name_tok.text,
                default=default or None,
                is_localparam=is_local,
                location=_loc(filename, start, end),
            )
        )

    def _parse_port_list(
        self,
        cur: _Cursor,
        filename: str,
        module: Module,
        result: ParseResult,
    ) -> dict[str, Port]:
        """Parse ``( ... )`` after the module name.

        Returns a dict of ANSI ports declared here (name -> Port). Non-ANSI port
        lists (bare identifiers) are resolved later from body declarations.
        """
        cur.next()  # '('
        ansi: dict[str, Port] = {}
        pending_nonansi: list[Token] = []
        # Track "sticky" direction/kind/range across comma-separated ANSI ports.
        cur_dir: PortDirection | None = None
        cur_kind: NetKind | None = None
        cur_range: Range | None = None

        while not cur.at_end() and not cur.is_punct(")"):
            t = cur.peek()
            if t.text in _DIR_KEYWORDS:
                cur.next()
                cur_dir = _DIR_KEYWORDS[t.text]
                cur_kind = None
                cur_range = None
                # optional net kind
                if cur.peek().text in _NET_KEYWORDS:
                    cur_kind = _NET_KEYWORDS[cur.next().text]
                # optional 'signed'
                if cur.is_text("signed"):
                    cur.next()
                # optional range
                if cur.is_punct("["):
                    cur_range = self._parse_range(cur)
                # the port name
                if cur.peek().kind == TokKind.IDENT:
                    nm = cur.next()
                    ansi[nm.text] = Port(
                        name=nm.text,
                        direction=cur_dir,
                        net_kind=cur_kind,
                        range=cur_range,
                        location=_loc(filename, t, nm),
                    )
                if cur.is_punct(","):
                    cur.next()
                continue

            if t.kind == TokKind.IDENT and cur_dir is not None:
                # Continuation of a sticky ANSI declaration: `input a, b, c`
                nm = cur.next()
                ansi[nm.text] = Port(
                    name=nm.text,
                    direction=cur_dir,
                    net_kind=cur_kind,
                    range=cur_range,
                    location=_loc(filename, nm, nm),
                )
                if cur.is_punct(","):
                    cur.next()
                continue

            if t.kind == TokKind.IDENT:
                # Non-ANSI: just a name; direction comes from the body.
                pending_nonansi.append(cur.next())
                if cur.is_punct(","):
                    cur.next()
                continue

            # Unexpected token in the port list.
            cur.next()

        if cur.is_punct(")"):
            cur.next()

        # Stash non-ANSI names on the module so the body pass can attach dirs.
        module.__dict__.setdefault("_nonansi_ports", [])
        for tok in pending_nonansi:
            module.__dict__["_nonansi_ports"].append((tok.text, _loc(filename, tok, tok)))

        for p in ansi.values():
            module.ports.append(p)
        return ansi

    def _parse_range(self, cur: _Cursor) -> Range:
        cur.next()  # '['
        msb_toks = self._collect_expr(cur, stop={":", "]"})
        lsb_toks: list[Token] = []
        if cur.is_punct(":"):
            cur.next()
            lsb_toks = self._collect_expr(cur, stop={"]"})
        if cur.is_punct("]"):
            cur.next()
        msb = _join(msb_toks)
        lsb = _join(lsb_toks) if lsb_toks else msb
        return Range(msb=msb, lsb=lsb)

    # -- module body -----------------------------------------------------------

    def _parse_module_body(
        self,
        cur: _Cursor,
        filename: str,
        module: Module,
        result: ParseResult,
        ansi_ports: dict[str, Port],
    ) -> None:
        proc_index = 0
        while not cur.at_end() and not cur.is_text("endmodule"):
            t = cur.peek()
            text = t.text

            if text in _DIR_KEYWORDS:
                self._parse_port_decl(cur, filename, module, ansi_ports)
                continue
            if text in _NET_KEYWORDS:
                self._parse_net_decl(cur, filename, module)
                continue
            if text in ("parameter", "localparam"):
                self._parse_parameter_decl(cur, filename, module, inline=False)
                continue
            if text == "assign":
                self._parse_continuous_assign(cur, filename, module)
                continue
            if text in ("always", "always_ff", "always_comb", "always_latch"):
                self._parse_always(cur, filename, module, proc_index, result)
                proc_index += 1
                continue
            if text in ("generate", "function", "task", "initial", "case", "casez",
                        "casex", "typedef", "genvar", "integer"):
                self._record_unsupported_block(cur, filename, result, text)
                continue

            # Instance? IDENT [#(...)] IDENT ( ... ) ;
            if t.kind == TokKind.IDENT and text not in _STMT_KEYWORDS:
                if self._try_parse_instance(cur, filename, module, result):
                    continue

            # Unknown statement: record and resync.
            self._record_unknown_stmt(cur, filename, result)

    def _parse_port_decl(
        self,
        cur: _Cursor,
        filename: str,
        module: Module,
        ansi_ports: dict[str, Port],
    ) -> None:
        dir_tok = cur.next()
        direction = _DIR_KEYWORDS[dir_tok.text]
        net_kind: NetKind | None = None
        if cur.peek().text in _NET_KEYWORDS:
            net_kind = _NET_KEYWORDS[cur.next().text]
        if cur.is_text("signed"):
            cur.next()
        rng: Range | None = None
        if cur.is_punct("["):
            rng = self._parse_range(cur)
        # one or more names
        while cur.peek().kind == TokKind.IDENT:
            nm = cur.next()
            existing = next((p for p in module.ports if p.name == nm.text), None)
            if existing is None:
                module.ports.append(
                    Port(
                        name=nm.text,
                        direction=direction,
                        net_kind=net_kind,
                        range=rng,
                        location=_loc(filename, dir_tok, nm),
                    )
                )
            else:
                # Non-ANSI: header listed name, body gives direction/width.
                existing.direction = direction
                if net_kind is not None:
                    existing.net_kind = net_kind
                if rng is not None:
                    existing.range = rng
            if cur.is_punct(","):
                cur.next()
                continue
            break
        if cur.is_punct(";"):
            cur.next()

    def _parse_net_decl(
        self, cur: _Cursor, filename: str, module: Module
    ) -> None:
        kw = cur.next()
        net_kind = _NET_KEYWORDS[kw.text]
        if cur.is_text("signed"):
            cur.next()
        rng: Range | None = None
        if cur.is_punct("["):
            rng = self._parse_range(cur)
        while cur.peek().kind == TokKind.IDENT:
            nm = cur.next()
            # A reg/logic decl may also be a port already declared - if so,
            # just refine the port's net_kind rather than adding a net.
            port = next((p for p in module.ports if p.name == nm.text), None)
            if port is not None:
                if port.net_kind is None:
                    port.net_kind = net_kind
                if port.range is None and rng is not None:
                    port.range = rng
            else:
                # Optional unpacked dimension after the name => memory array.
                unpacked: Range | None = None
                if cur.is_punct("["):
                    unpacked = self._parse_range(cur)
                module.nets.append(
                    Net(
                        name=nm.text,
                        net_kind=net_kind,
                        range=rng,
                        unpacked_range=unpacked,
                        is_memory=unpacked is not None,
                        location=_loc(filename, kw, nm),
                    )
                )
            # skip an optional initializer '= expr'
            if cur.is_punct("="):
                cur.next()
                self._collect_expr(cur, stop={",", ";"})
            if cur.is_punct(","):
                cur.next()
                continue
            break
        if cur.is_punct(";"):
            cur.next()

    def _parse_continuous_assign(
        self, cur: _Cursor, filename: str, module: Module
    ) -> None:
        kw = cur.next()  # assign
        while not cur.at_end() and not cur.is_punct(";"):
            lhs_toks = self._collect_expr(cur, stop={"="})
            if cur.is_punct("="):
                cur.next()
            rhs_toks = self._collect_expr(cur, stop={",", ";"})
            lhs = _join(lhs_toks)
            rhs = _join(rhs_toks)
            end = rhs_toks[-1] if rhs_toks else kw
            if lhs:
                module.continuous_assigns.append(
                    ContinuousAssign(
                        lhs=lhs, rhs=rhs, location=_loc(filename, kw, end)
                    )
                )
            if cur.is_punct(","):
                cur.next()
                continue
            break
        if cur.is_punct(";"):
            cur.next()

    def _parse_always(
        self,
        cur: _Cursor,
        filename: str,
        module: Module,
        index: int,
        result: ParseResult,
    ) -> None:
        kw = cur.next()  # always / always_ff / always_comb
        sensitivity: list[SensitivityEntry] = []
        star = False
        explicit_comb = kw.text == "always_comb"
        explicit_ff = kw.text == "always_ff"

        # Sensitivity list @(...) or @*
        if cur.is_punct("@"):
            cur.next()
            if cur.is_punct("*"):
                cur.next()
                star = True
            elif cur.is_punct("("):
                cur.next()
                if cur.is_punct("*"):
                    star = True
                    cur.next()
                else:
                    sensitivity = self._parse_sensitivity(cur)
                if cur.is_punct(")"):
                    cur.next()
        # Body.
        conditions: list[str] = []
        assignments, body_end = self._parse_always_body(
            cur, filename, result, conditions
        )

        has_edge = any(s.edge for s in sensitivity)
        if explicit_ff or has_edge:
            kind = ProcedureKind.ALWAYS_FF
        elif explicit_comb or star or (sensitivity and not has_edge):
            kind = ProcedureKind.ALWAYS_COMB
        else:
            kind = ProcedureKind.ALWAYS

        targets: list[str] = []
        for a in assignments:
            base = _base_signal(a.lhs)
            if base and base not in targets:
                targets.append(base)

        # Deduplicate condition signals, preserving first-seen order.
        seen: set[str] = set()
        cond_signals: list[str] = []
        for c in conditions:
            if c not in seen:
                seen.add(c)
                cond_signals.append(c)

        proc = Procedure(
            index=index,
            kind=kind,
            sensitivity=sensitivity,
            is_star_sensitivity=star,
            assignment_targets=targets,
            assignments=assignments,
            condition_signals=cond_signals,
            location=_loc(filename, kw, body_end),
        )
        module.procedures.append(proc)

    def _parse_sensitivity(self, cur: _Cursor) -> list[SensitivityEntry]:
        entries: list[SensitivityEntry] = []
        while not cur.at_end() and not cur.is_punct(")"):
            edge = None
            if cur.is_text("posedge") or cur.is_text("negedge"):
                edge = cur.next().text
            if cur.peek().kind == TokKind.IDENT:
                sig = cur.next().text
                entries.append(SensitivityEntry(signal=sig, edge=edge))
            # separators: 'or' or ','
            if cur.is_text("or"):
                cur.next()
            elif cur.is_punct(","):
                cur.next()
            elif not cur.is_punct(")"):
                cur.next()  # skip anything unexpected
        return entries

    def _parse_always_body(
        self,
        cur: _Cursor,
        filename: str,
        result: ParseResult,
        conditions: list[str],
    ) -> tuple[list[Assignment], Token]:
        """Parse an always body, collecting assignments at any nesting depth.

        Handles begin/end and if/else/for nesting by tracking begin depth and
        scanning for ``lhs = expr`` / ``lhs <= expr`` statements. Conditions and
        control-flow are not modeled structurally (recorded as understood but not
        represented), but every assignment target is captured.
        """
        assignments: list[Assignment] = []
        last = cur.peek()

        if cur.is_text("begin"):
            begin_tok = cur.next()
            last = begin_tok
            depth = 1
            while not cur.at_end() and depth > 0:
                if cur.is_text("begin"):
                    depth += 1
                    last = cur.next()
                    continue
                if cur.is_text("end"):
                    depth -= 1
                    last = cur.next()
                    continue
                stmt_end = self._scan_body_statement(
                    cur, filename, assignments, conditions
                )
                if stmt_end is not None:
                    last = stmt_end
        else:
            # No begin/end: the body is a single (possibly compound if/else)
            # statement, e.g. ``if (rst) q <= 0; else q <= 1;``. Scan the
            # if/else chain: a control-flow header, then its (single) guarded
            # statement, repeating while `else` continues the chain.
            while not cur.at_end():
                t = cur.peek()
                if t.text in _MODULE_LEVEL_KEYWORDS or cur.is_text("endmodule"):
                    break
                stmt_end = self._scan_body_statement(
                    cur, filename, assignments, conditions
                )
                if stmt_end is not None:
                    last = stmt_end
                # Continue only when an `else` keeps the chain going, or the
                # statement we just scanned was a control-flow header (so its
                # guarded statement follows next).
                if cur.is_text("else"):
                    continue
                if t.text in ("if", "else", "for", "while", "case"):
                    continue
                break
        return assignments, last

    def _scan_body_statement(
        self,
        cur: _Cursor,
        filename: str,
        assignments: list[Assignment],
        conditions: list[str],
    ) -> Token | None:
        """Consume one statement inside an always body.

        Recognizes assignments; skips control-flow keywords but records the
        identifiers appearing in their conditions so downstream heuristics can
        see e.g. a synchronous reset referenced only in ``if (rst)``.
        """
        t = cur.peek()

        # Control-flow keywords: consume keyword + any parenthesized condition.
        if t.text in ("if", "else", "for", "while", "case", "casez", "casex", "repeat"):
            cur.next()
            if cur.is_punct("("):
                cond_toks = self._capture_parens(cur)
                for ct in cond_toks:
                    if ct.kind == TokKind.IDENT and not _is_verilog_keyword(ct.text):
                        conditions.append(ct.text)
            # 'else' / 'begin' handled by outer loop; nothing else to do.
            return t
        if t.text in ("endcase", "default", ":"):
            cur.next()
            return t

        # Potential assignment: collect an lhs up to '=' or '<='.
        start = t
        lhs_toks: list[Token] = []
        # Guard: don't run past a ';' or 'end'.
        while (
            not cur.at_end()
            and not cur.is_punct(";")
            and not cur.is_text("end")
            and not cur.is_punct("=")
            and not (cur.peek().kind == TokKind.PUNCT and cur.peek().text == "<=")
        ):
            # If we hit a 'begin' or control keyword, this isn't an assignment.
            if cur.peek().text in ("begin", "if", "else", "for", "case"):
                break
            lhs_toks.append(cur.next())

        if cur.is_punct("=") or (cur.peek().kind == TokKind.PUNCT and cur.peek().text == "<="):
            op = cur.next()
            nonblocking = op.text == "<="
            rhs_toks = self._collect_expr(cur, stop={";"})
            end = rhs_toks[-1] if rhs_toks else op
            lhs = _join(lhs_toks)
            rhs = _join(rhs_toks)
            if lhs:
                assignments.append(
                    Assignment(
                        lhs=lhs,
                        rhs=rhs,
                        nonblocking=nonblocking,
                        location=_loc(filename, start, end),
                    )
                )
            if cur.is_punct(";"):
                cur.next()
            return end

        # Not an assignment - consume up to ';' to make progress.
        if cur.is_punct(";"):
            return cur.next()
        if lhs_toks:
            return lhs_toks[-1]
        return cur.next()

    def _try_parse_instance(
        self,
        cur: _Cursor,
        filename: str,
        module: Module,
        result: ParseResult,
    ) -> bool:
        """Attempt ``ModName [#(...)] instName ( ... ) ;``.

        Returns True if it consumed an instance. Uses a save/restore so a failed
        attempt does not corrupt the cursor.
        """
        save = cur.pos
        mod_tok = cur.next()  # module name
        # optional parameter override #( ... )
        if cur.is_punct("#"):
            cur.next()
            if cur.is_punct("("):
                self._skip_parens(cur)
        # instance name
        if cur.peek().kind != TokKind.IDENT:
            cur.pos = save
            return False
        inst_tok = cur.next()
        # optional instance array range [ ... ]
        if cur.is_punct("["):
            self._skip_bracketed(cur)
        if not cur.is_punct("("):
            cur.pos = save
            return False

        connections = self._parse_connections(cur, filename)
        if cur.is_punct(";"):
            cur.next()
        module.instances.append(
            Instance(
                module=mod_tok.text,
                name=inst_tok.text,
                connections=connections,
                location=_loc(filename, mod_tok, inst_tok),
            )
        )
        return True

    def _parse_connections(
        self, cur: _Cursor, filename: str
    ) -> list[PortConnection]:
        cur.next()  # '('
        conns: list[PortConnection] = []
        while not cur.at_end() and not cur.is_punct(")"):
            if cur.is_punct("."):
                dot = cur.next()
                formal = cur.next().text if cur.peek().kind == TokKind.IDENT else ""
                actual = ""
                if cur.is_punct("("):
                    cur.next()
                    actual_toks = self._collect_expr(cur, stop={")"})
                    actual = _join(actual_toks)
                    if cur.is_punct(")"):
                        cur.next()
                conns.append(
                    PortConnection(
                        formal=formal or None,
                        actual=actual,
                        location=_loc(filename, dot, dot),
                    )
                )
            else:
                start = cur.peek()
                actual_toks = self._collect_expr(cur, stop={",", ")"})
                actual = _join(actual_toks)
                if actual:
                    conns.append(
                        PortConnection(
                            formal=None,
                            actual=actual,
                            location=_loc(
                                filename, start, actual_toks[-1] if actual_toks else start
                            ),
                        )
                    )
            if cur.is_punct(","):
                cur.next()
        if cur.is_punct(")"):
            cur.next()
        return conns

    # -- unsupported / recovery ------------------------------------------------

    def _record_unsupported_block(
        self, cur: _Cursor, filename: str, result: ParseResult, kind: str
    ) -> None:
        start = cur.next()
        # Best-effort skip to a matching end keyword or ';'.
        enders = {
            "generate": "endgenerate",
            "function": "endfunction",
            "task": "endtask",
            "case": "endcase",
            "casez": "endcase",
            "casex": "endcase",
        }
        result.unresolved.append(
            UnresolvedConstruct(
                kind="unsupported_construct",
                detail=f"'{kind}' block is not modeled in v0.1",
                location=_loc(filename, start, start),
            )
        )
        ender = enders.get(kind)
        if ender:
            self._skip_to_text(cur, ender)
            if cur.is_text(ender):
                cur.next()
        else:
            self._skip_to_semicolon_or_end(cur)

    def _record_unknown_stmt(
        self, cur: _Cursor, filename: str, result: ParseResult
    ) -> None:
        start = cur.peek()
        end = self._skip_to_semicolon_or_end(cur)
        result.unresolved.append(
            UnresolvedConstruct(
                kind="unrecognized_statement",
                detail=f"could not classify statement beginning with '{start.text}'",
                location=_loc(filename, start, end),
            )
        )

    # -- token helpers ---------------------------------------------------------

    def _collect_expr(self, cur: _Cursor, stop: set[str]) -> list[Token]:
        """Collect tokens for an expression until a top-level stop punct.

        Tracks (), [], {} nesting so commas/semicolons inside them do not stop
        collection prematurely.
        """
        toks: list[Token] = []
        depth = 0
        while not cur.at_end():
            t = cur.peek()
            if t.kind == TokKind.PUNCT:
                if t.text in "([{":
                    depth += 1
                elif t.text in ")]}":
                    if depth == 0 and t.text in stop:
                        break
                    depth -= 1
                    if depth < 0:
                        break
                elif depth == 0 and t.text in stop:
                    break
            toks.append(cur.next())
        return toks

    def _skip_parens(self, cur: _Cursor) -> None:
        if not cur.is_punct("("):
            return
        cur.next()
        depth = 1
        while not cur.at_end() and depth > 0:
            if cur.is_punct("("):
                depth += 1
            elif cur.is_punct(")"):
                depth -= 1
            cur.next()

    def _capture_parens(self, cur: _Cursor) -> list[Token]:
        """Consume a balanced ``( ... )`` and return the inner tokens."""
        inner: list[Token] = []
        if not cur.is_punct("("):
            return inner
        cur.next()
        depth = 1
        while not cur.at_end() and depth > 0:
            if cur.is_punct("("):
                depth += 1
                inner.append(cur.next())
                continue
            if cur.is_punct(")"):
                depth -= 1
                tok = cur.next()
                if depth > 0:
                    inner.append(tok)
                continue
            inner.append(cur.next())
        return inner

    def _skip_bracketed(self, cur: _Cursor) -> None:
        if not cur.is_punct("["):
            return
        cur.next()
        depth = 1
        while not cur.at_end() and depth > 0:
            if cur.is_punct("["):
                depth += 1
            elif cur.is_punct("]"):
                depth -= 1
            cur.next()

    def _skip_to_semicolon_or_end(self, cur: _Cursor) -> Token:
        last = cur.peek()
        while not cur.at_end():
            if cur.is_punct(";"):
                last = cur.next()
                break
            if cur.is_text("endmodule"):
                break
            last = cur.next()
        return last

    def _skip_to_text(self, cur: _Cursor, text: str) -> None:
        while not cur.at_end() and not cur.is_text(text):
            cur.next()

    # -- finalize --------------------------------------------------------------

    def _finalize_module(self, module: Module) -> None:
        from ..models import ProcedureSummary, Register

        # Attach non-ANSI ports that never got a direction (rare / malformed):
        nonansi = module.__dict__.pop("_nonansi_ports", [])
        known = {p.name for p in module.ports}
        for name, loc in nonansi:
            if name not in known:
                module.ports.append(
                    Port(
                        name=name,
                        direction=PortDirection.INPUT,  # conservative default
                        location=loc,
                    )
                )

        # Registers = nonblocking targets under an always_ff.
        registers: dict[str, Register] = {}
        for proc in module.procedures:
            if proc.kind != ProcedureKind.ALWAYS_FF:
                continue
            for a in proc.assignments:
                if not a.nonblocking:
                    continue
                base = _base_signal(a.lhs)
                if base and base not in registers:
                    registers[base] = Register(
                        name=base,
                        driven_in_procedure_index=proc.index,
                        location=a.location,
                    )
        module.registers = list(registers.values())

        # Procedure summary.
        summary = ProcedureSummary()
        for proc in module.procedures:
            if proc.kind == ProcedureKind.ALWAYS_FF:
                summary.always_ff += 1
            elif proc.kind == ProcedureKind.ALWAYS_COMB:
                summary.always_comb += 1
            else:
                summary.always_other += 1
        summary.continuous_assigns = len(module.continuous_assigns)
        module.procedure_summary = summary


def _join(tokens: list[Token]) -> str:
    """Join tokens back into a compact, deterministic expression string."""
    out: list[str] = []
    for idx, t in enumerate(tokens):
        if idx == 0:
            out.append(t.text)
            continue
        prev = tokens[idx - 1]
        # No space before/after these; keep the string tight and stable.
        no_space_after = prev.text in "([{.~!"
        no_space_before = t.text in ")]},;."
        if no_space_after or no_space_before:
            out.append(t.text)
        elif t.text in "([" and prev.kind == TokKind.IDENT:
            out.append(t.text)  # indexing / call: foo[ , foo(
        else:
            out.append(" " + t.text)
    return "".join(out).strip()


_VERILOG_KEYWORDS = frozenset(
    {
        "if", "else", "for", "while", "case", "casez", "casex", "begin", "end",
        "posedge", "negedge", "or", "and", "not", "default", "repeat",
    }
)


def _is_verilog_keyword(text: str) -> bool:
    return text in _VERILOG_KEYWORDS


def _base_signal(lhs: str) -> str:
    """Extract the base signal name from an lhs like ``q[3:0]`` or ``mem[i]``."""
    lhs = lhs.strip()
    for sep in ("[", ".", " "):
        idx = lhs.find(sep)
        if idx > 0:
            lhs = lhs[:idx]
    return lhs.strip()
