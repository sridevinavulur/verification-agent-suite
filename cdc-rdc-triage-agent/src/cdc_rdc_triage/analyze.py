"""Deterministic structural CDC/RDC triage engine.

Pipeline (per module, then aggregated):

1. Domain assignment
   For every ``always_ff`` procedure, determine its *clock* (edge-sensitive
   entry whose signal is a clock candidate, else the first edge signal) and its
   *reset* (a reset candidate appearing in the sensitivity list -> async, or in
   the control/condition signals -> sync).  Every register driven in that
   procedure inherits that (clock, reset) domain.

2. Data-flow edges
   For each register, look at the RHS of its nonblocking assignments and find
   which *other registers* it reads.  If a source register lives in a different
   clock domain than the destination register, that is a candidate CDC crossing.
   If the clock is the same but the (async) reset differs, that is a candidate
   RDC crossing.

3. Synchronizer evidence (2-FF detection)
   A destination register in domain D is a synchronizer-stage candidate if its
   only data source is a single register that is *also* in domain D and whose
   only job is to sample a cross-domain signal.  We walk the chain of
   single-fan-in same-domain registers ("FF chain") landing on a crossing and
   report its depth.  Depth >= 2 with no combinational logic in between is a
   2-FF (or deeper) synchronizer *candidate* -- reported as HEURISTIC evidence,
   never as "correct".

4. Multi-bit warnings
   A crossing whose transferred signal is wider than 1 bit (from its net/port
   range) is flagged multi_bit -- multi-bit CDC needs gray-code/handshake, which
   a plain FF sync does not provide.

5. Risk ranking
   A deterministic score combines: crossing kind, presence/absence of sync
   evidence, multi-bit-ness, and reset asymmetry.

All outputs are HEURISTIC and STRUCTURAL.  See report_models for the non-claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .glossary import Glossary
from .manifest_models import (
    Manifest,
    Module,
    Procedure,
    ProcedureKind,
    Range,
)
from .report_models import (
    Crossing,
    CrossingKind,
    Domain,
    ModuleTriage,
    Severity,
    SyncEvidence,
    TriageReport,
)
from .rhs import base_signal, is_bit_sliced, referenced_identifiers


@dataclass
class _RegInfo:
    """Resolved per-register structural facts inside one module."""

    name: str
    proc_index: int
    clock: str | None
    reset: str | None
    reset_async: bool
    width: int | None
    location: object  # SourceLocation
    # base names of *other signals* this reg reads on its RHS
    reads: set[str] = field(default_factory=set)
    # subset of reads that are bit-sliced
    sliced_reads: set[str] = field(default_factory=set)


def _range_width(rng: Range | None) -> int | None:
    """Try to compute a bit width from a packed range with numeric bounds.

    Returns ``None`` when either bound is a non-numeric expression (parameter)
    -- we do not evaluate parameter arithmetic.
    """

    if rng is None:
        return 1
    try:
        msb = int(str(rng.msb).strip())
        lsb = int(str(rng.lsb).strip())
    except ValueError:
        return None
    return abs(msb - lsb) + 1


def _signal_width(module: Module, name: str) -> int | None:
    for net in module.nets:
        if net.name == name:
            if net.is_memory:
                return _range_width(net.range)
            return _range_width(net.range)
    for port in module.ports:
        if port.name == name:
            return _range_width(port.range)
    return None


def _procedure_clock(proc: Procedure, clocks: set[str]) -> str | None:
    edge_signals = [s.signal for s in proc.sensitivity if s.edge in ("posedge", "negedge")]
    for sig in edge_signals:
        if sig in clocks:
            return sig
    # fall back to the first edge-sensitive signal that is not a known reset
    return edge_signals[0] if edge_signals else None


def _procedure_reset(
    proc: Procedure, resets: set[str], clock: str | None
) -> tuple[str | None, bool]:
    """Return (reset_signal, is_async).

    async reset  -> reset appears in the sensitivity list as an edge.
    sync reset   -> reset appears only in condition/control signals.
    """

    edge_signals = {s.signal for s in proc.sensitivity if s.edge in ("posedge", "negedge")}
    for sig in edge_signals:
        if sig in resets and sig != clock:
            return sig, True
    for sig in proc.condition_signals:
        if sig in resets:
            return sig, False
    return None, False


class _ModuleAnalyzer:
    def __init__(self, module: Module, glossary: Glossary) -> None:
        self.m = module
        self.glossary = glossary
        self.clocks = {c.signal for c in module.clock_candidates}
        self.resets = {r.signal for r in module.reset_candidates}
        self.regs: dict[str, _RegInfo] = {}
        self._build_registers()
        self.fanout: dict[str, list[str]] = self._build_fanout()

    def _build_registers(self) -> None:
        procs_by_index = {p.index: p for p in self.m.procedures}
        for reg in self.m.registers:
            proc = procs_by_index.get(reg.driven_in_procedure_index)
            if proc is None or proc.kind != ProcedureKind.always_ff:
                continue
            clock = _procedure_clock(proc, self.clocks)
            reset, is_async = _procedure_reset(proc, self.resets, clock)
            width = _signal_width(self.m, reg.name)
            info = _RegInfo(
                name=reg.name,
                proc_index=proc.index,
                clock=clock,
                reset=reset,
                reset_async=is_async,
                width=width,
                location=reg.location,
            )
            self._collect_reads(info, proc)
            self.regs[reg.name] = info

    def _collect_reads(self, info: _RegInfo, proc: Procedure) -> None:
        for a in proc.assignments:
            if not a.nonblocking:
                continue
            if base_signal(a.lhs) != info.name:
                continue
            for ident in referenced_identifiers(a.rhs):
                if ident == info.name:
                    continue
                info.reads.add(ident)
                if is_bit_sliced(a.rhs, ident):
                    info.sliced_reads.add(ident)

    def _build_fanout(self) -> dict[str, list[str]]:
        """reg -> list of registers that read it (as their sole/among sources)."""

        fanout: dict[str, list[str]] = {name: [] for name in self.regs}
        for reg in self.regs.values():
            for src in reg.reads:
                if src in fanout:
                    fanout[src].append(reg.name)
        for k in fanout:
            fanout[k].sort()
        return fanout

    # ---- domain identity -------------------------------------------------

    def _domain_of(self, name: str) -> Domain | None:
        r = self.regs.get(name)
        if r is None:
            return None
        return Domain(clock=r.clock, reset=r.reset)

    # ---- synchronizer chain detection ------------------------------------

    def _is_clean_stage(self, reg: _RegInfo, expected_source: str) -> bool:
        """A clean synchronizer stage samples exactly ``expected_source`` and
        nothing else (no combinational mixing, no bit-slicing)."""

        return (
            reg.reads == {expected_source}
            and expected_source not in reg.sliced_reads
        )

    def _sync_chain_depth(self, sampling_reg: str, crossing_src: str) -> int:
        """Forward synchronizer depth starting at the flop that *samples* the
        cross-domain source.

        A 2-FF synchronizer is::

            sync_ff1 <= flag_a;   // samples cross-domain source (stage 1)
            sync_ff2 <= sync_ff1; // same clock domain, single fan-in (stage 2)

        We count ``sampling_reg`` (stage 1, which must cleanly sample
        ``crossing_src``) plus each downstream register that lives in the same
        clock domain and does nothing but forward the previous stage.  The walk
        follows the *unique* same-domain single-fan-in successor.
        """

        first = self.regs[sampling_reg]
        # Stage 1 must cleanly sample the cross-domain source.
        if not self._is_clean_stage(first, crossing_src):
            return 1 if crossing_src in first.reads else 0

        depth = 1
        prev = sampling_reg
        seen = {sampling_reg}
        while True:
            successors = [
                s
                for s in self.fanout.get(prev, [])
                if s not in seen
                and self.regs[s].clock == first.clock
                and self._is_clean_stage(self.regs[s], prev)
            ]
            if len(successors) != 1:
                break
            nxt = successors[0]
            depth += 1
            seen.add(nxt)
            prev = nxt
        return depth

    def _glossary_evidence(self) -> dict[str, int]:
        """Map a module-local *net* to a synchronizer depth if it is driven by
        an instance of a glossary synchronizer cell."""

        out: dict[str, int] = {}
        for inst in self.m.instances:
            cell = self.glossary.cell_for_module(inst.module)
            if cell is None:
                continue
            for conn in inst.connections:
                if cell.data_out_port and conn.formal == cell.data_out_port:
                    out[base_signal(conn.actual)] = cell.depth
                elif cell.data_out_port is None:
                    out[base_signal(conn.actual)] = cell.depth
        return out

    # ---- main -------------------------------------------------------------

    def analyze(self) -> ModuleTriage:
        clock_domains = sorted({r.clock for r in self.regs.values() if r.clock})
        reset_domains = sorted({r.reset for r in self.regs.values() if r.reset})
        glossary_sync = self._glossary_evidence()

        crossings: list[Crossing] = []
        notes: list[str] = []

        for dst in sorted(self.regs.values(), key=lambda r: r.name):
            dst_domain = Domain(clock=dst.clock, reset=dst.reset)
            for src_name in sorted(dst.reads):
                src = self.regs.get(src_name)
                if src is None:
                    continue  # not a register -> combinational input, skip here
                src_domain = Domain(clock=src.clock, reset=src.reset)

                cdc = (
                    src.clock is not None
                    and dst.clock is not None
                    and src.clock != dst.clock
                )
                # RDC: same clock but different *asynchronous* reset domains.
                rdc = (
                    not cdc
                    and src.clock == dst.clock
                    and src.reset != dst.reset
                    and (src.reset_async or dst.reset_async)
                )
                if not cdc and not rdc:
                    continue

                kind = CrossingKind.cdc if cdc else CrossingKind.rdc
                crossings.append(
                    self._make_crossing(
                        kind, src, dst, src_domain, dst_domain, glossary_sync
                    )
                )

        crossings.sort(key=lambda c: (-c.risk_score, c.src_signal, c.dst_signal))
        return ModuleTriage(
            module=self.m.name,
            clock_domains=clock_domains,
            reset_domains=reset_domains,
            crossings=crossings,
            notes=notes,
        )

    def _make_crossing(
        self,
        kind: CrossingKind,
        src: _RegInfo,
        dst: _RegInfo,
        src_domain: Domain,
        dst_domain: Domain,
        glossary_sync: dict[str, int],
    ) -> Crossing:
        rationale: list[str] = []
        width = src.width
        multi_bit = width is not None and width > 1
        combinational = src.name in dst.sliced_reads or self._has_comb_neighbors(dst)

        # ---- synchronizer evidence ----
        sync_evidence = SyncEvidence.none_found
        sync_depth: int | None = None

        if dst.name in glossary_sync:
            sync_evidence = SyncEvidence.glossary_cell
            sync_depth = glossary_sync[dst.name]
            rationale.append(
                f"destination fed by glossary synchronizer cell (depth {sync_depth})"
            )
        elif kind == CrossingKind.cdc:
            # ``dst`` is the flop that samples the cross-domain source; measure
            # the forward same-domain single-fan-in flop chain from it.
            depth = self._sync_chain_depth(dst.name, src.name)
            if depth >= 2:
                sync_depth = depth
                sync_evidence = (
                    SyncEvidence.two_ff_candidate
                    if depth == 2
                    else SyncEvidence.multi_ff_candidate
                )
                rationale.append(
                    f"{depth} back-to-back flops in destination clock domain "
                    f"'{dst.clock}' with single fan-in starting at the sampling "
                    f"flop '{dst.name}' -- {depth}-FF synchronizer candidate "
                    "(HEURISTIC; clock/domain evidence only, correctness NOT proven)"
                )
            else:
                rationale.append(
                    "no back-to-back single-fan-in flop chain detected at the "
                    "sampling flop -- no structural synchronizer evidence"
                )

        # ---- rationale for the crossing itself ----
        if kind == CrossingKind.cdc:
            rationale.insert(
                0,
                f"register '{dst.name}' (clk={dst.clock}) reads register "
                f"'{src.name}' (clk={src.clock}) across clock domains",
            )
        else:
            rationale.insert(
                0,
                f"register '{dst.name}' (rst={dst.reset}) reads register "
                f"'{src.name}' (rst={src.reset}) on the same clock "
                f"'{dst.clock}' across asynchronous reset domains",
            )
        if multi_bit:
            rationale.append(
                f"transferred signal '{src.name}' is {width} bits wide -- multi-bit "
                "CDC needs gray-code/handshake; a plain FF sync is insufficient"
            )
        if combinational:
            rationale.append(
                "combinational logic observed on the crossing path -- may "
                "reconverge / glitch (HEURISTIC)"
            )

        severity, score = self._rank(
            kind, sync_evidence, multi_bit, combinational, src, dst
        )

        return Crossing(
            kind=kind,
            module=self.m.name,
            src_signal=src.name,
            dst_signal=dst.name,
            src_domain=src_domain,
            dst_domain=dst_domain,
            width_bits=width,
            multi_bit=multi_bit,
            sync_evidence=sync_evidence,
            sync_depth=sync_depth,
            severity=severity,
            risk_score=score,
            heuristic=True,
            rationale=rationale,
            src_location=src.location,  # type: ignore[arg-type]
            dst_location=dst.location,  # type: ignore[arg-type]
        )

    def _has_comb_neighbors(self, dst: _RegInfo) -> bool:
        # more than one data source, or a mix of reg and non-reg reads => logic
        reg_sources = [s for s in dst.reads if s in self.regs]
        non_reg = [s for s in dst.reads if s not in self.regs]
        return len(reg_sources) > 1 or bool(non_reg)

    def _rank(
        self,
        kind: CrossingKind,
        sync: SyncEvidence,
        multi_bit: bool,
        combinational: bool,
        src: _RegInfo,
        dst: _RegInfo,
    ) -> tuple[Severity, int]:
        score = 40  # base for any candidate crossing
        if kind == CrossingKind.rdc:
            score += 10
        if sync in (SyncEvidence.none_found, SyncEvidence.not_applicable):
            score += 25
        elif sync in (SyncEvidence.two_ff_candidate, SyncEvidence.multi_ff_candidate):
            score -= 15  # some evidence lowers priority (but never to zero)
        elif sync == SyncEvidence.glossary_cell:
            score -= 20
        if multi_bit:
            score += 20
        if combinational:
            score += 10
        if src.width is None or dst.width is None:
            score += 5  # unknown width -> can't rule out multi-bit
        score = max(5, min(100, score))

        if score >= 70:
            sev = Severity.high
        elif score >= 50:
            sev = Severity.medium
        elif score >= 30:
            sev = Severity.low
        else:
            sev = Severity.info
        return sev, score


REVIEWER_CHECKLIST = [
    "Confirm the source and destination clocks are genuinely asynchronous "
    "(different frequency/phase or unrelated), not just differently named.",
    "For each flagged crossing, confirm an appropriate synchronizer exists and "
    "matches the transfer type (single-bit -> N-FF; multi-bit -> gray-code or "
    "handshake/FIFO).",
    "For every '2-FF synchronizer candidate', verify the flops are actually in "
    "the destination domain and have no combinational logic between stages.",
    "For every multi-bit crossing, verify a coherent transfer scheme "
    "(gray-code counter, req/ack handshake, async FIFO) -- FF sync alone is unsafe.",
    "Verify reset-domain crossings: source and destination resets must be "
    "sequenced/synchronized so a reset assert/deassert cannot corrupt the "
    "destination.",
    "Confirm no CDC path is fed by combinational reconvergence of "
    "differently-synchronized bits.",
    "Run a commercial CDC/RDC signoff tool -- this triage is heuristic and NOT "
    "a substitute for structural+functional CDC/RDC verification.",
]

LIMITATIONS = [
    "Structural only: no metastability, glitch, or functional analysis.",
    "Clock/reset domains come from heuristic candidates in the manifest; a "
    "wrong candidate propagates to every finding.",
    "Data flow is derived from expression *text* (no full AST); complex "
    "expressions may under- or over-report identifier references.",
    "Cross-module (hierarchical) crossings are NOT traced through port "
    "connections in this version -- analysis is per-module.",
    "Parameterized widths that the manifest keeps as text cannot be evaluated, "
    "so some multi-bit crossings show width=unknown.",
    "A '2-FF synchronizer candidate' is structural evidence only and does NOT "
    "prove correct metastability handling.",
    "Generate blocks, functions/tasks, and memories are not modeled by the "
    "upstream subset parser and are therefore invisible here.",
]


def analyze_manifest(
    manifest: Manifest,
    *,
    glossary: Glossary | None = None,
    tool_version: str,
) -> TriageReport:
    """Run the full structural triage over a manifest and return a report."""

    gl = glossary or Glossary.empty()
    module_reports: list[ModuleTriage] = []
    for module in sorted(manifest.modules, key=lambda m: m.name):
        analyzer = _ModuleAnalyzer(module, gl)
        module_reports.append(analyzer.analyze())

    all_crossings = [c for mr in module_reports for c in mr.crossings]
    summary = {
        "total_crossings": len(all_crossings),
        "cdc_crossings": sum(1 for c in all_crossings if c.kind == CrossingKind.cdc),
        "rdc_crossings": sum(1 for c in all_crossings if c.kind == CrossingKind.rdc),
        "multi_bit_crossings": sum(1 for c in all_crossings if c.multi_bit),
        "crossings_without_sync_evidence": sum(
            1
            for c in all_crossings
            if c.sync_evidence in (SyncEvidence.none_found, SyncEvidence.not_applicable)
        ),
        "high_severity": sum(1 for c in all_crossings if c.severity == Severity.high),
        "medium_severity": sum(1 for c in all_crossings if c.severity == Severity.medium),
        "low_severity": sum(1 for c in all_crossings if c.severity == Severity.low),
    }

    return TriageReport(
        tool_version=tool_version,
        top=manifest.top,
        summary=summary,
        modules=module_reports,
        reviewer_checklist=list(REVIEWER_CHECKLIST),
        limitations=list(LIMITATIONS),
    )
