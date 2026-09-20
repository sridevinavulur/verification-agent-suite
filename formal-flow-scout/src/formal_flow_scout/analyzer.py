"""COI / partition analysis: turn a graph + property into a :class:`CoiReport`.

Pipeline (deterministic algorithms A, heuristic ranking B kept separate):

A. Deterministic (SOUND over-approximation):
   1. Resolve property seed signals to node ids.
   2. Combinational backward COI.
   3. Sequential expansion through state elements.
   4. Clock/reset-domain annotation.
   5. Tarjan SCCs restricted to the COI.

B. Heuristic (labelled HEURISTIC everywhere):
   6. Candidate partitions from hierarchy / SCC / interface cuts, each with cut
      signals, UNPROVEN environment assumptions, and soundness-risk flags.

The class never claims a partition is a valid formal reduction. It emits the
obligations a human/formal tool must discharge.
"""

from __future__ import annotations

from .graph_core import PackedGraph
from .models import (
    CandidatePartition,
    CoiReport,
    CoiStats,
    CutSignal,
    DependencyGraph,
    DomainInfo,
    EnvironmentAssumption,
    ExcludedLogic,
    ExclusionReason,
    NodeKind,
    PropertySpec,
    Provenance,
    SCCInfo,
    Soundness,
    SoundnessRisk,
)

_STATE_KINDS = frozenset({NodeKind.REG})
_CONTROL_KINDS = frozenset({NodeKind.CLOCK, NodeKind.RESET})


