"""Deterministic reset-topology analysis.

Turns :class:`~reset_intent_agent.rtl_parser.ParsedModule` records into a
:class:`~reset_intent_agent.models.ResetIntentManifest`.

Everything here is deterministic and evidence-backed:

* Reset polarity is decided by *voting* over explicit evidence
  (edge in sensitivity list, guard expression form, name convention). If votes
  conflict or are absent, the result is ``UNKNOWN`` and an
  :class:`Ambiguity` is recorded. Polarity is NEVER inferred silently.
* Sync vs async is structural: a reset in the sensitivity edge list of an
  ``always_ff`` block is asynchronous; a reset only used inside the block body
  guard is synchronous.
* Reset domains group registers by shared reset signal and are marked
  ``heuristic=True``.
* Reset-domain crossings are detected structurally (a register from one domain
  read in a procedure that writes another domain) and marked heuristic.
"""

from __future__ import annotations

from .models import (
    Ambiguity,
    CandidateSVA,
    PolarityEvidence,
    PropertyKind,
    ResetCandidate,
    ResetDomain,
    ResetDomainCrossing,
    ResetGraph,
    ResetGraphEdge,
    ResetGraphNode,
    ResetPolarity,
    ResetSync,
    ResetTarget,
    Risk,
    Severity,
    SourceLocation,
    TestRecommendation,
)
from .rtl_parser import (
    AlwaysBlock,
    ParsedModule,
    _signals_in_expr,
    looks_like_reset_name,
)


# --------------------------------------------------------------------------- #
# Polarity evidence extraction
# --------------------------------------------------------------------------- #
def _polarity_from_guard(guard: str, reset_signal: str) -> tuple[ResetPolarity, str]:
    """Infer the polarity a single guard expression votes for.

    Rules (each returns an explicit vote, never a silent guess):
      * ``if (!rst_n)`` / ``if (~rst_n)``  -> active_low  (reset active when 0)
      * ``if (rst)``   / ``if (rst == 1)`` -> active_high
      * ``if (rst_n)`` (bare, name ends _n) is contradictory -> unknown
    """
    g = guard.replace(" ", "")
    negated = f"!{reset_signal}" in g or f"~{reset_signal}" in g
    eq0 = f"{reset_signal}==0" in g or f"{reset_signal}==1'b0" in g
    eq1 = f"{reset_signal}==1" in g or f"{reset_signal}==1'b1" in g
    bare = g == reset_signal

    if negated or eq0:
        return ResetPolarity.ACTIVE_LOW, "guard negates reset -> active-low"
    if eq1:
        return ResetPolarity.ACTIVE_HIGH, "guard compares reset==1 -> active-high"
    if bare:
        return ResetPolarity.ACTIVE_HIGH, "bare reset guard -> active-high"
    return ResetPolarity.UNKNOWN, "guard form did not determine polarity"


def _polarity_from_name(name: str) -> tuple[ResetPolarity, str]:
    low = name.lower()
    if low.endswith("_n") or low.endswith("n") and ("rst" in low or "reset" in low):
        if low.endswith("_n") or low in {"rstn", "resetn", "nrst", "arstn", "srstn"}:
            return ResetPolarity.ACTIVE_LOW, "name suffix _n suggests active-low"
    return ResetPolarity.UNKNOWN, "name gives no polarity signal"


def _polarity_from_edge(edge: str | None) -> tuple[ResetPolarity, str]:
    """Async reset edge in sensitivity list votes for a polarity.

    ``negedge rst_n`` -> asserted when low -> active-low.
    ``posedge rst``   -> asserted when high -> active-high.
    """
    if edge == "negedge":
        return ResetPolarity.ACTIVE_LOW, "async negedge -> active-low"
    if edge == "posedge":
        return ResetPolarity.ACTIVE_HIGH, "async posedge -> active-high"
    return ResetPolarity.UNKNOWN, "no async edge evidence"


def _vote_polarity(
    evidence: list[PolarityEvidence],
) -> tuple[ResetPolarity, list[str]]:
    """Aggregate polarity votes. Conflicts -> UNKNOWN (never silent)."""
    votes = [e.votes_polarity for e in evidence if e.votes_polarity != ResetPolarity.UNKNOWN]
    notes: list[str] = []
    if not votes:
        return ResetPolarity.UNKNOWN, ["no polarity evidence; not inferred silently"]
    unique = set(votes)
    if len(unique) == 1:
        return votes[0], [f"{len(votes)} consistent polarity vote(s)"]
    notes.append(
        "conflicting polarity evidence: "
        + ", ".join(sorted(v.value for v in unique))
        + " -> unknown (requires review)"
    )
    return ResetPolarity.UNKNOWN, notes


