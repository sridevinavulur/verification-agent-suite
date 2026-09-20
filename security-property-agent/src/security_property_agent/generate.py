"""Candidate SVA generation and mutation/fault example synthesis.

For each requirement we already have:
  * a decomposition (safety properties vs assumptions vs objectives)
  * a grounding (resolved RTL symbols with evidence)

This module turns *safety-property* clauses into candidate SVA using a fixed
whitelist of security property forms, then synthesizes deliberately-broken
mutations so a reviewer has concrete should-fail witnesses.

Design constraints (spec 6.13 + BUILD_STANDARD):
  * We only emit a candidate when the clause is a SAFETY_PROPERTY (or a
    SECURITY_TEST_OBJECTIVE, which becomes a ``cover``). Environment
    assumptions are rendered as ``assume`` candidates but NEVER as asserts.
  * We only emit when the required symbols are grounded with evidence. If a
    symbol is unresolved we skip emission and record why (no guessing).
  * Every emitted artifact is a CANDIDATE (status reflects this).
"""

from __future__ import annotations

from . import renderer
from .models import (
    CandidateProperty,
    Clause,
    ClauseKind,
    GroundingResult,
    MatchKind,
    MutationExample,
    MutationKind,
    PropertyForm,
    PropertyKind,
    Provenance,
    SecurityCategory,
    SecurityRequirement,
    SymbolRef,
)
from .util import sha256_text

# ---------------------------------------------------------------------------
# Per-category template selection
# ---------------------------------------------------------------------------
# Each category maps to a (property_form, builder) describing how to turn the
# grounded symbols into an SVA expression. Builders return (kind, form, text)
# or raise/return None when the required symbols are missing.
# ---------------------------------------------------------------------------


def _resolved(grounding: GroundingResult) -> dict[str, SymbolRef]:
    """Return term -> SymbolRef for symbols resolved with evidence."""
    return {
        s.term: s
        for s in grounding.symbols
        if s.match_kind in (MatchKind.EXACT, MatchKind.ALIAS) and s.symbol
    }


def _pick(resolved: dict[str, SymbolRef], *keywords: str) -> SymbolRef | None:
    """Pick the first resolved symbol whose name contains any keyword."""
    for kw in keywords:
        for term, ref in resolved.items():
            if kw in (ref.symbol or "").lower() or kw in term.lower():
                return ref
    return None


def _pick_excluding(
    resolved: dict[str, SymbolRef], exclude: SymbolRef | None, *keywords: str
) -> SymbolRef | None:
    """Pick a resolved symbol matching a keyword, excluding one already chosen."""
    ex_sig = _sig(exclude) if exclude else None
    for kw in keywords:
        for term, ref in resolved.items():
            if ex_sig is not None and _sig(ref) == ex_sig:
                continue
            if kw in (ref.symbol or "").lower() or kw in term.lower():
                return ref
    return None


def _clock_reset(grounding: GroundingResult) -> tuple[str | None, str | None]:
    clk = grounding.clock_candidates[0] if grounding.clock_candidates else None
    rst = grounding.reset_candidates[0] if grounding.reset_candidates else None
    return clk, rst


def _first_two_registers(resolved: dict[str, SymbolRef]) -> list[SymbolRef]:
    regs = [r for r in resolved.values() if r.kind in ("register", "net", "port")]
    return regs[:2]