class Analyzer:
    def __init__(self, graph: DependencyGraph) -> None:
        self.graph = graph
        self.pg = PackedGraph(graph)

    # -- seed resolution ----------------------------------------------------- #

    def _resolve_seeds(self, prop: PropertySpec) -> tuple[list[int], list[str]]:
        resolved: list[int] = []
        unresolved: list[str] = []
        for sig in prop.signals:
            nid = self.pg.id_of(sig.name)
            if nid is None:
                # Try a suffix match: property signals may be given un-prefixed.
                matches = [
                    node.node_id
                    for node in self.pg.nodes
                    if node.name == sig.name or node.name.endswith("." + sig.name)
                ]
                if len(matches) == 1:
                    resolved.append(matches[0])
                    continue
                unresolved.append(sig.name)
            else:
                resolved.append(nid)
        return sorted(set(resolved)), unresolved

    # -- main entry ---------------------------------------------------------- #

    def analyze(
        self,
        prop: PropertySpec,
        provenance: Provenance,
        *,
        include_control_in_coi: bool = True,
    ) -> CoiReport:
        seeds, unresolved = self._resolve_seeds(prop)

        # Step 2+3: full sequential COI (comb + seq). Sound over-approximation.
        coi = self.pg.backward_coi(
            seeds,
            combinational_only=False,
            include_control=include_control_in_coi,
        )
        coi_sorted = sorted(coi)

        # Step 4: clock/reset domains, restricted to the COI.
        domains = self._domains(coi)

        # Step 5: SCCs restricted to the COI.
        sccs_raw = self.pg.tarjan_scc(subset=coi)
        sccs = [
            SCCInfo(
                scc_id=i,
                node_ids=comp,
                is_cyclic=(len(comp) > 1 or self.pg.has_self_loop(comp[0])),
            )
            for i, comp in enumerate(sccs_raw)
        ]
        cyclic = [s for s in sccs if s.is_cyclic]

        # Excluded logic with reasons.
        excluded = self._excluded(coi)

        # Global soundness risks (independent of a specific partition).
        global_risks = self._global_risks(coi, domains, cyclic)

        # Step 6 (heuristic): candidate partitions.
        partitions = self._candidate_partitions(coi, sccs, domains)

        stats = CoiStats(
            total_nodes=self.pg.n,
            total_edges=len(self.graph.edges),
            coi_nodes=len(coi),
            coi_registers=sum(1 for nid in coi if self.pg.kinds[nid] in _STATE_KINDS),
            coi_combinational=sum(
                1 for nid in coi if self.pg.kinds[nid] == NodeKind.NET
            ),
            excluded_nodes=self.pg.n - len(coi),
            scc_count=len(sccs),
            cyclic_scc_count=len(cyclic),
            largest_scc_size=max((len(s.node_ids) for s in sccs), default=0),
            clock_domain_count=len(domains.clock_domains),
            reset_domain_count=len(domains.reset_domains),
            seed_signals=len(prop.signals),
            unresolved_seed_signals=len(unresolved),
        )

        notes = [
            "Cone-of-influence is a SOUND structural over-approximation for the "
            "supported Verilog subset (see ARCHITECTURE.md).",
            "All candidate_partitions are HEURISTIC. A cut is a valid formal "
            "reduction ONLY if every listed environment_assumption (UNPROVEN) is "
            "discharged by a human or formal tool.",
        ]
        if unresolved:
            notes.append(
                "Some property seed signals did not resolve to graph nodes; the "
                "COI for those signals is EMPTY and may be unsound - resolve them."
            )

        return CoiReport(
            provenance=provenance,
            property_name=prop.name,
            top=self.graph.top,
            seed_node_ids=seeds,
            unresolved_seed_signals=unresolved,
            coi_node_ids=coi_sorted,
            excluded_logic=excluded,
            sccs=sccs,
            domains=domains,
            candidate_partitions=partitions,
            soundness_risks=global_risks,
            stats=stats,
            notes=notes,
        )

    # -- domains ------------------------------------------------------------- #

    def _domains(self, coi: set[int]) -> DomainInfo:
        clock_domains: dict[str, list[int]] = {}
        reset_domains: dict[str, list[int]] = {}
        for nid in sorted(coi):
            node = self.pg.nodes[nid]
            if node.clock_domain:
                clock_domains.setdefault(node.clock_domain, []).append(nid)
            if node.reset_domain:
                reset_domains.setdefault(node.reset_domain, []).append(nid)
        return DomainInfo(
            clock_domains={k: clock_domains[k] for k in sorted(clock_domains)},
            reset_domains={k: reset_domains[k] for k in sorted(reset_domains)},
            multi_clock=len(clock_domains) > 1,
        )

    # -- exclusions ---------------------------------------------------------- #

    def _excluded(self, coi: set[int]) -> list[ExcludedLogic]:
        out: list[ExcludedLogic] = []
        for nid in range(self.pg.n):
            if nid in coi:
                continue
            node = self.pg.nodes[nid]
            out.append(
                ExcludedLogic(
                    node_id=nid,
                    name=node.name,
                    kind=node.kind,
                    reason=ExclusionReason.NOT_IN_COI,
                    detail="Not reachable via fan-in from any property seed signal.",
                )
            )
        return out

    # -- risks --------------------------------------------------------------- #

    def _global_risks(
        self, coi: set[int], domains: DomainInfo, cyclic: list[SCCInfo]
    ) -> list[SoundnessRisk]:
        risks: list[SoundnessRisk] = []
        if domains.multi_clock:
            risks.append(
                SoundnessRisk(
                    severity="high",
                    kind="multi_clock_coi",
                    detail=(
                        "COI spans multiple clock domains "
                        f"({sorted(domains.clock_domains)}). Cross-clock reasoning "
                        "requires explicit CDC handling; a naive partition per "
                        "clock is NOT sound without synchronization assumptions."
                    ),
                    node_ids=sorted(coi),
                )
            )
        blackboxes = [
            nid for nid in sorted(coi) if self.pg.kinds[nid] == NodeKind.BLACKBOX
        ]
        if blackboxes:
            risks.append(
                SoundnessRisk(
                    severity="high",
                    kind="blackbox_in_coi",
                    detail=(
                        "COI includes outputs of undefined (black-box) instances. "
                        "Their internal behaviour is unknown and treated as free "
                        "inputs (sound over-approximation), but any proof relying "
                        "on their behaviour is UNSOUND without a model."
                    ),
                    node_ids=blackboxes,
                )
            )
        big_cycles = [s for s in cyclic if len(s.node_ids) > 1]
        if big_cycles:
            risks.append(
                SoundnessRisk(
                    severity="medium",
                    kind="combinational_or_sequential_cycle",
                    detail=(
                        f"{len(big_cycles)} cyclic SCC(s) in the COI. Cutting "
                        "inside a feedback loop requires an inductive/assume-"
                        "guarantee argument; a plain cut is UNSOUND."
                    ),
                    node_ids=sorted(n for s in big_cycles for n in s.node_ids),
                )
            )
        return risks

    # -- heuristic partitions ------------------------------------------------ #

    def _candidate_partitions(
        self, coi: set[int], sccs: list[SCCInfo], domains: DomainInfo
    ) -> list[CandidatePartition]:
        parts: list[CandidatePartition] = []

        # Strategy 1: hierarchy - group COI nodes by their owning module.
        by_module: dict[str, list[int]] = {}
        for nid in sorted(coi):
            by_module.setdefault(self.pg.nodes[nid].module, []).append(nid)
        for mod in sorted(by_module):
            members = by_module[mod]
            if len(by_module) < 2:
                continue  # single module - no meaningful hierarchy cut
            parts.append(
                self._make_partition(
                    f"hier::{mod}",
                    "hierarchy",
                    set(members),
                    coi,
                    rationale=(
                        f"HEURISTIC: all COI signals owned by module '{mod}'. "
                        "Grouping by hierarchy is a structural heuristic only."
                    ),
                )
            )

        # Strategy 2: SCC - one partition per non-trivial cyclic SCC.
        for scc in sccs:
            if scc.is_cyclic and len(scc.node_ids) > 1:
                parts.append(
                    self._make_partition(
                        f"scc::{scc.scc_id}",
                        "scc",
                        set(scc.node_ids),
                        coi,
                        rationale=(
                            "HEURISTIC: strongly-connected feedback cluster kept "
                            "intact so a cut does not split a loop. Proving it in "
                            "isolation still needs assume-guarantee obligations."
                        ),
                    )
                )

        # Strategy 3: interface cut - registers form a natural sequential cut.
        # Partition = combinational cone up to the nearest register boundary of
        # each seed-reachable register. We expose the register inputs as cuts.
        reg_nodes = {nid for nid in coi if self.pg.kinds[nid] in _STATE_KINDS}
        if reg_nodes:
            # Combinational-only COI from the seeds defines the "output" cone.
            parts.append(
                self._make_partition(
                    "interface::seq_boundary",
                    "interface_cut",
                    coi,  # full COI, but cuts placed at register boundaries
                    coi,
                    rationale=(
                        "HEURISTIC: cut placed at sequential (register) "
                        "boundaries. Each register's next-state inputs crossing "
                        "the boundary become free inputs requiring an assumption."
                    ),
                    force_reg_cuts=True,
                )
            )

        return parts

    def _make_partition(
        self,
        pid: str,
        strategy: str,
        members: set[int],
        coi: set[int],
        *,
        rationale: str,
        force_reg_cuts: bool = False,
    ) -> CandidatePartition:
        # A cut signal is a node inside `members` that has a fan-in edge to a
        # node OUTSIDE `members` but still in the COI (a real dependency severed
        # by the partition), or a boundary register when force_reg_cuts is set.
        cut_signals: list[CutSignal] = []
        assumptions: list[EnvironmentAssumption] = []
        risks: list[SoundnessRisk] = []
        seen_cut: set[int] = set()

        for nid in sorted(members):
            for dst, kind in self.pg.neighbours(nid):
                crosses = dst not in members and dst in coi
                reg_boundary = force_reg_cuts and kind.value == "seq"
                if crosses or reg_boundary:
                    # The severed dependency is `dst` (driver now outside).
                    cut_id = dst
                    if cut_id in seen_cut or cut_id not in coi:
                        continue
                    # Clock/reset are control signals, not data cuts: constraining
                    # them as "free inputs" is not a meaningful proof obligation
                    # (clock-domain concerns are covered by the multi_clock risk).
                    if self.pg.kinds[cut_id] in _CONTROL_KINDS:
                        continue
                    seen_cut.add(cut_id)
                    node = self.pg.nodes[cut_id]
                    cut_signals.append(
                        CutSignal(
                            node_id=cut_id,
                            name=node.name,
                            kind=node.kind,
                            direction="into_partition",
                        )
                    )
                    assumptions.append(
                        EnvironmentAssumption(
                            cut_signal=node.name,
                            node_id=cut_id,
                            obligation=(
                                f"Constrain '{node.name}' at the partition boundary "
                                "to over-approximate all values it can take in the "
                                "full design (free input, or a proven envelope)."
                            ),
                            soundness=Soundness.UNPROVEN,
                            rationale=(
                                "Severing this dependency drops the driving logic; "
                                "without a discharged assumption the reduced proof "
                                "may be UNSOUND (false PASS)."
                            ),
                        )
                    )

        if cut_signals:
            risks.append(
                SoundnessRisk(
                    severity="medium",
                    kind="unproven_cut_assumptions",
                    detail=(
                        f"Partition '{pid}' introduces {len(cut_signals)} cut "
                        "signal(s) whose environment assumptions are UNPROVEN. "
                        "The reduction is NOT valid until they are discharged."
                    ),
                    node_ids=[c.node_id for c in cut_signals],
                )
            )

        state_bits = sum(1 for nid in members if self.pg.kinds[nid] in _STATE_KINDS)
        return CandidatePartition(
            partition_id=pid,
            strategy=strategy,
            soundness=Soundness.HEURISTIC,
            included_nodes=sorted(members),
            cut_signals=cut_signals,
            environment_assumptions=assumptions,
            soundness_risks=risks,
            rationale=rationale,
            estimated_state_bits=state_bits,
        )
