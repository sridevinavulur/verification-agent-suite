"""Deterministic triage engine.

Given a parsed :class:`EquivalenceLog`, optional reference/revised
:class:`DesignManifest`s, and an optional :class:`SourceMap`, this engine:

* groups duplicate mismatch signatures (:meth:`group_signatures`),
* identifies each group's mismatch cone (fan-in union),
* compares reset/init behavior (:meth:`compare_reset`),
* runs likely-cause heuristics -- width, polarity, gating, state-encoding,
  optimization, reset/init, config/constraint (:meth:`classify_causes`),
* ranks source locations for review (:meth:`rank_locations`), and
* builds a reproducible debug packet.

Everything is deterministic (stable sort keys, no randomness). All cause
verdicts are tagged ``is_heuristic=True``. The engine never overrides the
tool's own status.
"""

from __future__ import annotations

from .models import (
    CauseCategory,
    DebugPacket,
    DesignManifest,
    EquivalenceLog,
    EquivalenceStatus,
    LikelyCause,
    MismatchGroup,
    MismatchKind,
    MismatchPoint,
    Provenance,
    RankedLocation,
    ResetComparison,
    ResetInfo,
    ResetPolarity,
    ResetSync,
    SourceMap,
    TriageReport,
)

# Signals whose *names* suggest reset/enable/gating logic. Used only as a
# heuristic hint alongside structural evidence.
_GATING_HINTS = ("en", "enable", "clk_en", "gate", "cg", "valid", "stall")
_POLARITY_HINTS = ("rst", "reset", "rstn", "rst_n", "clr", "clear", "aresetn")


