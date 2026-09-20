"""Deterministic static checks.

Every function takes a :class:`CheckContext` and returns a list of
:class:`Finding`. No check ever declares a property *correct*; it only surfaces
smells, risks, and outright errors. Heuristic findings are marked
``heuristic=True`` and phrased as risks, per BUILD_STANDARD.
"""

from __future__ import annotations

import re

from ..models import (
    CheckId,
    Finding,
    ImplicationStyle,
    PropertyKind,
    ResetPolarity,
    Severity,
    SignalRole,
)
from .context import CheckContext

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_RANGE_UNBOUNDED_RE = re.compile(r"##\s*\[\s*\d+\s*:\s*\$\s*\]")  # ##[n:$]
_EVENTUALLY_RE = re.compile(r"\bs?_?eventually\b")
_UNTIL_RE = re.compile(r"\bs?_?until(?:_with)?\b")
_CONST_RE = re.compile(r"^\s*(1'b1|1|1'h1|'1|true|1'bx|1'b0|0|1'h0)\s*$", re.IGNORECASE)
_RESET_HINT_RE = re.compile(r"\b(rst|reset|clr|clear)\b", re.IGNORECASE)


def _norm(expr: str | None) -> str:
    if not expr:
        return ""
    return re.sub(r"\s+", "", expr)


def _reset_signal_name(expr: str) -> str | None:
    """Return the base reset-ish identifier referenced in a disable expr."""
    m = re.search(r"!?\s*([A-Za-z_][A-Za-z0-9_$]*)", expr)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# 1. Missing clock
# ---------------------------------------------------------------------------