# --------------------------------------------------------------------------- #
# Core analysis
# --------------------------------------------------------------------------- #
class ResetAnalyzer:
    def __init__(self, module: ParsedModule) -> None:
        self.mod = module
        self._amb_counter = 0
        self._risk_counter = 0
        self._rec_counter = 0

    def _amb_id(self) -> str:
        self._amb_counter += 1
        return f"AMB{self._amb_counter:03d}"

    def _risk_id(self) -> str:
        self._risk_counter += 1
        return f"RISK{self._risk_counter:03d}"

    def _rec_id(self) -> str:
        self._rec_counter += 1
        return f"REC{self._rec_counter:03d}"

    # -- resets --------------------------------------------------------------
    def _detect_reset_candidates(
        self, ambiguities: list[Ambiguity]
    ) -> tuple[list[ResetCandidate], dict[str, ResetCandidate]]:
        # signal -> aggregated evidence
        agg: dict[str, dict] = {}
        port_names = {p.name for p in self.mod.ports}

        for blk in self.mod.always_blocks:
            if not blk.is_edge_sensitive:
                continue
            # async reset: edge-listed non-clock signals that look like resets
            clock_sigs = _guess_clock_signals(blk)
            for item in blk.sensitivity:
                if item.edge and item.signal not in clock_sigs:
                    sig = item.signal
                    ent = agg.setdefault(sig, _new_entry(sig, blk.location))
                    ent["sync"] = ResetSync.ASYNCHRONOUS
                    pol, detail = _polarity_from_edge(item.edge)
                    ent["evidence"].append(
                        PolarityEvidence(
                            kind="edge",
                            detail=detail,
                            votes_polarity=pol,
                            location=blk.location,
                        )
                    )
                    ent["rationale"].append(
                        f"appears as {item.edge} in async always_ff sensitivity list"
                    )

            # sync reset: guard signals inside block body
            for a in blk.assigns:
                if a.under_reset and a.reset_signal:
                    sig = a.reset_signal
                    ent = agg.setdefault(sig, _new_entry(sig, blk.location))
                    if ent["sync"] == ResetSync.UNKNOWN:
                        ent["sync"] = ResetSync.SYNCHRONOUS
                    pol, detail = _polarity_from_guard(a.reset_active_expr or "", sig)
                    ent["evidence"].append(
                        PolarityEvidence(
                            kind="guard_expr",
                            detail=f"{detail}: `{a.reset_active_expr}`",
                            votes_polarity=pol,
                            location=a.location,
                        )
                    )
                    ent["rationale"].append(
                        f"guards a reset-value assignment: `{a.reset_active_expr}`"
                    )
                    ent["targets"].append(a)

        # name evidence for every candidate
        for sig, ent in agg.items():
            pol, detail = _polarity_from_name(sig)
            if pol != ResetPolarity.UNKNOWN:
                ent["evidence"].append(
                    PolarityEvidence(kind="name_suffix", detail=detail, votes_polarity=pol)
                )

        candidates: list[ResetCandidate] = []
        by_signal: dict[str, ResetCandidate] = {}
        for sig, ent in sorted(agg.items()):
            polarity, notes = _vote_polarity(ent["evidence"])
            rationale = list(dict.fromkeys(ent["rationale"] + notes))
            confidence = _reset_confidence(sig, ent)
            cand = ResetCandidate(
                signal=sig,
                polarity=polarity,
                sync=ent["sync"],
                confidence=confidence,
                polarity_evidence=ent["evidence"],
                rationale=rationale,
                location=ent["location"],
                fanout_registers=sorted({a.lhs for a in ent["targets"]}),
                is_port=sig in port_names,
            )
            candidates.append(cand)
            by_signal[sig] = cand

            if polarity == ResetPolarity.UNKNOWN:
                ambiguities.append(
                    Ambiguity(
                        ambiguity_id=self._amb_id(),
                        signal=sig,
                        detail=(
                            f"Reset polarity of '{sig}' could not be determined from "
                            "evidence; not inferred silently. Reviewer must confirm."
                        ),
                        severity=Severity.HIGH,
                        location=ent["location"],
                    )
                )
        return candidates, by_signal

    # -- targets & domains ---------------------------------------------------
    def _reset_targets(
        self, by_signal: dict[str, ResetCandidate]
    ) -> list[ResetTarget]:
        targets: list[ResetTarget] = []
        seen: set[tuple[str, str]] = set()
        for blk in self.mod.always_blocks:
            for a in blk.assigns:
                if a.under_reset and a.reset_signal:
                    key = (a.lhs, a.reset_signal)
                    if key in seen:
                        continue
                    seen.add(key)
                    sync = (
                        by_signal[a.reset_signal].sync
                        if a.reset_signal in by_signal
                        else ResetSync.UNKNOWN
                    )
                    targets.append(
                        ResetTarget(
                            register_name=a.lhs,
                            reset_signal=a.reset_signal,
                            reset_value=a.rhs,
                            sync=sync,
                            location=a.location,
                        )
                    )
        return sorted(targets, key=lambda t: (t.reset_signal, t.register_name))

    def _domains(
        self, targets: list[ResetTarget], by_signal: dict[str, ResetCandidate]
    ) -> list[ResetDomain]:
        groups: dict[str, list[str]] = {}
        for t in targets:
            groups.setdefault(t.reset_signal, []).append(t.register_name)
        domains: list[ResetDomain] = []
        for i, (sig, regs) in enumerate(sorted(groups.items())):
            cand = by_signal.get(sig)
            domains.append(
                ResetDomain(
                    domain_id=f"D{i}",
                    reset_signal=sig,
                    polarity=cand.polarity if cand else ResetPolarity.UNKNOWN,
                    sync=cand.sync if cand else ResetSync.UNKNOWN,
                    members=sorted(set(regs)),
                    heuristic=True,
                )
            )
        return domains

    def _crossings(
        self, targets: list[ResetTarget], domains: list[ResetDomain]
    ) -> list[ResetDomainCrossing]:
        """Structural RDC detection.

        For each edge-sensitive block, if a register is written under reset
        domain B but its next-state expression reads a register belonging to
        reset domain A (A != B), flag a possible reset-domain crossing.
        """
        reg_domain: dict[str, str] = {}
        for d in domains:
            for r in d.members:
                reg_domain[r] = d.domain_id
        domain_reset = {d.domain_id: d.reset_signal for d in domains}

        crossings: list[ResetDomainCrossing] = []
        seen: set[tuple[str, str]] = set()
        for blk in self.mod.always_blocks:
            for a in blk.assigns:
                if a.under_reset:
                    continue
                dst = a.lhs
                dst_dom = reg_domain.get(dst)
                if dst_dom is None:
                    continue
                for src in _signals_in_expr(a.rhs):
                    src_dom = reg_domain.get(src)
                    if src_dom is None or src_dom == dst_dom:
                        continue
                    key = (src, dst)
                    if key in seen:
                        continue
                    seen.add(key)
                    crossings.append(
                        ResetDomainCrossing(
                            from_domain=src_dom,
                            to_domain=dst_dom,
                            from_register=src,
                            to_register=dst,
                            severity=Severity.MEDIUM,
                            rationale=[
                                f"'{src}' (reset {domain_reset[src_dom]}) feeds "
                                f"'{dst}' (reset {domain_reset[dst_dom]}); "
                                "possible reset-domain crossing",
                            ],
                            heuristic=True,
                            location=a.location,
                        )
                    )
        return sorted(crossings, key=lambda c: (c.from_register, c.to_register))

    # -- graph ---------------------------------------------------------------
    def _graph(
        self,
        candidates: list[ResetCandidate],
        domains: list[ResetDomain],
        crossings: list[ResetDomainCrossing],
    ) -> ResetGraph:
        nodes: list[ResetGraphNode] = []
        edges: list[ResetGraphEdge] = []
        for c in candidates:
            nodes.append(
                ResetGraphNode(
                    node_id=f"rst::{c.signal}",
                    kind="reset",
                    label=f"{c.signal}\\n({c.polarity.value}, {c.sync.value})",
                )
            )
        for d in domains:
            nodes.append(
                ResetGraphNode(node_id=f"dom::{d.domain_id}", kind="domain", label=d.domain_id)
            )
            edges.append(
                ResetGraphEdge(
                    src=f"rst::{d.reset_signal}", dst=f"dom::{d.domain_id}", kind="resets"
                )
            )
            for r in d.members:
                rid = f"reg::{r}"
                if not any(n.node_id == rid for n in nodes):
                    nodes.append(ResetGraphNode(node_id=rid, kind="register", label=r))
                edges.append(
                    ResetGraphEdge(src=f"dom::{d.domain_id}", dst=rid, kind="member_of")
                )
        for cr in crossings:
            edges.append(
                ResetGraphEdge(
                    src=f"reg::{cr.from_register}",
                    dst=f"reg::{cr.to_register}",
                    kind="rdc",
                    heuristic=True,
                )
            )
        return ResetGraph(nodes=nodes, edges=edges)

    # -- risks & recommendations --------------------------------------------
    def _risks(
        self,
        candidates: list[ResetCandidate],
        targets: list[ResetTarget],
        crossings: list[ResetDomainCrossing],
    ) -> list[Risk]:
        risks: list[Risk] = []
        # no reset detected but there are edge-sensitive blocks with state
        edge_blocks = [b for b in self.mod.always_blocks if b.is_edge_sensitive]
        if edge_blocks and not candidates:
            risks.append(
                Risk(
                    risk_id=self._risk_id(),
                    category="no_reset",
                    detail=(
                        "Edge-sensitive sequential logic present but no reset "
                        "candidate detected. Uninitialised state on power-up is possible."
                    ),
                    severity=Severity.HIGH,
                    location=edge_blocks[0].location,
                )
            )
        # mixed sync/async for one signal, or mixed across signals
        syncs = {c.sync for c in candidates}
        if ResetSync.SYNCHRONOUS in syncs and ResetSync.ASYNCHRONOUS in syncs:
            risks.append(
                Risk(
                    risk_id=self._risk_id(),
                    category="mixed_sync",
                    detail=(
                        "Module mixes synchronous and asynchronous resets. Verify "
                        "reset assertion/deassertion ordering and recovery."
                    ),
                    severity=Severity.MEDIUM,
                )
            )
        for c in candidates:
            if c.polarity == ResetPolarity.UNKNOWN:
                risks.append(
                    Risk(
                        risk_id=self._risk_id(),
                        category="polarity",
                        detail=(
                            f"Reset '{c.signal}' has undetermined polarity. Candidate "
                            "SVA for this reset is emitted parameterised and MUST be "
                            "reviewed before use."
                        ),
                        severity=Severity.HIGH,
                        location=c.location,
                    )
                )
        for cr in crossings:
            risks.append(
                Risk(
                    risk_id=self._risk_id(),
                    category="rdc",
                    detail=(
                        f"Possible reset-domain crossing {cr.from_register} "
                        f"({cr.from_domain}) -> {cr.to_register} ({cr.to_domain}). "
                        "Heuristic; requires RDC review."
                    ),
                    severity=cr.severity,
                    location=cr.location,
                )
            )
        # registers written in edge blocks with no reset value -> quiescence/init risk
        reset_regs = {t.register_name for t in targets}
        unreset = _unreset_registers(self.mod, reset_regs)
        for r in sorted(unreset):
            risks.append(
                Risk(
                    risk_id=self._risk_id(),
                    category="quiescence",
                    detail=(
                        f"Register '{r}' is written in sequential logic but has no "
                        "detected reset value; initial state may be X."
                    ),
                    severity=Severity.MEDIUM,
                )
            )
        return risks

    def _recommendations(
        self, candidates: list[ResetCandidate], targets: list[ResetTarget]
    ) -> list[TestRecommendation]:
        recs: list[TestRecommendation] = []
        for c in candidates:
            recs.append(
                TestRecommendation(
                    rec_id=self._rec_id(),
                    kind="cover",
                    detail=(
                        f"Cover that reset '{c.signal}' is asserted at least once "
                        "(reset-assertion reachability)."
                    ),
                    target_signal=c.signal,
                )
            )
            recs.append(
                TestRecommendation(
                    rec_id=self._rec_id(),
                    kind="cover",
                    detail=(
                        f"Cover reset deassertion of '{c.signal}' followed by normal "
                        "operation (reset recovery)."
                    ),
                    target_signal=c.signal,
                )
            )
        if targets:
            recs.append(
                TestRecommendation(
                    rec_id=self._rec_id(),
                    kind="directed_test",
                    detail=(
                        "Directed test: assert reset mid-transaction and confirm all "
                        "reset targets return to their reset values (interface quiescence)."
                    ),
                )
            )
        return recs

    # -- driver --------------------------------------------------------------
    def analyze(self) -> tuple[
        list[ResetCandidate],
        list[ResetTarget],
        list[ResetDomain],
        list[ResetDomainCrossing],
        ResetGraph,
        list[Risk],
        list[Ambiguity],
        list[TestRecommendation],
    ]:
        ambiguities: list[Ambiguity] = []
        candidates, by_signal = self._detect_reset_candidates(ambiguities)
        targets = self._reset_targets(by_signal)
        domains = self._domains(targets, by_signal)
        crossings = self._crossings(targets, domains)
        graph = self._graph(candidates, domains, crossings)
        risks = self._risks(candidates, targets, crossings)
        recs = self._recommendations(candidates, targets)
        for u in self.mod.unsupported:
            ambiguities.append(
                Ambiguity(
                    ambiguity_id=self._amb_id(),
                    detail=f"Unsupported construct ({u.kind}): {u.detail}",
                    severity=Severity.LOW,
                    location=u.location,
                )
            )
        return candidates, targets, domains, crossings, graph, risks, ambiguities, recs