class TriageEngine:
    """Stateful-per-run triage engine (construct once per report)."""

    def __init__(
        self,
        log: EquivalenceLog,
        ref_manifest: DesignManifest | None = None,
        rev_manifest: DesignManifest | None = None,
        source_map: SourceMap | None = None,
    ) -> None:
        self.log = log
        self.ref_manifest = ref_manifest
        self.rev_manifest = rev_manifest
        self.source_map = source_map or SourceMap()

    # ------------------------------------------------------------------ #
    # Signature grouping                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def signature(mp: MismatchPoint) -> str:
        """A duplicate-detection signature for a mismatch point.

        Two mismatches with the same signature are considered "the same bug"
        for triage purposes. The signature deliberately ignores the specific
        compare-point *name* (e.g. bit index) so that ``out[0]``, ``out[1]``
        collapse into one group, but is sensitive to kind, width relation, the
        set of differing CEX signals, and the fan-in cone shape.
        """
        width_rel = "same"
        if mp.ref_width is not None and mp.rev_width is not None:
            if mp.ref_width != mp.rev_width:
                width_rel = f"w{mp.ref_width}!=w{mp.rev_width}"
        diff_sigs = ()
        if mp.counterexample is not None:
            diff_sigs = tuple(_strip_index(s) for s in mp.counterexample.diff_signals())
        cone = tuple(sorted({_strip_index(s) for s in mp.fanin_signals}))
        base = _strip_index(mp.name)
        return "|".join(
            [
                mp.kind.value,
                width_rel,
                base,
                ",".join(sorted(set(diff_sigs))),
                ",".join(cone),
            ]
        )

    def group_signatures(self) -> list[MismatchGroup]:
        groups: dict[str, MismatchGroup] = {}
        for mp in self.log.mismatches:
            sig = self.signature(mp)
            g = groups.get(sig)
            if g is None:
                g = MismatchGroup(
                    signature=sig,
                    kind=mp.kind,
                    width_ref=mp.ref_width,
                    width_rev=mp.rev_width,
                )
                groups[sig] = g
            g.members.append(mp.name)
            for s in mp.fanin_signals:
                if s not in g.cone_signals:
                    g.cone_signals.append(s)
            if mp.counterexample is not None:
                for s in mp.counterexample.diff_signals():
                    if s not in g.cone_signals:
                        g.cone_signals.append(s)
        # Deterministic order: largest group first, then signature.
        return sorted(groups.values(), key=lambda g: (-g.count, g.signature))

    # ------------------------------------------------------------------ #
    # Reset / init comparison                                            #
    # ------------------------------------------------------------------ #

    def compare_reset(self) -> ResetComparison:
        ref = self.ref_manifest.reset if self.ref_manifest else ResetInfo()
        rev = self.rev_manifest.reset if self.rev_manifest else ResetInfo()
        cmp = ResetComparison(reference=ref, revised=rev)

        cmp.polarity_differs = (
            ref.polarity != ResetPolarity.UNKNOWN
            and rev.polarity != ResetPolarity.UNKNOWN
            and ref.polarity != rev.polarity
        )
        cmp.sync_differs = (
            ref.sync != ResetSync.UNKNOWN
            and rev.sync != ResetSync.UNKNOWN
            and ref.sync != rev.sync
        )
        for sig in sorted(set(ref.init_values) | set(rev.init_values)):
            rv = ref.init_values.get(sig)
            xv = rev.init_values.get(sig)
            if rv != xv:
                cmp.init_value_diffs[sig] = f"ref={rv} != rev={xv}"

        if cmp.polarity_differs:
            cmp.notes.append(
                f"Reset polarity differs: ref={ref.polarity.value}, "
                f"rev={rev.polarity.value}."
            )
        if cmp.sync_differs:
            cmp.notes.append(
                f"Reset synchronization differs: ref={ref.sync.value}, "
                f"rev={rev.sync.value}."
            )
        if not cmp.notes and (
            ref.polarity == ResetPolarity.UNKNOWN or rev.polarity == ResetPolarity.UNKNOWN
        ):
            cmp.notes.append(
                "Reset info incomplete in one or both manifests; comparison partial."
            )
        return cmp

    # ------------------------------------------------------------------ #
    # Likely-cause heuristics                                            #
    # ------------------------------------------------------------------ #

    def classify_causes(
        self, group: MismatchGroup, reset_cmp: ResetComparison
    ) -> list[LikelyCause]:
        causes: list[LikelyCause] = []

        # 1. WIDTH -- explicit width mismatch on the compare point.
        if (
            group.width_ref is not None
            and group.width_rev is not None
            and group.width_ref != group.width_rev
        ):
            causes.append(
                LikelyCause(
                    category=CauseCategory.WIDTH,
                    confidence=0.9,
                    rationale=[
                        f"Compare point width differs: ref={group.width_ref} "
                        f"bits vs rev={group.width_rev} bits."
                    ],
                    evidence_refs=[f"log:mismatch:{m}" for m in group.members],
                )
            )

        # 2. POLARITY -- CEX shows inverted values, or reset polarity differs
        #    and a reset-like signal is in the cone.
        inv = self._inverted_cex_evidence(group)
        cone_has_reset = any(
            any(h in s.lower() for h in _POLARITY_HINTS) for s in group.cone_signals
        )
        if inv:
            causes.append(
                LikelyCause(
                    category=CauseCategory.POLARITY,
                    confidence=0.75,
                    rationale=[
                        "Counterexample shows consistently inverted values "
                        f"({inv}); suggests polarity/inversion mismatch."
                    ],
                    evidence_refs=[f"cex:{group.members[0]}"],
                )
            )
        elif reset_cmp.polarity_differs and cone_has_reset:
            causes.append(
                LikelyCause(
                    category=CauseCategory.POLARITY,
                    confidence=0.6,
                    rationale=[
                        "Reset polarity differs between designs and a "
                        "reset-like signal is in the mismatch cone."
                    ],
                    evidence_refs=["reset_comparison"],
                )
            )

        # 3. GATING -- an enable/gating-like signal in the cone but not driving
        #    a width/polarity story.
        gating = [
            s
            for s in group.cone_signals
            if any(h in s.lower() for h in _GATING_HINTS)
        ]
        if gating:
            causes.append(
                LikelyCause(
                    category=CauseCategory.GATING,
                    confidence=0.55,
                    rationale=[
                        "Enable/gating-like signal(s) in cone: "
                        + ", ".join(sorted(gating))
                        + " -- check clock-gating / enable-condition changes."
                    ],
                    evidence_refs=[f"cone:{s}" for s in sorted(gating)],
                )
            )

        # 4. RESET/INIT -- reset behavior differs and mismatch appears early.
        if (reset_cmp.polarity_differs or reset_cmp.sync_differs) or (
            reset_cmp.init_value_diffs and self._mismatch_at_time_zero(group)
        ):
            causes.append(
                LikelyCause(
                    category=CauseCategory.RESET_INIT,
                    confidence=0.6 if self._mismatch_at_time_zero(group) else 0.4,
                    rationale=[
                        "Reset/init behavior differs between designs"
                        + (
                            " and first difference occurs at t=0."
                            if self._mismatch_at_time_zero(group)
                            else "."
                        )
                    ],
                    evidence_refs=["reset_comparison"],
                )
            )

        # 5. STATE_ENCODING -- FSM/state compare point with differing encoding.
        enc = self._state_encoding_evidence(group)
        if enc:
            causes.append(
                LikelyCause(
                    category=CauseCategory.STATE_ENCODING,
                    confidence=0.65,
                    rationale=[enc],
                    evidence_refs=["manifest:state_encoding"],
                )
            )

        # 6. CONFIG / CONSTRAINT -- surfaced whenever a real config delta exists.
        real_deltas = [d for d in self.log.config_deltas if d.differs]
        if real_deltas:
            causes.append(
                LikelyCause(
                    category=CauseCategory.CONFIG_CONSTRAINT,
                    confidence=0.5,
                    rationale=[
                        "Run configuration/constraints differ ("
                        + ", ".join(d.key for d in real_deltas)
                        + "); mismatches may be an artifact of setup, not RTL."
                    ],
                    evidence_refs=[f"config:{d.key}" for d in real_deltas],
                )
            )

        # 7. OPTIMIZATION -- fallback when the cone is small, widths match, and
        #    no stronger cause fired (e.g. a redundant/constant-folded node).
        if not causes and group.kind in {MismatchKind.STATE, MismatchKind.CUTPOINT}:
            causes.append(
                LikelyCause(
                    category=CauseCategory.OPTIMIZATION,
                    confidence=0.35,
                    rationale=[
                        "Internal state/cutpoint mismatch with no width/"
                        "polarity/reset signal; may be a synthesis optimization "
                        "(retiming, constant folding, redundancy removal)."
                    ],
                    evidence_refs=[f"log:mismatch:{group.members[0]}"],
                )
            )

        if not causes:
            causes.append(
                LikelyCause(
                    category=CauseCategory.UNKNOWN,
                    confidence=0.2,
                    rationale=["No specific heuristic matched; manual review needed."],
                )
            )

        return sorted(causes, key=lambda c: (-c.confidence, c.category.value))

    def _inverted_cex_evidence(self, group: MismatchGroup) -> str | None:
        """Return a short description if CEX values look bit-inverted."""
        for name in group.members:
            mp = self._mismatch_by_name(name)
            if mp is None or mp.counterexample is None:
                continue
            pairs = [
                (v.ref_value, v.rev_value)
                for v in mp.counterexample.vectors
                if v.differs and v.signal == (mp.rev_signal or v.signal)
            ] or [
                (v.ref_value, v.rev_value)
                for v in mp.counterexample.vectors
                if v.differs
            ]
            binary = [
                (r, x)
                for r, x in pairs
                if r in {"0", "1"} and x in {"0", "1"}
            ]
            if binary and all(r != x for r, x in binary):
                return f"{len(binary)} bit-pairs inverted"
        return None

    def _state_encoding_evidence(self, group: MismatchGroup) -> str | None:
        if not (self.ref_manifest and self.rev_manifest):
            return None
        for sig in group.cone_signals + group.members:
            base = _strip_index(sig)
            r = self.ref_manifest.state_encoding.get(base)
            x = self.rev_manifest.state_encoding.get(base)
            if r and x and r != x:
                return f"State signal '{base}' encoding differs: ref={r}, rev={x}."
        return None

    def _mismatch_at_time_zero(self, group: MismatchGroup) -> bool:
        for name in group.members:
            mp = self._mismatch_by_name(name)
            if mp and mp.counterexample and mp.counterexample.first_diff_time == 0:
                return True
        return False

    def _mismatch_by_name(self, name: str) -> MismatchPoint | None:
        for mp in self.log.mismatches:
            if mp.name == name:
                return mp
        return None

    # ------------------------------------------------------------------ #
    # Location ranking                                                   #
    # ------------------------------------------------------------------ #

    def rank_locations(self, group: MismatchGroup) -> list[RankedLocation]:
        """Rank source locations in the cone for engineer review.

        Score = base(compare-point) + cone contribution + cause boosts.
        Signals that are direct compare points score highest; cone signals with
        a source-map entry score next; unmapped signals still appear but lower.
        """
        ranked: dict[tuple[str, str], RankedLocation] = {}

        def bump(signal: str, design: str, score: float, reason: str) -> None:
            key = (signal, design)
            entry = self.source_map.lookup(signal, design)
            rl = ranked.get(key)
            if rl is None:
                rl = RankedLocation(
                    signal=signal,
                    design=design,
                    location=entry.location if entry else None,
                    module=entry.module if entry else None,
                    score=0.0,
                )
                ranked[key] = rl
            rl.score += score
            if reason not in rl.reasons:
                rl.reasons.append(reason)

        for name in group.members:
            mp = self._mismatch_by_name(name)
            if mp is None:
                continue
            for design, sig in (
                ("reference", mp.ref_signal or name),
                ("revised", mp.rev_signal or name),
            ):
                bump(sig, design, 3.0, "direct compare point")

        for sig in group.cone_signals:
            for design in ("reference", "revised"):
                bump(sig, design, 1.0, "in mismatch cone")

        # Boost signals implicated by likely causes.
        for cause in group.likely_causes:
            for ref in cause.evidence_refs:
                if ref.startswith("cone:"):
                    s = ref.split(":", 1)[1]
                    for design in ("reference", "revised"):
                        bump(s, design, 0.5, f"implicated by {cause.category.value}")

        # Prefer mapped locations; drop unmapped duplicates that add no info by
        # scoring them but keeping deterministic ordering.
        out = sorted(
            ranked.values(),
            key=lambda r: (-r.score, r.design, r.signal),
        )
        # Keep only signals with either a location or a nonzero cone/compare role.
        return [r for r in out if r.score > 0]

    # ------------------------------------------------------------------ #
    # Debug packet                                                       #
    # ------------------------------------------------------------------ #

    def build_debug_packet(
        self, groups: list[MismatchGroup], repro_command: str, input_files: list[str]
    ) -> DebugPacket:
        focus_cps: list[str] = []
        focus_sigs: list[str] = []
        for g in groups[:3]:  # top groups by size
            focus_cps.extend(g.members[:4])
            for rl in g.ranked_locations[:3]:
                if rl.signal not in focus_sigs:
                    focus_sigs.append(rl.signal)

        steps = [
            "Re-run equivalence check with the same tool/version to confirm "
            "reproducibility.",
            "Inspect the ranked source locations for the top mismatch group.",
        ]
        if any(d.differs for d in self.log.config_deltas):
            steps.insert(
                0,
                "Reconcile configuration/constraint differences BEFORE debugging "
                "RTL -- mismatches may be a setup artifact.",
            )
        if any(
            c.category in {CauseCategory.RESET_INIT, CauseCategory.POLARITY}
            for g in groups
            for c in g.likely_causes
        ):
            steps.append(
                "Compare reset/init sequences of both designs on the failing "
                "compare points."
            )

        return DebugPacket(
            repro_command=repro_command,
            input_files=input_files,
            focus_compare_points=focus_cps,
            focus_signals=focus_sigs,
            suggested_next_steps=steps,
        )

    # ------------------------------------------------------------------ #
    # Orchestration                                                      #
    # ------------------------------------------------------------------ #

    def run(
        self,
        provenance: Provenance,
        repro_command: str = "",
        input_files: list[str] | None = None,
    ) -> TriageReport:
        input_files = input_files or []
        reset_cmp = self.compare_reset()
        groups = self.group_signatures()
        for g in groups:
            g.likely_causes = self.classify_causes(g, reset_cmp)
            g.ranked_locations = self.rank_locations(g)

        warnings: list[str] = []
        if self.log.status in {
            EquivalenceStatus.TIMEOUT,
            EquivalenceStatus.INCONCLUSIVE,
            EquivalenceStatus.ERROR,
            EquivalenceStatus.ABORTED,
        }:
            warnings.append(
                f"Tool status is {self.log.status.value}; mismatch localization is "
                "advisory only. Do NOT treat as a non-equivalence proof."
            )
        if any(d.differs for d in self.log.config_deltas):
            warnings.append(
                "Configuration/constraint differences detected between runs; "
                "these are surfaced in config_deltas and may explain mismatches."
            )

        report = TriageReport(
            provenance=provenance,
            reported_status=self.log.status,
            status_evidence=self._status_evidence(),
            reference_design=self.log.reference_design,
            revised_design=self.log.revised_design,
            compare_points_total=self.log.compare_points_total,
            compare_points_matched=self.log.compare_points_matched,
            mismatch_count=len(self.log.mismatches),
            config_deltas=list(self.log.config_deltas),
            reset_comparison=reset_cmp,
            groups=groups,
            warnings=warnings,
        )
        report.debug_packet = self.build_debug_packet(
            groups, repro_command, input_files
        )
        return report

    def _status_evidence(self) -> list[str]:
        loc = self.log.raw_log_path or "<log>"
        ev = [f"{loc}: status: {self.log.status.value}"]
        ev.append(
            f"{loc}: compare_points: "
            f"{self.log.compare_points_matched}/{self.log.compare_points_total}"
        )
        return ev


def _strip_index(name: str) -> str:
    """Strip a trailing ``[n]`` bit index so ``out[0]`` -> ``out``."""
    idx = name.find("[")
    return name[:idx] if idx != -1 else name