def generate_candidates(
    requirement: SecurityRequirement,
    clauses: list[Clause],
    grounding: GroundingResult,
    git_sha: str = "UNKNOWN",
) -> tuple[list[CandidateProperty], list[str]]:
    """Return (candidates, skip_reasons)."""
    resolved = _resolved(grounding)
    clk, rst = _clock_reset(grounding)
    candidates: list[CandidateProperty] = []
    skips: list[str] = []
    seen_sva: set[str] = set()

    def prov(stage: str) -> Provenance:
        return Provenance(
            stage=stage,
            git_sha=git_sha,
            input_hashes={requirement.requirement_id: sha256_text(requirement.text)},
            notes=["candidate only; not verified; requires human review + tool evidence"],
        )

    for clause in clauses:
        # Only safety properties and test objectives become emittable artifacts.
        if clause.kind not in (
            ClauseKind.SAFETY_PROPERTY,
            ClauseKind.SECURITY_TEST_OBJECTIVE,
            ClauseKind.ENVIRONMENT_ASSUMPTION,
        ):
            continue

        if clk is None:
            skips.append(
                f"{clause.clause_id}: no clock candidate in Manifest; cannot render clocked SVA"
            )
            continue

        built = _build_for_category(requirement.category, clause, resolved, clk, rst)
        if built is None:
            skips.append(
                f"{clause.clause_id}: required symbols for category "
                f"'{requirement.category.value}' not grounded; skipped (no guessing)"
            )
            continue

        kind, form, sva_text, used = built

        # Environment assumptions may only be assume/cover, never assert.
        if clause.kind is ClauseKind.ENVIRONMENT_ASSUMPTION and kind is PropertyKind.ASSERT:
            skips.append(
                f"{clause.clause_id}: classified as environment assumption; refusing "
                "to emit as an assert (would over-constrain / mis-signoff)"
            )
            continue
        if clause.kind is ClauseKind.SECURITY_TEST_OBJECTIVE and kind is not PropertyKind.COVER:
            # objectives become cover regardless of category default
            kind = PropertyKind.COVER
            form = PropertyForm.REACHABLE
            sva_text = renderer.render_reachable(
                f"{clause.clause_id}_cover", clk, rst,
                _cover_expr(resolved, clause) or "1'b1",
            )

        # De-duplicate candidates whose SVA body (ignoring the trailing
        # per-clause comment) is identical. Splitting a sentence on punctuation
        # can yield sibling clauses that ground to the same property.
        body = sva_text.split("//")[0].strip()
        if body in seen_sva:
            skips.append(
                f"{clause.clause_id}: duplicate of an earlier clause's candidate; deduped"
            )
            continue
        seen_sva.add(body)

        candidates.append(
            CandidateProperty(
                property_name=f"{clause.clause_id}",
                requirement_id=requirement.requirement_id,
                clause_id=clause.clause_id,
                category=requirement.category,
                property_kind=kind,
                property_form=form,
                sva_text=sva_text,
                referenced_symbols=used,
                ambiguities=list(grounding.ambiguities),
                provenance=prov("generate_candidate"),
            )
        )

    return candidates, skips


def _cover_expr(resolved: dict[str, SymbolRef], clause: Clause) -> str | None:
    ref = next(iter(resolved.values()), None)
    return f"{ref.symbol}" if ref else None


def _sig(ref: SymbolRef) -> str:
    return ref.symbol or ref.term