# --------------------------------------------------------------------------- #
# Candidate SVA generation (sva-intent-engine style: status=candidate)
# --------------------------------------------------------------------------- #
def generate_candidate_sva(
    candidates: list[ResetCandidate],
    targets: list[ResetTarget],
    clock: str | None,
) -> list[CandidateSVA]:
    """Emit reviewable candidate reset-behavior properties.

    Properties emitted per reset target:
      * reset-state: while reset asserted, target holds reset value.

    The reset-active expression is chosen from polarity. If polarity is UNKNOWN
    the expression is left as a ``/* REVIEW: polarity */`` placeholder so the
    property compiles-shaped but forces human review -- never a silent guess.
    """
    props: list[CandidateSVA] = []
    clk = clock or "clk"
    counter = 0
    for t in targets:
        cand = next((c for c in candidates if c.signal == t.reset_signal), None)
        polarity = cand.polarity if cand else ResetPolarity.UNKNOWN
        active = _reset_active_expr(t.reset_signal, polarity)
        counter += 1
        pid = f"P{counter:03d}"
        name = f"p_reset_state_{t.register_name}"
        sva = (
            f"{name}: assert property (\n"
            f"  @(posedge {clk}) ({active}) |-> ({t.register_name} == {t.reset_value})\n"
            f");"
        )
        notes = ["Candidate only. Not verified. Confirm clock, polarity, and value."]
        if polarity == ResetPolarity.UNKNOWN:
            notes.append(
                "Reset polarity UNKNOWN: active expression is a REVIEW placeholder."
            )
        props.append(
            CandidateSVA(
                property_id=pid,
                name=name,
                kind=PropertyKind.ASSERT,
                sva_text=sva,
                clock=clk,
                reset_signal=t.reset_signal,
                reset_polarity=polarity,
                rationale=(
                    f"Register '{t.register_name}' is assigned '{t.reset_value}' under "
                    f"reset '{t.reset_signal}'."
                ),
                referenced_signals=sorted({t.register_name, t.reset_signal}),
                review_notes=notes,
            )
        )
    return props


