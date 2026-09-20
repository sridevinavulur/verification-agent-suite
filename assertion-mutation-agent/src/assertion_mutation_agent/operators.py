"""Real source-mutation operators for a constrained Verilog subset.

Each operator scans the tokenized RTL, finds syntactically safe mutation
points, and produces :class:`~assertion_mutation_agent.models.Mutant` objects
with an *exact* source diff and stable ID. Mutations are applied as textual
splices (single-token / small-span replacements), which keeps mutants
"compilable-looking": the surrounding structure is untouched.

Design notes / soundness:
- These are structural, best-effort transforms on a *subset*. They do not
  attempt full Verilog semantics. Where a transform cannot be applied safely
  (e.g. width truncation of a bare identifier with unknown width), the operator
  simply does not emit a mutant rather than emit an invalid one.
- "mutated_signals" records the identifiers touched so a downstream executor
  (real or mock) can reason about which properties could observe the defect.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from .lexer import Token, code_tokens, tokenize
from .models import Mutant, MutationOperator, SourceDiff, SourceLocation

# Relational / equality operators and their "flipped" counterpart.
_RELATIONAL_FLIP = {
    "<": ">",
    ">": "<",
    "<=": ">=",  # NOTE: see guard below — only in expression context
    ">=": "<=",
    "==": "!=",
    "!=": "==",
    "===": "!==",
    "!==": "===",
}

_KEYWORDS = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg", "logic",
    "always", "always_ff", "always_comb", "assign", "begin", "end", "if",
    "else", "posedge", "negedge", "or", "and", "not", "case", "endcase",
    "default", "parameter", "localparam", "initial", "for", "integer",
}


def _line_text(source: str, line: int) -> str:
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1]
    return ""


def _apply_span(source: str, start: int, end: int, replacement: str) -> str:
    return source[:start] + replacement + source[end:]


def _mutated_line(source: str, start: int, end: int, replacement: str, line: int) -> str:
    mutated_full = _apply_span(source, start, end, replacement)
    return _line_text(mutated_full, line)


def _build_mutant(
    module: str,
    source: str,
    operator: MutationOperator,
    tok: Token,
    replacement: str,
    description: str,
    signals: list[str],
    *,
    span_end: int | None = None,
    original_text: str | None = None,
) -> Mutant:
    """Construct a Mutant that replaces [tok.start, span_end) with ``replacement``."""
    end = tok.end if span_end is None else span_end
    orig = tok.value if original_text is None else original_text
    mutated_source = _apply_span(source, tok.start, end, replacement)
    loc = SourceLocation(
        file=module,
        line=tok.line,
        col_start=tok.col,
        col_end=tok.col + (end - tok.start) - 1,
    )
    diff = SourceDiff(
        location=loc,
        original_text=orig,
        mutated_text=replacement,
        original_line=_line_text(source, tok.line),
        mutated_line=_mutated_line(source, tok.start, end, replacement, tok.line),
    )
    mutant_id = Mutant.make_id(module, operator, tok.line, tok.col, orig, replacement)
    return Mutant(
        mutant_id=mutant_id,
        operator=operator,
        description=description,
        diff=diff,
        mutated_signals=sorted(set(signals)),
        mutated_source=mutated_source,
    )


def _nearest_lhs_signal(code: list[Token], idx: int) -> str | None:
    """Walk left from index ``idx`` to find the assignment LHS identifier.

    Looks for the first identifier that precedes a '=' or '<=' at statement
    scope. Best-effort: returns the identifier immediately before the nearest
    preceding assignment operator, else None.
    """
    j = idx
    while j >= 0:
        t = code[j]
        if t.kind == "op" and t.value in ("=", "<="):
            # identifier just before this op (skip index selects)
            k = j - 1
            depth = 0
            while k >= 0:
                tk = code[k]
                if tk.kind == "op" and tk.value == "]":
                    depth += 1
                elif tk.kind == "op" and tk.value == "[":
                    depth -= 1
                elif tk.kind == "ident" and depth <= 0:
                    return tk.value
                k -= 1
            return None
        if t.kind == "op" and t.value == ";":
            return None
        j -= 1
    return None


def _rhs_signals(code: list[Token], idx: int) -> list[str]:
    """Collect identifiers to the right of index ``idx`` up to the statement end."""
    sigs: list[str] = []
    j = idx + 1
    while j < len(code):
        t = code[j]
        if t.kind == "op" and t.value in (";", ")"):
            break
        if t.kind == "ident" and t.value not in _KEYWORDS:
            sigs.append(t.value)
        j += 1
    return sigs


def _stmt_signals(code: list[Token], idx: int) -> list[str]:
    """Identifiers on both sides of the statement containing token index idx."""
    lhs = _nearest_lhs_signal(code, idx)
    sigs = _rhs_signals(code, idx)
    if lhs:
        sigs.append(lhs)
    return sigs


# --------------------------------------------------------------------------- #
# Operators                                                                    #
# --------------------------------------------------------------------------- #


def op_relational_flip(module: str, source: str) -> Iterator[Mutant]:
    toks = tokenize(source)
    code = code_tokens(toks)
    for i, t in enumerate(code):
        if t.kind != "op" or t.value not in _RELATIONAL_FLIP:
            continue
        # Guard: '<=' can be a nonblocking assignment. Treat as relational only
        # when it is NOT the first operator following an LHS at statement start.
        if t.value == "<=" and _is_nonblocking_assign(code, i):
            continue
        flipped = _RELATIONAL_FLIP[t.value]
        signals = _stmt_signals(code, i)
        yield _build_mutant(
            module, source, MutationOperator.RELATIONAL_FLIP, t, flipped,
            f"Flip relational operator '{t.value}' -> '{flipped}'", signals,
        )


def _is_nonblocking_assign(code: list[Token], idx: int) -> bool:
    """Heuristic: is the '<=' at ``idx`` a nonblocking assignment (not relational)?

    A nonblocking assign has an LHS target immediately to its left: a plain
    identifier possibly followed by index/part selects (``a[3]``, ``a[3:0]``),
    and *before* that LHS chain there is a statement boundary (start of stream,
    ';', or a 'begin'/'end'/'else' keyword). If instead the '<=' is embedded in
    an expression (preceded by another operator, number, or ')'), it is
    relational.
    """
    if idx == 0:
        return True
    prev = code[idx - 1]
    if not (prev.kind == "ident" or (prev.kind == "op" and prev.value == "]")):
        # e.g. `(count + 1) <= x` or `3 <= x` -> relational context.
        return False

    # Walk left across the LHS chain (ident and [...] selects only).
    j = idx - 1
    depth = 0
    while j >= 0:
        tk = code[j]
        if tk.kind == "op" and tk.value == "]":
            depth += 1
            j -= 1
            continue
        if tk.kind == "op" and tk.value == "[":
            depth -= 1
            j -= 1
            continue
        if depth > 0:
            j -= 1
            continue
        # depth == 0 here: this is the token that ends the LHS chain.
        if tk.kind == "ident" and tk.value not in _KEYWORDS:
            j -= 1
            continue
        # Reached the boundary token before the LHS.
        if tk.kind == "op" and tk.value == ";":
            return True
        if tk.kind == "ident" and tk.value in ("begin", "end", "else"):
            return True
        if tk.kind == "op" and tk.value in (")",):
            # e.g. `if (cond) count <= ...` — ')' closes the if-condition.
            return True
        return False
    return True


def op_boolean_negation(module: str, source: str) -> Iterator[Mutant]:
    """Negate the condition of an ``if (...)`` by wrapping it in ``!( ... )``."""
    toks = tokenize(source)
    code = code_tokens(toks)
    for i, t in enumerate(code):
        if not (t.kind == "ident" and t.value == "if"):
            continue
        if i + 1 >= len(code) or not (code[i + 1].kind == "op" and code[i + 1].value == "("):
            continue
        # match parentheses
        depth = 0
        open_idx = i + 1
        close_idx = None
        for j in range(open_idx, len(code)):
            if code[j].kind == "op" and code[j].value == "(":
                depth += 1
            elif code[j].kind == "op" and code[j].value == ")":
                depth -= 1
                if depth == 0:
                    close_idx = j
                    break
        if close_idx is None or close_idx == open_idx + 1:
            continue
        inner_start = code[open_idx].end
        inner_end = code[close_idx].start
        inner_text = source[inner_start:inner_end]
        signals = [
            tk.value
            for tk in code[open_idx + 1 : close_idx]
            if tk.kind == "ident" and tk.value not in _KEYWORDS
        ]
        replacement = f"!({inner_text})"
        cond_tok = code[open_idx + 1]
        yield _build_mutant(
            module, source, MutationOperator.BOOLEAN_NEGATION, cond_tok,
            replacement,
            "Negate if-condition: cond -> !(cond)", signals,
            span_end=inner_end, original_text=inner_text,
        )


def op_enable_removal(module: str, source: str) -> Iterator[Mutant]:
    """Remove an enable guard of the form ``if (en) begin ... end`` /
    ``if (en) stmt`` by forcing the condition to constant true (``1'b1``).

    Targets single-identifier conditions whose name suggests an enable/valid
    guard, so the removal is meaningful and syntactically safe.
    """
    toks = tokenize(source)
    code = code_tokens(toks)
    for i, t in enumerate(code):
        if not (t.kind == "ident" and t.value == "if"):
            continue
        if not (i + 3 < len(code)
                and code[i + 1].kind == "op" and code[i + 1].value == "("
                and code[i + 2].kind == "ident"
                and code[i + 3].kind == "op" and code[i + 3].value == ")"):
            continue
        cond = code[i + 2]
        low = cond.value.lower()
        if not any(k in low for k in ("en", "enable", "valid", "vld")):
            continue
        yield _build_mutant(
            module, source, MutationOperator.ENABLE_REMOVAL, cond, "1'b1",
            f"Remove enable guard '{cond.value}' (force condition true)",
            [cond.value],
        )


def op_reset_polarity_flip(module: str, source: str) -> Iterator[Mutant]:
    """Flip reset edge sensitivity and its matching branch test.

    Handles the common pattern in the subset:
      always @(posedge clk or negedge rst_n) ... if (!rst_n) ...
    Flipping ``negedge`` <-> ``posedge`` in the sensitivity list is the concrete
    injected defect; the mutated signal is the reset net.
    """
    toks = tokenize(source)
    code = code_tokens(toks)
    for i, t in enumerate(code):
        if t.kind != "ident" or t.value not in ("posedge", "negedge"):
            continue
        if i + 1 >= len(code) or code[i + 1].kind != "ident":
            continue
        target = code[i + 1].value
        low = target.lower()
        if not any(k in low for k in ("rst", "reset", "rstn", "resetn")):
            continue
        flipped = "posedge" if t.value == "negedge" else "negedge"
        yield _build_mutant(
            module, source, MutationOperator.RESET_POLARITY_FLIP, t, flipped,
            f"Flip reset edge '{t.value}' -> '{flipped}' on '{target}'",
            [target],
        )


def op_reset_value_change(module: str, source: str) -> Iterator[Mutant]:
    """Change a reset assignment's constant value.

    Looks for ``<lhs> <= <const>;`` inside a reset branch and perturbs the
    constant. For a sized/based literal we flip a bit representation; for a plain
    0/1 we toggle; otherwise increment by 1.
    """
    toks = tokenize(source)
    code = code_tokens(toks)
    for i, t in enumerate(code):
        if not (t.kind == "op" and t.value == "<=" and _is_nonblocking_assign(code, i)):
            continue
        if i + 1 >= len(code):
            continue
        nxt = code[i + 1]
        # value must be a single constant followed by ';'
        if not (i + 2 < len(code) and code[i + 2].kind == "op" and code[i + 2].value == ";"):
            continue
        if nxt.kind != "number":
            continue
        new_val = _perturb_constant(nxt.value)
        if new_val == nxt.value:
            continue
        lhs = _nearest_lhs_signal(code, i)
        signals = [lhs] if lhs else []
        yield _build_mutant(
            module, source, MutationOperator.RESET_VALUE_CHANGE, nxt, new_val,
            f"Change reset/assign value '{nxt.value}' -> '{new_val}'", signals,
        )


def _perturb_constant(value: str) -> str:
    if "'" in value:
        prefix, _, digits = value.partition("'")
        base = digits[0]
        body = digits[1:]
        if base in ("b", "B") and set(body) <= set("01_"):
            flipped = "".join("1" if c == "0" else "0" if c == "1" else c for c in body)
            return f"{prefix}'{base}{flipped}"
        if base in ("h", "H", "d", "D", "o", "O"):
            # bump last hex/dec/oct digit deterministically
            last = body[-1]
            table = "0123456789abcdef"
            if last.lower() in table:
                idx = table.index(last.lower())
                nxt = table[(idx + 1) % (16 if base in ("h", "H") else 10)]
                return f"{prefix}'{base}{body[:-1]}{nxt}"
        return value
    if value in ("0", "1"):
        return "1" if value == "0" else "0"
    try:
        return str(int(value) + 1)
    except ValueError:
        return value


def op_counter_incdec_change(module: str, source: str) -> Iterator[Mutant]:
    """Swap counter increment/decrement: ``x + 1`` <-> ``x - 1``.

    Matches ``ident (+|-) 1`` on the RHS of an assignment.
    """
    toks = tokenize(source)
    code = code_tokens(toks)
    for i in range(len(code) - 2):
        a, op_t, b = code[i], code[i + 1], code[i + 2]
        if not (a.kind == "ident" and a.value not in _KEYWORDS):
            continue
        if not (op_t.kind == "op" and op_t.value in ("+", "-")):
            continue
        if not (b.kind == "number" and b.value in ("1", "1'b1", "1'd1")):
            continue
        flipped = "-" if op_t.value == "+" else "+"
        lhs = _nearest_lhs_signal(code, i)
        signals = [a.value] + ([lhs] if lhs else [])
        yield _build_mutant(
            module, source, MutationOperator.COUNTER_INCDEC_CHANGE, op_t, flipped,
            f"Change counter update '{a.value} {op_t.value} 1' -> "
            f"'{a.value} {flipped} 1'", signals,
        )


def op_assign_operand_swap(module: str, source: str) -> Iterator[Mutant]:
    """Swap the two operands of a binary ``+`` or ``-`` on an assignment RHS.

    For ``a - b`` this changes semantics (``b - a``); for ``a + b`` it is a
    weaker mutation but still exercises operand-ordering assumptions. Only fires
    when both operands are plain identifiers (syntactically safe).
    """
    toks = tokenize(source)
    code = code_tokens(toks)
    for i in range(len(code) - 2):
        a, op_t, b = code[i], code[i + 1], code[i + 2]
        if not (a.kind == "ident" and a.value not in _KEYWORDS):
            continue
        if not (op_t.kind == "op" and op_t.value in ("-", "+")):
            continue
        if not (b.kind == "ident" and b.value not in _KEYWORDS):
            continue
        replacement = f"{b.value} {op_t.value} {a.value}"
        signals = [a.value, b.value]
        yield _build_mutant(
            module, source, MutationOperator.ASSIGN_OPERAND_SWAP, a, replacement,
            f"Swap operands '{a.value} {op_t.value} {b.value}' -> "
            f"'{b.value} {op_t.value} {a.value}'", signals,
            span_end=b.end, original_text=source[a.start:b.end],
        )


def op_valid_ready_gating_removal(module: str, source: str) -> Iterator[Mutant]:
    """Remove valid/ready gating in a boolean expression.

    Targets ``valid && ready`` (or ``vld && rdy`` etc.) and drops the ready
    term, leaving just ``valid``. Concretely replaces ``A && B`` with ``A`` when
    the two identifiers look like a handshake pair.
    """
    toks = tokenize(source)
    code = code_tokens(toks)
    for i in range(len(code) - 2):
        a, op_t, b = code[i], code[i + 1], code[i + 2]
        if not (a.kind == "ident" and op_t.kind == "op" and op_t.value == "&&"
                and b.kind == "ident"):
            continue
        names = (a.value.lower(), b.value.lower())
        is_handshake = (
            any("valid" in n or "vld" in n for n in names)
            and any("ready" in n or "rdy" in n for n in names)
        )
        if not is_handshake:
            continue
        yield _build_mutant(
            module, source, MutationOperator.VALID_READY_GATING_REMOVAL, a,
            a.value,
            f"Remove handshake gating '{a.value} && {b.value}' -> '{a.value}'",
            [a.value, b.value],
            span_end=b.end, original_text=source[a.start:b.end],
        )


def op_width_truncation(module: str, source: str) -> Iterator[Mutant]:
    """Truncate an assignment RHS with an explicit bit-select (syntactically safe).

    Only fires on ``<lhs> = <rhs_ident>;`` / ``<= <rhs_ident>;`` where the RHS is
    a bare identifier: it becomes ``<rhs_ident>[0]`` (keep LSB only), a
    deterministic, always-legal narrowing.
    """
    toks = tokenize(source)
    code = code_tokens(toks)
    for i, t in enumerate(code):
        if not (t.kind == "op" and t.value in ("=", "<=")):
            continue
        if t.value == "<=" and not _is_nonblocking_assign(code, i):
            continue
        if not (i + 2 < len(code)
                and code[i + 1].kind == "ident"
                and code[i + 1].value not in _KEYWORDS
                and code[i + 2].kind == "op" and code[i + 2].value == ";"):
            continue
        rhs = code[i + 1]
        replacement = f"{rhs.value}[0]"
        lhs = _nearest_lhs_signal(code, i)
        signals = [rhs.value] + ([lhs] if lhs else [])
        yield _build_mutant(
            module, source, MutationOperator.WIDTH_TRUNCATION, rhs, replacement,
            f"Truncate width of RHS '{rhs.value}' -> '{rhs.value}[0]'", signals,
        )


ALL_OPERATORS: dict[MutationOperator, Callable[[str, str], Iterator[Mutant]]] = {
    MutationOperator.RELATIONAL_FLIP: op_relational_flip,
    MutationOperator.BOOLEAN_NEGATION: op_boolean_negation,
    MutationOperator.ENABLE_REMOVAL: op_enable_removal,
    MutationOperator.RESET_POLARITY_FLIP: op_reset_polarity_flip,
    MutationOperator.RESET_VALUE_CHANGE: op_reset_value_change,
    MutationOperator.COUNTER_INCDEC_CHANGE: op_counter_incdec_change,
    MutationOperator.ASSIGN_OPERAND_SWAP: op_assign_operand_swap,
    MutationOperator.VALID_READY_GATING_REMOVAL: op_valid_ready_gating_removal,
    MutationOperator.WIDTH_TRUNCATION: op_width_truncation,
}


def generate_mutants(
    module: str,
    source: str,
    operators: list[MutationOperator] | None = None,
) -> list[Mutant]:
    """Generate all mutants for ``source`` using the selected operators.

    Results are de-duplicated by mutant_id and returned in a stable, sorted
    order so golden reports are reproducible.
    """
    selected = operators or list(ALL_OPERATORS.keys())
    seen: dict[str, Mutant] = {}
    for op in selected:
        fn = ALL_OPERATORS[op]
        for mutant in fn(module, source):
            # A mutation that does not change the source is invalid; skip here
            # (invalid-ness due to no-op is caught in the executor too).
            if mutant.mutated_source == source:
                continue
            seen.setdefault(mutant.mutant_id, mutant)
    return sorted(
        seen.values(),
        key=lambda m: (m.diff.location.line, m.diff.location.col_start, m.mutant_id),
    )