def _build_for_category(
    category: SecurityCategory,
    clause: Clause,
    resolved: dict[str, SymbolRef],
    clk: str,
    rst: str | None,
) -> tuple[PropertyKind, PropertyForm, str, list[SymbolRef]] | None:
    """Return (kind, form, sva_text, used_symbols) or None if unbuildable."""
    name = f"{clause.clause_id}"

    if category is SecurityCategory.ACCESS_CONTROL:
        # "access X may only happen when granted": the guarded action implies
        # the grant. The guard signal is picked first so it is not mistaken for
        # the action.
        guard = _pick(resolved, "grant", "allow", "unlock", "authorized", "permit")
        action = _pick_excluding(
            resolved, guard, "commit", "access", "wr_en", "rd_en", "write", "read", "en"
        )
        if action is None or guard is None:
            # Without a distinct (action, guard) pair we cannot form a sound
            # access-control implication; refuse rather than guess.
            return None
        # committed action implies grant was present
        text = renderer.render_implication(
            name, clk, rst, _sig(action), _sig(guard), next_cycle=False
        )
        return PropertyKind.ASSERT, PropertyForm.IMPLICATION, text, [action, guard]

    if category is SecurityCategory.PRIVILEGE_GATING:
        op = _pick(resolved, "op", "wr_en", "write", "exec", "secure", "access")
        priv = _pick(resolved, "priv", "mode", "level", "ring", "supervisor")
        if op is None or priv is None:
            return None
        # privileged op implies privilege bit set
        text = renderer.render_implication(
            name, clk, rst, _sig(op), _sig(priv), next_cycle=False
        )
        return PropertyKind.ASSERT, PropertyForm.IMPLICATION, text, [op, priv]

    if category is SecurityCategory.DEBUG_LOCKOUT:
        # The lock signal is picked first (most specific), then the debug-enable
        # signal is picked while excluding whatever became the lock.
        lock = _pick(resolved, "lock", "locked", "lockout")
        dbg = _pick_excluding(
            resolved, lock,
            "dbg_en", "debug_en", "dbg_enable", "enable", "dbg", "debug", "jtag", "scan",
        )
        if dbg is None:
            return None
        if lock is not None and _sig(lock) != _sig(dbg):
            # when locked, debug must never be enabled
            text = renderer.render_implication(
                name, clk, rst, _sig(lock), f"!{_sig(dbg)}", next_cycle=False
            )
            return PropertyKind.ASSERT, PropertyForm.IMPLICATION, text, [lock, dbg]
        text = renderer.render_never(name, clk, rst, _sig(dbg))
        return PropertyKind.ASSERT, PropertyForm.NEVER, text, [dbg]

    if category is SecurityCategory.FAULT_RESPONSE:
        fault = _pick(resolved, "fault", "error", "err", "alarm", "detect")
        resp = _pick(resolved, "resp", "halt", "safe", "shutdown", "clear", "recover")
        if fault is None or resp is None:
            return None
        # fault detected -> response within a bounded window (default 1..3)
        text = renderer.render_bounded_response(
            name, clk, rst, _sig(fault), _sig(resp), 1, 3
        )
        return (
            PropertyKind.ASSERT,
            PropertyForm.BOUNDED_RESPONSE,
            text,
            [fault, resp],
        )

    if category is SecurityCategory.ERROR_CONTAINMENT:
        err = _pick(resolved, "error", "err", "corrupt", "poison")
        out = _pick(resolved, "out", "valid", "commit", "propagate", "downstream")
        if err is None or out is None:
            return None
        # error must not propagate to output (same cycle)
        text = renderer.render_implication(
            name, clk, rst, _sig(err), f"!{_sig(out)}", next_cycle=False
        )
        return PropertyKind.ASSERT, PropertyForm.IMPLICATION, text, [err, out]

    if category is SecurityCategory.LOCKSTEP_MISMATCH:
        pair = _first_two_registers(resolved)
        mism = _pick(resolved, "mismatch", "error", "fault", "err")
        if len(pair) >= 2:
            a, b = pair[0], pair[1]
            text = renderer.render_lockstep_equal(name, clk, rst, _sig(a), _sig(b))
            return PropertyKind.ASSERT, PropertyForm.LOCKSTEP_EQUAL, text, [a, b]
        if mism is not None:
            # can only assert that the mismatch flag is observed/handled
            text = renderer.render_never(name, clk, rst, f"{_sig(mism)}")
            return PropertyKind.ASSERT, PropertyForm.NEVER, text, [mism]
        return None

    if category is SecurityCategory.INFORMATION_FLOW_ADJACENT:
        secret = _pick(resolved, "secret", "key", "priv", "sensitive")
        sink = _pick(resolved, "out", "observe", "leak", "public", "debug", "readable")
        if secret is None or sink is None:
            return None
        # adjacency check only: secret should not equal an observable sink.
        # NOTE: this is NOT a true non-interference proof (see limitations).
        text = renderer.render_never(name, clk, rst, f"{_sig(sink)} == {_sig(secret)}")
        return PropertyKind.ASSERT, PropertyForm.NEVER, text, [secret, sink]

    return None