def _reset_active_expr(signal: str, polarity: ResetPolarity) -> str:
    if polarity == ResetPolarity.ACTIVE_LOW:
        return f"!{signal}"
    if polarity == ResetPolarity.ACTIVE_HIGH:
        return signal
    return f"/* REVIEW: polarity of {signal} unknown */ {signal}"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _new_entry(signal: str, location: SourceLocation) -> dict:
    return {
        "signal": signal,
        "sync": ResetSync.UNKNOWN,
        "evidence": [],
        "rationale": [],
        "location": location,
        "targets": [],
    }


def _reset_confidence(signal: str, ent: dict) -> float:
    score = 0.4
    if looks_like_reset_name(signal):
        score += 0.3
    if ent["sync"] == ResetSync.ASYNCHRONOUS:
        score += 0.15
    if ent["targets"]:
        score += 0.15
    return round(min(score, 1.0), 3)


def _guess_clock_signals(blk: AlwaysBlock) -> set[str]:
    """Within an edge-sensitive block, identify likely clock(s).

    Heuristic: the posedge/negedge signal that does NOT look like a reset is the
    clock. If ambiguous, treat name-based clock hints (clk/clock) as clocks.
    """
    edges = [i for i in blk.sensitivity if i.edge]
    clocks: set[str] = set()
    for i in edges:
        low = i.signal.lower()
        if "clk" in low or "clock" in low:
            clocks.add(i.signal)
    if not clocks:
        non_reset = [i.signal for i in edges if not looks_like_reset_name(i.signal)]
        if len(non_reset) == 1:
            clocks.add(non_reset[0])
    return clocks


def _unreset_registers(mod: ParsedModule, reset_regs: set[str]) -> set[str]:
    written: set[str] = set()
    for blk in mod.always_blocks:
        if not blk.is_edge_sensitive:
            continue
        for a in blk.assigns:
            written.add(a.lhs)
    return written - reset_regs


def module_clock(mod: ParsedModule) -> str | None:
    for blk in mod.always_blocks:
        if blk.is_edge_sensitive:
            clks = _guess_clock_signals(blk)
            if clks:
                return sorted(clks)[0]
    return None
