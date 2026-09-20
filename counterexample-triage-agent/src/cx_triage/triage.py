"""Deterministic counterexample triage engine.

Given a parsed trace, a structured assertion-failure record, and an RTL Intent
Manifest, this module extracts *evidence* and produces a
:class:`~cx_triage.models.TriageReport`. Every field is derived from the trace
and manifest -- nothing is invented.

Authority boundary (enforced in code and documented in ARCHITECTURE.md):

* This engine never modifies RTL, assertions, or the trace.
* It never asserts a design bug without trace-grounded evidence (the model layer
  additionally rejects an evidence-free design_bug hypothesis).
* It always keeps alternative hypotheses (property / environment / reset /
  modeling) alongside any design-bug hypothesis.
* A failing property is never treated as *necessarily* a design bug.
"""

from __future__ import annotations

from .models import (
    AssertionFailure,
    HypothesisCategory,
    ImplicationStyle,
    ReproInfo,
    RootCauseHypothesis,
    RTLIntentManifest,
    SourceCitation,
    SourceLocation,
    TimelineEvent,
    TriageReport,
    WaveTrace,
)


def _is_true(value: str | None) -> bool:
    """A scalar signal is 'true' when it is exactly '1'. x/z/None are not true."""
    return value == "1"


def _reset_active(value: str | None, active_high: bool) -> bool:
    if value is None:
        return False
    if value in ("x", "z"):
        return False
    return (value == "1") if active_high else (value == "0")


def _clock_edge_times(trace: WaveTrace, clock: str, edge: str) -> list[int]:
    """Return times at which the clock makes the requested edge, in order."""
    sig = trace.signal(clock)
    if sig is None:
        return []
    times: list[int] = []
    prev: str | None = None
    for s in sig.samples:
        if prev is not None:
            if edge == "posedge" and prev != "1" and s.value == "1":
                times.append(s.time)
            elif edge == "negedge" and prev != "0" and s.value == "0":
                times.append(s.time)
        prev = s.value
    return times