# ---------------------------------------------------------------------------
# Mutation / fault example synthesis
# ---------------------------------------------------------------------------
def generate_mutations(
    candidate: CandidateProperty, git_sha: str = "UNKNOWN"
) -> list[MutationExample]:
    """Synthesize deliberately-broken variants of a candidate.

    A mutation should FAIL (fire) if the original candidate is meaningful. This
    is a sanity witness for reviewers, not a correctness proof of the original.
    """
    prov = Provenance(
        stage="mutation",
        git_sha=git_sha,
        notes=["mutation is a should-fail witness; not proof the original holds"],
    )
    muts: list[MutationExample] = []
    base = candidate.sva_text

    def add(i: int, kind: MutationKind, desc: str, text: str) -> None:
        muts.append(
            MutationExample(
                mutation_id=f"{candidate.property_name}.m{i}",
                of_property=candidate.property_name,
                mutation_kind=kind,
                description=desc,
                mutated_sva_text=text,
                provenance=prov,
            )
        )

    form = candidate.property_form
    if form in (PropertyForm.IMPLICATION, PropertyForm.NEXT_CYCLE):
        # Negate the consequent: guard implies the *wrong* thing -> should fail.
        add(
            0,
            MutationKind.NEGATE_CONSEQUENT,
            "negate the consequent so the implication asserts the opposite outcome",
            _flip_consequent(base),
        )
        # Drop the guard so it becomes an unconditional (usually false) claim.
        add(
            1,
            MutationKind.DROP_GUARD,
            "drop the antecedent guard, over-asserting the consequent every cycle",
            _drop_guard(base),
        )
    elif form is PropertyForm.NEVER:
        # Turn 'never X' into 'always X' -> should fail on any real design.
        add(
            0,
            MutationKind.NEGATE_ANTECEDENT,
            "flip 'never' to 'always', asserting the forbidden condition holds",
            _drop_never(base),
        )
    elif form is PropertyForm.BOUNDED_RESPONSE:
        # Weaken the bound to [0:0] -> requires same-cycle response; often fails.
        add(
            0,
            MutationKind.WEAKEN_BOUND,
            "tighten response window to same cycle [0:0] to expose latency",
            _retime_bound(base, 0, 0),
        )
        add(
            1,
            MutationKind.NEGATE_CONSEQUENT,
            "negate the response, asserting the fault triggers the wrong action",
            _flip_consequent(base),
        )
    elif form is PropertyForm.LOCKSTEP_EQUAL:
        # Break lockstep: replace == with != -> should fail when replicas agree.
        add(
            0,
            MutationKind.BREAK_LOCKSTEP,
            "assert the two replicas are unequal; fires whenever they agree",
            base.replace(") == (", ") != (", 1),
        )

    return muts


def _flip_consequent(sva: str) -> str:
    """Wrap the consequent of an implication in ``!(...)``.

    ``sva`` = ``assert property (<clk> (ante) |-> [##[a:b]] (cons));  // name``
    Result negates the ``(cons)`` term so the property asserts the wrong outcome.
    """
    for op in ("|->", "|=>"):
        if op in sva:
            head, tail = sva.split(op, 1)
            # tail = " (cons));  // name"  (possibly with a leading ##[a:b])
            close = tail.rfind("))")
            if close == -1:
                return sva
            open_paren = tail.rfind("(", 0, close + 1)
            inner = tail[open_paren : close + 1]  # "(cons)"
            lead = tail[:open_paren]  # possible " ##[a:b] " and whitespace
            return f"{head}{op}{lead}!{inner});  // MUTATED"
    return sva.replace("));", ")) /* MUTATED */;", 1)


def _drop_never(sva: str) -> str:
    """Turn ``... !(cond));`` into ``... (cond));`` (assert the forbidden cond)."""
    if "!(" in sva:
        # remove exactly the negation directly after the clocking block
        return sva.replace(" !(", " (", 1).replace("  // ", "  // MUTATED ", 1)
    return sva + "  // MUTATED"


def _drop_guard(sva: str) -> str:
    """Drop the antecedent guard, asserting the consequent every cycle.

    ``assert property (@(posedge clk) disable iff (r) (ante) |-> (cons));``
    -> ``assert property (@(posedge clk) disable iff (r) (cons));``
    """
    for op in ("|->", "|=>"):
        if op in sva:
            head, tail = sva.split(op, 1)  # head ends after "(ante) "
            # clocking prefix = everything in head up to the last "(ante)" group
            ante_open = head.rstrip().rfind("(")
            clocking = head[:ante_open].rstrip()  # "...disable iff (r)"
            cons = tail.strip()  # "(cons));  // name"  (or "##[a:b] (cons));...")
            return f"{clocking} {cons}".rstrip() + "  // MUTATED"
    return sva + "  // MUTATED"


def _retime_bound(sva: str, lo: int, hi: int) -> str:
    import re as _re

    return _re.sub(r"##\[\d+:\d+\]", f"##[{lo}:{hi}]", sva, count=1) + "  // MUTATED"