def check_missing_clock(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if p.clock is None:
        return [
            Finding(
                check_id=CheckId.MISSING_CLOCK,
                severity=Severity.ERROR,
                message="Property has no explicit clocking event (@(posedge ...)).",
                location=p.location,
                property_name=p.name,
                recommendation="Add an explicit clocking event; an unclocked concurrent "
                "assertion relies on a default clocking block that may not exist.",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 2. Missing / incorrect disable iff
# ---------------------------------------------------------------------------


def check_disable_iff(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    findings: list[Finding] = []

    # Cover properties legitimately often omit disable iff.
    if p.kind == PropertyKind.COVER:
        return findings

    has_reset_candidate = bool(ctx.manifest and ctx.manifest.reset_candidates)

    if p.disable_iff is None:
        sev = Severity.WARNING if has_reset_candidate else Severity.INFO
        findings.append(
            Finding(
                check_id=CheckId.MISSING_DISABLE_IFF,
                severity=sev,
                message="Assertion has no 'disable iff' reset guard.",
                location=p.location,
                property_name=p.name,
                heuristic=True,
                recommendation="Add 'disable iff (<reset>)' so the assertion does not "
                "fire during reset. Confirm intent; some invariants intentionally hold "
                "through reset.",
            )
        )
        return findings

    # disable iff present -- sanity-check the referenced signal.
    rst = _reset_signal_name(p.disable_iff)
    if ctx.manifest and rst is not None:
        sig = ctx.manifest.by_name().get(rst)
        if sig is None and rst not in ctx.manifest.reset_candidates:
            findings.append(
                Finding(
                    check_id=CheckId.MISSING_DISABLE_IFF,
                    severity=Severity.WARNING,
                    message=f"'disable iff' references '{rst}', which is not a declared "
                    "signal or reset candidate in the manifest.",
                    location=p.location,
                    property_name=p.name,
                    recommendation="Guard reset with an actual reset signal from the manifest.",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 3. Reset polarity risk
# ---------------------------------------------------------------------------


def check_reset_polarity(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if not p.disable_iff or not ctx.manifest:
        return []
    rst = _reset_signal_name(p.disable_iff)
    if rst is None:
        return []
    sig = ctx.manifest.by_name().get(rst)
    if sig is None or sig.reset_polarity == ResetPolarity.UNKNOWN:
        return []

    negated = p.disable_iff.strip().startswith("!") or p.disable_iff.strip().startswith("~")
    # active_low reset (rst_n) is asserted when LOW -> disable should use "!rst_n".
    # active_high reset is asserted when HIGH -> disable should use bare "rst".
    if sig.reset_polarity == ResetPolarity.ACTIVE_LOW and not negated:
        return [
            Finding(
                check_id=CheckId.RESET_POLARITY_RISK,
                severity=Severity.ERROR,
                message=f"'{rst}' is active-low in the manifest but 'disable iff' uses it "
                "un-negated. The assertion will be disabled when reset is INACTIVE.",
                location=p.location,
                property_name=p.name,
                recommendation=f"Use 'disable iff (!{rst})'.",
            )
        ]
    if sig.reset_polarity == ResetPolarity.ACTIVE_HIGH and negated:
        return [
            Finding(
                check_id=CheckId.RESET_POLARITY_RISK,
                severity=Severity.ERROR,
                message=f"'{rst}' is active-high in the manifest but 'disable iff' negates "
                "it. The assertion will be disabled when reset is INACTIVE.",
                location=p.location,
                property_name=p.name,
                recommendation=f"Use 'disable iff ({rst})'.",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 4. |-> vs |=> mismatch risk
# ---------------------------------------------------------------------------


def check_implication_style(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if p.implication == ImplicationStyle.NONE or not p.consequent:
        return []
    cons = p.consequent
    # Overlapping |-> combined with an immediately-following ##0 or a same-cycle
    # comparison of a *registered* output is a classic off-by-one smell.
    findings: list[Finding] = []
    if p.implication == ImplicationStyle.OVERLAPPING:
        # If the consequent starts with a next-cycle delay ##1, the author may
        # have wanted |=> instead (redundant delay), and vice-versa.
        if re.match(r"^\s*##\s*1\b", cons):
            findings.append(
                Finding(
                    check_id=CheckId.IMPLICATION_STYLE_RISK,
                    severity=Severity.WARNING,
                    message="Overlapping '|->' followed by '##1' is equivalent to '|=>'; "
                    "confirm the intended cycle alignment.",
                    location=p.location,
                    property_name=p.name,
                    heuristic=True,
                    recommendation="Use '|=>' for a next-cycle response, or drop the '##1'.",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 5. Unbounded / ambiguous temporal operators
# ---------------------------------------------------------------------------


def check_unbounded_temporal(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    findings: list[Finding] = []
    body = p.body
    if _RANGE_UNBOUNDED_RE.search(body):
        findings.append(
            Finding(
                check_id=CheckId.UNBOUNDED_TEMPORAL,
                severity=Severity.WARNING,
                message="Unbounded delay range '##[n:$]' used; the response has no upper "
                "bound, which is often unintended and hard to prove.",
                location=p.location,
                property_name=p.name,
                recommendation="Replace '$' with a concrete maximum cycle bound.",
            )
        )
    if _EVENTUALLY_RE.search(body) and "[" not in body.split("eventually")[-1][:8]:
        findings.append(
            Finding(
                check_id=CheckId.UNBOUNDED_TEMPORAL,
                severity=Severity.WARNING,
                message="Unbounded liveness operator ('eventually'/'s_eventually') without a "
                "cycle window; unbounded liveness is often not what was intended.",
                location=p.location,
                property_name=p.name,
                heuristic=True,
                recommendation="Prefer a bounded window, e.g. 's_eventually[1:N]', unless "
                "unbounded liveness is truly required.",
            )
        )
    if _UNTIL_RE.search(body):
        findings.append(
            Finding(
                check_id=CheckId.UNBOUNDED_TEMPORAL,
                severity=Severity.INFO,
                message="'until'-family operator present; verify termination / fairness "
                "conditions are intended.",
                location=p.location,
                property_name=p.name,
                heuristic=True,
                recommendation="Confirm whether a strong (s_until) or weak (until) form is meant.",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# 6. Weak consequent
# ---------------------------------------------------------------------------


_LEADING_DELAY_RE = re.compile(r"^\s*(##\s*(?:\[[^\]]*\]|\d+)\s*)+")


def check_weak_consequent(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if p.implication == ImplicationStyle.NONE or not p.consequent:
        return []
    # Strip a leading temporal delay so "##[0:$] 1'b1" is seen as constant-true.
    core = _LEADING_DELAY_RE.sub("", p.consequent.strip()).strip()
    cons_n = _norm(core)
    if _CONST_RE.match(core) and cons_n in {"1'b1", "1", "'1", "true"}:
        return [
            Finding(
                check_id=CheckId.WEAK_CONSEQUENT,
                severity=Severity.ERROR,
                message="Consequent is a constant true; the implication proves nothing.",
                location=p.location,
                property_name=p.name,
                recommendation="Replace the consequent with the actual expected behaviour.",
            )
        ]
    # A consequent that is a bare 1-bit signal with no relation is weak-ish.
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", p.consequent.strip()):
        return [
            Finding(
                check_id=CheckId.WEAK_CONSEQUENT,
                severity=Severity.INFO,
                message="Consequent is a single bare signal with no relation or timing; "
                "confirm it captures the full intended behaviour.",
                location=p.location,
                property_name=p.name,
                heuristic=True,
                recommendation="Consider tightening the consequent (value, timing window).",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 7. Antecedent duplicated in consequent
# ---------------------------------------------------------------------------


def check_antecedent_in_consequent(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if p.implication == ImplicationStyle.NONE or not p.antecedent or not p.consequent:
        return []
    ant = _norm(p.antecedent)
    cons = _norm(p.consequent)
    if not ant:
        return []
    if ant == cons:
        return [
            Finding(
                check_id=CheckId.ANTECEDENT_IN_CONSEQUENT,
                severity=Severity.ERROR,
                message="Antecedent and consequent are identical; the property is a "
                "tautology and cannot fail.",
                location=p.location,
                property_name=p.name,
                recommendation="The consequent must express a distinct expected behaviour.",
            )
        ]
    # Whole antecedent appears verbatim as a conjunct of the consequent.
    if ant and (cons.startswith(ant + "&&") or cons.endswith("&&" + ant) or f"&&{ant}&&" in cons):
        return [
            Finding(
                check_id=CheckId.ANTECEDENT_IN_CONSEQUENT,
                severity=Severity.WARNING,
                message="Antecedent expression is repeated inside the consequent; this is "
                "usually redundant and may indicate a copy/paste error.",
                location=p.location,
                property_name=p.name,
                heuristic=True,
                recommendation="Remove the duplicated antecedent term from the consequent.",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 8. Trivially-passing assertion
# ---------------------------------------------------------------------------


def check_trivially_passing(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if p.kind == PropertyKind.COVER:
        return []
    # No implication and body is a constant true.
    if p.implication == ImplicationStyle.NONE:
        body = p.body.strip()
        if _CONST_RE.match(body) and _norm(body) in {"1'b1", "1", "'1", "true"}:
            return [
                Finding(
                    check_id=CheckId.TRIVIALLY_PASSING,
                    severity=Severity.ERROR,
                    message="Assertion body is a constant true; it passes trivially and "
                    "verifies nothing.",
                    location=p.location,
                    property_name=p.name,
                    recommendation="Express an actual design property.",
                )
            ]
    # Implication whose antecedent is constant false -> vacuous by construction.
    if p.antecedent is not None:
        an = _norm(p.antecedent)
        if an in {"1'b0", "0", "'0", "false"}:
            return [
                Finding(
                    check_id=CheckId.TRIVIALLY_PASSING,
                    severity=Severity.ERROR,
                    message="Antecedent is constant false; the implication can never be "
                    "triggered and passes vacuously.",
                    location=p.location,
                    property_name=p.name,
                    recommendation="Fix the antecedent so the property can actually trigger.",
                )
            ]
    return []


# ---------------------------------------------------------------------------
# 9. Assumption constraining outputs / internal state
# ---------------------------------------------------------------------------


def check_assume_constrains_output(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if p.kind != PropertyKind.ASSUME or not ctx.manifest:
        return []
    by_name = ctx.manifest.by_name()
    findings: list[Finding] = []
    for ident in p.identifiers:
        sig = by_name.get(ident)
        if sig is None:
            continue
        if sig.role in (SignalRole.OUTPUT, SignalRole.INTERNAL):
            findings.append(
                Finding(
                    check_id=CheckId.ASSUME_CONSTRAINS_OUTPUT,
                    severity=Severity.ERROR,
                    message=f"Assumption constrains '{ident}', which is a design "
                    f"{sig.role.value}. Assuming outputs/internal state can mask real bugs "
                    "and unsoundly restrict the proof.",
                    location=p.location,
                    property_name=p.name,
                    recommendation="Assumptions should constrain environment inputs only. "
                    "Convert to an assertion or remove; requires human decision.",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 10 + 11. Undeclared / mismatched-width signals
# ---------------------------------------------------------------------------

_WIDTH_LITERAL_RE = re.compile(r"(\d+)\s*'[bhdo]", re.IGNORECASE)
_COMPARE_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_$]*)\s*(==|!=|<=|>=|<|>)\s*(\d+)\s*'[bhdo]([0-9a-fA-FxXzZ_]+)"
)


def check_signals(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if ctx.manifest is None:
        return []
    by_name = ctx.manifest.by_name()
    known = set(by_name) | set(ctx.manifest.clock_candidates) | set(ctx.manifest.reset_candidates)
    findings: list[Finding] = []

    idents = list(p.identifiers)
    if p.clock and p.clock not in idents:
        idents.append(p.clock)

    for ident in idents:
        if ident not in known:
            findings.append(
                Finding(
                    check_id=CheckId.UNDECLARED_SIGNAL,
                    severity=Severity.ERROR,
                    message=f"Signal '{ident}' is not declared in the RTL Intent Manifest.",
                    location=p.location,
                    property_name=p.name,
                    recommendation="Ground every identifier to a manifest symbol before review.",
                )
            )

    # Width mismatch: compare signal width vs literal width in `sig == W'bxxx`.
    for m in _COMPARE_RE.finditer(p.body):
        sig_name, _op, wstr, _val = m.group(1), m.group(2), m.group(3), m.group(4)
        sig = by_name.get(sig_name)
        if sig is None:
            continue
        lit_width = int(wstr)
        if lit_width != sig.width:
            findings.append(
                Finding(
                    check_id=CheckId.WIDTH_MISMATCH,
                    severity=Severity.WARNING,
                    message=f"Signal '{sig_name}' is {sig.width}-bit in the manifest but is "
                    f"compared against a {lit_width}-bit literal.",
                    location=p.location,
                    property_name=p.name,
                    recommendation="Match literal width to the signal width to avoid "
                    "unintended truncation or zero-extension.",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# 12. Property name does not reflect semantics
# ---------------------------------------------------------------------------

_SEMANTIC_TOKENS = {
    "req",
    "grant",
    "gnt",
    "ack",
    "ready",
    "valid",
    "vld",
    "rdy",
    "full",
    "empty",
    "overflow",
    "ovf",
    "underflow",
    "udf",
    "reset",
    "rst",
    "stable",
    "onehot",
    "mutex",
    "counter",
    "wrap",
    "sat",
    "resp",
    "response",
    "handshake",
    "en",
    "enable",
    "state",
}
_GENERIC_NAMES_RE = re.compile(
    r"^(p|prop|property|a|assert|assertion|check|chk)\d*$", re.IGNORECASE
)


def check_name_semantics(ctx: CheckContext) -> list[Finding]:
    p = ctx.prop
    if not p.name:
        return [
            Finding(
                check_id=CheckId.NAME_SEMANTICS,
                severity=Severity.INFO,
                message="Property is unnamed; named properties are easier to trace and debug.",
                location=p.location,
                property_name=None,
                recommendation="Give the property a semantic label, e.g. 'req_gets_grant'.",
            )
        ]
    name = p.name
    if _GENERIC_NAMES_RE.match(name):
        return [
            Finding(
                check_id=CheckId.NAME_SEMANTICS,
                severity=Severity.INFO,
                message=f"Property name '{name}' is generic and does not describe its intent.",
                location=p.location,
                property_name=name,
                heuristic=True,
                recommendation="Rename to reflect the checked behaviour.",
            )
        ]
    lname = name.lower()
    if not any(tok in lname for tok in _SEMANTIC_TOKENS):
        return [
            Finding(
                check_id=CheckId.NAME_SEMANTICS,
                severity=Severity.INFO,
                message=f"Property name '{name}' does not obviously reflect the behaviour it "
                "checks.",
                location=p.location,
                property_name=name,
                heuristic=True,
                recommendation="Prefer a name that encodes trigger/response semantics.",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 13. Vacuity RISK heuristic (NOT complete vacuity detection)
# ---------------------------------------------------------------------------


def check_vacuity_risk(ctx: CheckContext) -> list[Finding]:
    """Heuristic only. This is NOT sound vacuity detection: that requires formal
    reachability/coverage analysis of the antecedent. We only flag *structural*
    risk patterns."""
    p = ctx.prop
    if p.implication == ImplicationStyle.NONE or not p.antecedent:
        return []
    ant = p.antecedent.strip()

    risky = False
    reason = ""
    # Antecedent references a reset-ish signal in a way that may never be true
    # once disable iff already excludes reset.
    if p.disable_iff and _RESET_HINT_RE.search(ant):
        risky = True
        reason = (
            "antecedent references a reset-like signal that 'disable iff' may already "
            "exclude, so the antecedent might never hold while enabled"
        )
    # Antecedent is a long AND-chain (>=3 conjuncts) -> harder to reach.
    elif ant.count("&&") >= 2:
        risky = True
        reason = "antecedent is a conjunction of 3+ terms and may be hard to reach"

    if not risky:
        return []
    return [
        Finding(
            check_id=CheckId.VACUITY_RISK,
            severity=Severity.INFO,
            message=f"Vacuity RISK (heuristic, not sound): {reason}. Confirm the antecedent "
            "is reachable with a cover property or formal reachability analysis.",
            location=p.location,
            property_name=p.name,
            heuristic=True,
            recommendation="Add a matching cover property to prove the antecedent is reachable.",
        )
    ]