class TriageEngine:
    """Produces a deterministic triage report from evidence."""

    def __init__(
        self,
        trace: WaveTrace,
        failure: AssertionFailure,
        manifest: RTLIntentManifest | None = None,
    ) -> None:
        self.trace = trace
        self.failure = failure
        self.manifest = manifest

    # -- cone of influence -------------------------------------------------

    def compute_cone(self) -> list[str]:
        """Backward reachability from consequent/antecedent through ``drivers``.

        This is a real graph traversal over the manifest's dependency edges. It
        is a heuristic structural cone (labeled as such in the report), not a
        sound formal reduction.
        """
        if self.manifest is None:
            return []
        seeds = [
            s
            for s in (self.failure.consequent_signal, self.failure.antecedent_signal)
            if s
        ]
        seen: set[str] = set()
        order: list[str] = []
        stack = list(seeds)
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            order.append(name)
            sym = self.manifest.symbol(name)
            if sym is None:
                continue
            for drv in sym.drivers:
                if drv not in seen:
                    stack.append(drv)
        # Deterministic ordering: BFS-ish discovery order is already stable given
        # sorted drivers upstream; sort for absolute determinism.
        return sorted(order)

    # -- antecedent activation & first divergence --------------------------

    def find_antecedent_cycle(self, edge_times: list[int]) -> tuple[int | None, int | None]:
        ant = self.failure.antecedent_signal
        if ant is None:
            return None, None
        sig = self.trace.signal(ant)
        if sig is None:
            return None, None
        for cycle, t in enumerate(edge_times):
            if self._reset_at(t):
                continue
            if _is_true(sig.value_at(t)):
                return cycle, t
        return None, None

    def _reset_at(self, time: int) -> bool:
        if self.failure.reset is None:
            return False
        rsig = self.trace.signal(self.failure.reset)
        if rsig is None:
            return False
        return _reset_active(rsig.value_at(time), self.failure.reset_active_high)

    def find_first_divergence(
        self, edge_times: list[int], antecedent_cycle: int | None
    ) -> tuple[int | None, int | None]:
        """Locate the first cycle where the consequent fails as required.

        For an implication ``antecedent |-> ##[min:max] consequent`` we look, for
        every activating antecedent, at whether the consequent holds within the
        [min,max] window. The first activation whose window contains no holding
        consequent is the divergence.

        For a plain invariant (no antecedent), the first cycle at which the
        consequent is not '1' (and reset is inactive) is the divergence.
        """
        cons = self.failure.consequent_signal
        if cons is None:
            return None, None
        csig = self.trace.signal(cons)
        if csig is None:
            return None, None

        ant = self.failure.antecedent_signal
        if ant is None:
            # Invariant style.
            for cycle, t in enumerate(edge_times):
                if self._reset_at(t):
                    continue
                if not _is_true(csig.value_at(t)):
                    return cycle, t
            return None, None

        asig = self.trace.signal(ant)
        if asig is None:
            return None, None

        # Non-overlapping (|=>) checks the consequent starting the cycle AFTER the
        # antecedent, so the effective window minimum is shifted up by 1. For an
        # overlapping (|->) implication the window starts at the antecedent cycle.
        base = 1 if self.failure.implication == ImplicationStyle.NON_OVERLAPPING else 0

        start = antecedent_cycle if antecedent_cycle is not None else 0
        for cycle in range(start, len(edge_times)):
            t = edge_times[cycle]
            if self._reset_at(t):
                continue
            if not _is_true(asig.value_at(t)):
                continue
            # antecedent active at this cycle; check the response window
            lo = cycle + max(base, self.failure.delay_min)
            hi = cycle + max(base, self.failure.delay_max)
            held = False
            for wc in range(lo, hi + 1):
                if wc >= len(edge_times):
                    # Response window runs off the end of the trace -> cannot
                    # confirm the consequent; this is unresolved, not a failure.
                    held = True  # avoid false "divergence" past trace end
                    break
                if _is_true(csig.value_at(edge_times[wc])):
                    held = True
                    break
            if not held:
                # Divergence is where the consequent should have held but didn't:
                # report the first cycle in the window inside the trace.
                div_cycle = min(lo, len(edge_times) - 1)
                return div_cycle, edge_times[div_cycle]
        return None, None

    # -- timeline ----------------------------------------------------------

    def build_timeline(
        self,
        edge_times: list[int],
        antecedent_cycle: int | None,
        divergence_cycle: int | None,
    ) -> list[TimelineEvent]:
        f = self.failure
        watch = [
            s
            for s in (f.reset, f.antecedent_signal, f.consequent_signal, f.clock)
            if s
        ]
        # Include cone signals for richer context (bounded to keep it readable).
        events: list[TimelineEvent] = []
        for cycle, t in enumerate(edge_times):
            sig_vals: dict[str, str] = {}
            for name in watch:
                sig = self.trace.signal(name)
                if sig is not None:
                    v = sig.value_at(t)
                    if v is not None:
                        sig_vals[name] = v
            kind = "sample"
            desc_parts = []
            if self._reset_at(t):
                kind = "reset"
                desc_parts.append("reset active")
            if antecedent_cycle == cycle:
                kind = "antecedent"
                desc_parts.append(f"antecedent '{f.antecedent_signal}' activated")
            if divergence_cycle == cycle:
                kind = "divergence"
                desc_parts.append("consequent failed to hold within window")
            if f.failure_time is not None and t == f.failure_time:
                kind = "failure"
                desc_parts.append(f"tool-reported failure of '{f.property_name}'")
            desc = "; ".join(desc_parts) if desc_parts else "sampled clock edge"
            # Keep the timeline focused: always keep salient cycles; sample others.
            salient = kind != "sample" or cycle in _context_window(
                antecedent_cycle, divergence_cycle, len(edge_times)
            )
            if salient:
                events.append(
                    TimelineEvent(
                        cycle=cycle,
                        time=t,
                        kind=kind,
                        description=desc,
                        signals=sig_vals,
                    )
                )
        return events

    # -- citations ---------------------------------------------------------

    def build_citations(self, cone: list[str]) -> list[SourceCitation]:
        cites: list[SourceCitation] = [
            SourceCitation(
                file=self.failure.source_file,
                line=self.failure.source_line,
                symbol=self.failure.property_name,
                reason="Property whose failure is being triaged.",
            )
        ]
        if self.manifest is not None:
            for name in cone:
                sym = self.manifest.symbol(name)
                if sym is not None:
                    cites.append(
                        SourceCitation(
                            file=sym.location.file,
                            line=sym.location.line,
                            symbol=name,
                            reason=f"In cone of influence ({sym.kind}).",
                        )
                    )
        return cites

    # -- hypotheses --------------------------------------------------------

    def build_hypotheses(
        self,
        edge_times: list[int],
        antecedent_cycle: int | None,
        divergence_cycle: int | None,
        cone: list[str],
    ) -> tuple[list[RootCauseHypothesis], list[str]]:
        """Rank root-cause hypotheses with confidence + trace-grounded evidence.

        The ranking is a transparent, deterministic scoring heuristic (documented
        as heuristic). It deliberately keeps *all* plausible categories so that a
        design-bug conclusion is never presented as the only option.
        """
        f = self.failure
        hyps: list[RootCauseHypothesis] = []
        unresolved: list[str] = []

        cons = f.consequent_signal
        csig = self.trace.signal(cons) if cons else None
        ant = f.antecedent_signal
        asig = self.trace.signal(ant) if ant else None

        # Evidence gathering ------------------------------------------------
        reset_seen = False
        if f.reset is not None:
            rsig = self.trace.signal(f.reset)
            if rsig is not None:
                reset_seen = any(
                    _reset_active(s.value, f.reset_active_high) for s in rsig.samples
                )

        div_time = edge_times[divergence_cycle] if divergence_cycle is not None else None
        reset_at_div = self._reset_at(div_time) if div_time is not None else False

        cons_x_at_div = False
        if csig is not None and div_time is not None:
            cons_x_at_div = csig.value_at(div_time) in ("x", "z", None)

        antecedent_ever = False
        if asig is not None:
            antecedent_ever = any(_is_true(s.value) for s in asig.samples)

        missing_signals = [
            n
            for n in (f.antecedent_signal, f.consequent_signal, f.clock, f.reset)
            if n and self.trace.signal(n) is None
        ]

        # 1. Design-bug hypothesis (only with concrete evidence) ------------
        if (
            divergence_cycle is not None
            and not reset_at_div
            and not cons_x_at_div
            and antecedent_cycle is not None
        ):
            ev = [
                f"Antecedent '{ant}' activated at cycle {antecedent_cycle} "
                f"(time {edge_times[antecedent_cycle]}).",
                f"Consequent '{cons}' did NOT hold within the required "
                f"[{f.delay_min},{f.delay_max}] window; first divergence at "
                f"cycle {divergence_cycle} (time {div_time}).",
                f"Reset '{f.reset}' was inactive at the divergence cycle.",
                "Consequent value at divergence was a defined 0 (not x/z).",
            ]
            if cone:
                ev.append(f"Cone of influence: {', '.join(cone)}.")
            conf = 0.6
            if not reset_seen:
                conf += 0.05
            hyps.append(
                RootCauseHypothesis(
                    category=HypothesisCategory.DESIGN_BUG,
                    statement=(
                        f"Logic in the cone of '{cons}' fails to satisfy the "
                        f"property after '{ant}'. Inspect the cone drivers."
                    ),
                    confidence=round(min(conf, 0.75), 3),
                    evidence=ev,
                )
            )

        # 2. Property-issue hypothesis (always retained) --------------------
        prop_ev = []
        conf_prop = 0.3
        if f.implication == ImplicationStyle.NON_OVERLAPPING and f.delay_min == 0:
            prop_ev.append(
                "Non-overlapping implication with delay_min=0 is unusual; the "
                "intended timing window may be mis-specified."
            )
            conf_prop += 0.1
        if divergence_cycle is not None and antecedent_cycle is None:
            prop_ev.append(
                "A divergence was found without a clear antecedent activation; "
                "the antecedent may be mis-modeled or the property vacuously "
                "structured."
            )
            conf_prop += 0.1
        if not prop_ev:
            prop_ev.append(
                "The property text/timing bounds should be reviewed against the "
                "requirement to confirm [min,max] and implication style are correct."
            )
        hyps.append(
            RootCauseHypothesis(
                category=HypothesisCategory.PROPERTY_ISSUE,
                statement=(
                    "The property (timing window, implication style, or "
                    "antecedent/consequent choice) may not match design intent."
                ),
                confidence=round(min(conf_prop, 0.6), 3),
                evidence=prop_ev,
            )
        )

        # 3. Reset-issue hypothesis ----------------------------------------
        if reset_at_div or (f.reset is not None and not reset_seen):
            reset_ev = []
            conf_reset = 0.2
            if reset_at_div:
                reset_ev.append(
                    f"Reset '{f.reset}' was ACTIVE at the divergence cycle "
                    f"{divergence_cycle}; behavior during reset may be out of scope "
                    f"for this property (missing 'disable iff')."
                )
                conf_reset = 0.55
            if f.reset is not None and not reset_seen:
                reset_ev.append(
                    f"Reset '{f.reset}' never asserted in the trace; the DUT may "
                    f"start from an uninitialized state."
                )
                conf_reset = max(conf_reset, 0.4)
            hyps.append(
                RootCauseHypothesis(
                    category=HypothesisCategory.RESET_ISSUE,
                    statement=(
                        "Reset behavior may explain the failure (missing disable "
                        "iff, wrong polarity, or uninitialized start state)."
                    ),
                    confidence=round(conf_reset, 3),
                    evidence=reset_ev,
                )
            )

        # 4. Environment-issue hypothesis ----------------------------------
        if not antecedent_ever and ant is not None:
            hyps.append(
                RootCauseHypothesis(
                    category=HypothesisCategory.ENVIRONMENT_ISSUE,
                    statement=(
                        "The stimulus/environment may not exercise the property; "
                        "the antecedent never becomes true in this trace."
                    ),
                    confidence=0.45,
                    evidence=[
                        f"Antecedent '{ant}' is never '1' anywhere in the trace."
                    ],
                )
            )
            unresolved.append(
                f"Is '{ant}' expected to activate under the current testbench "
                f"constraints? If not, the counterexample may be an environment gap."
            )

        # 5. Modeling-issue hypothesis (x/z or missing signals) ------------
        model_ev = []
        conf_model = 0.15
        if cons_x_at_div:
            model_ev.append(
                f"Consequent '{cons}' is x/z at the divergence cycle; this often "
                f"indicates uninitialized state or a modeling/reset gap rather than "
                f"functional logic error."
            )
            conf_model = 0.5
        if missing_signals:
            model_ev.append(
                f"Signals referenced by the failure record are absent from the "
                f"trace: {', '.join(missing_signals)}."
            )
            conf_model = max(conf_model, 0.5)
            unresolved.append(
                f"Trace is missing {', '.join(missing_signals)}; re-dump with these "
                f"signals to complete triage."
            )
        if model_ev:
            hyps.append(
                RootCauseHypothesis(
                    category=HypothesisCategory.MODELING_ISSUE,
                    statement=(
                        "An x/z propagation or missing-signal modeling gap may "
                        "explain the failure independent of design logic."
                    ),
                    confidence=round(conf_model, 3),
                    evidence=model_ev,
                )
            )

        # Unresolved questions that always apply -----------------------------
        if divergence_cycle is None and antecedent_cycle is not None:
            unresolved.append(
                "Antecedent activated but no divergence was located within the "
                "trace; the consequent window may extend past the dumped window."
            )
        if antecedent_cycle is None and ant is not None and asig is not None:
            unresolved.append(
                f"Could not locate an antecedent activation for '{ant}' outside "
                f"reset; confirm the antecedent signal mapping."
            )

        # Deterministic ranking: confidence desc, then category name for ties.
        hyps.sort(key=lambda h: (-h.confidence, h.category.value))
        return hyps, unresolved

    # -- top-level ---------------------------------------------------------

    def run(self, repro_command: str, artifacts: list[str]) -> TriageReport:
        edge_times = _clock_edge_times(self.trace, self.failure.clock, self.failure.clock_edge)
        antecedent_cycle, antecedent_time = self.find_antecedent_cycle(edge_times)
        divergence_cycle, divergence_time = self.find_first_divergence(
            edge_times, antecedent_cycle
        )
        cone = self.compute_cone()
        timeline = self.build_timeline(edge_times, antecedent_cycle, divergence_cycle)
        citations = self.build_citations(cone)
        hypotheses, unresolved = self.build_hypotheses(
            edge_times, antecedent_cycle, divergence_cycle, cone
        )

        if not edge_times:
            unresolved.append(
                f"No {self.failure.clock_edge} edges found on clock "
                f"'{self.failure.clock}'; cycle indexing is unavailable."
            )

        return TriageReport(
            property_name=self.failure.property_name,
            property_text=self.failure.property_text,
            property_location=SourceLocation(
                file=self.failure.source_file, line=self.failure.source_line
            ),
            clock=self.failure.clock,
            reset=self.failure.reset,
            antecedent_cycle=antecedent_cycle,
            antecedent_time=antecedent_time,
            first_divergence_cycle=divergence_cycle,
            first_divergence_time=divergence_time,
            timeline=timeline,
            rtl_cone=cone,
            citations=citations,
            hypotheses=hypotheses,
            unresolved_questions=unresolved,
            reproduction=ReproInfo(command=repro_command, artifacts=artifacts),
        )


def _context_window(
    antecedent_cycle: int | None, divergence_cycle: int | None, n: int
) -> set[int]:
    """Cycles to always include in the timeline for context (+/- 1 around events)."""
    keep: set[int] = set()
    for c in (antecedent_cycle, divergence_cycle):
        if c is not None:
            for d in (-1, 0, 1):
                if 0 <= c + d < n:
                    keep.add(c + d)
    return keep
