"""Deterministic coverage-hole triage engine.

This module is the *deterministic baseline classifier* required by spec 6.1 --
it runs before (and independently of) any LLM reasoning. Given the typed
:class:`TriageInputs`, it:

1. finds every uncovered coverage item (a "hole");
2. classifies each hole into a :class:`HoleCategory` using only evidence drawn
   from the inputs;
3. attaches root-cause hypotheses and cited evidence;
4. ranks next actions drawn *exclusively* from :class:`AllowedAction`;
5. estimates expected impact (as an explicit hypothesis, never a guarantee);
6. builds the independent-measurement manifest and human-review queue.

The engine is pure and deterministic: same inputs -> byte-identical report.
Ordering is stable (sorted by coverage_id) so golden tests are reliable.
"""

from __future__ import annotations

import hashlib
import json

from . import __version__
from .models import (
    AllowedAction,
    CoverageItem,
    CoverageKind,
    Evidence,
    HoleCategory,
    HoleClassification,
    HoleLabel,
    HumanReviewItem,
    IndependentMeasurementStep,
    Recommendation,
    SampleLabels,
    ScopeProvenance,
    TestEntry,
    TestStatus,
    TriageInputs,
    TriageMetrics,
    TriageReport,
)

# Base priority per action type; combined with per-hole modifiers when ranking.
# Ordering encodes "cheapest, highest-certainty first": re-running an existing
# passing-path test is the lowest-effort action, spec clarification the highest.
_ACTION_BASE_PRIORITY: dict[AllowedAction, float] = {
    AllowedAction.RUN_EXISTING_TEST: 0.90,
    AllowedAction.INSPECT_UNREACHABLE_CODE: 0.80,
    AllowedAction.ADD_DIRECTED_TEST: 0.70,
    AllowedAction.ADD_COVER_PROPERTY: 0.65,
    AllowedAction.ADD_CONSTRAINED_RANDOM_SCENARIO: 0.55,
    AllowedAction.PROPOSE_ASSERTION_CANDIDATE: 0.50,
    AllowedAction.REQUEST_WAIVER_REVIEW: 0.40,
    AllowedAction.REQUEST_SPEC_CLARIFICATION: 0.30,
}


class TriageEngine:
    """Deterministic baseline classifier + ranker. No network, no LLM."""

    def __init__(self, seed: int = 0) -> None:
        # ``seed`` is recorded for provenance; the baseline is deterministic and
        # does not actually sample, but the field keeps the run ledger honest and
        # forward-compatible with a future randomized/LLM policy.
        self.seed = seed

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------
    def _build_indexes(self, inputs: TriageInputs) -> None:
        self._tests_by_id: dict[str, TestEntry] = {t.test_id: t for t in inputs.tests.tests}

        # coverage_id -> set of test_ids intended to hit it (from test manifest)
        self._tests_for_cov: dict[str, set[str]] = {}
        for t in inputs.tests.tests:
            for cov in t.covers:
                self._tests_for_cov.setdefault(cov, set()).add(t.test_id)

        # coverage_id -> set of requirement_ids mapping to it
        self._reqs_for_cov: dict[str, set[str]] = {}
        for link in inputs.requirements.links:
            for cov in link.covers:
                self._reqs_for_cov.setdefault(cov, set()).add(link.requirement_id)

        # test_id -> log entries
        self._logs_for_test: dict[str, list] = {}
        for entry in inputs.logs.entries:
            self._logs_for_test.setdefault(entry.test_id, []).append(entry)

        # module -> dead-code line hints
        self._dead_lines: dict[str, set[int]] = {
            m.name: set(m.dead_code_hints) for m in inputs.rtl.modules
        }
        self._known_modules: set[str] = {m.name for m in inputs.rtl.modules}

    # ------------------------------------------------------------------
    # Classification of a single hole
    # ------------------------------------------------------------------
    def _classify_hole(self, item: CoverageItem) -> HoleClassification:
        evidence: list[Evidence] = []
        hypotheses: list[str] = []

        linked_tests = sorted(self._tests_for_cov.get(item.coverage_id, set()))
        linked_reqs = sorted(self._reqs_for_cov.get(item.coverage_id, set()))
        dead_hint = (
            item.source_line is not None
            and item.source_line in self._dead_lines.get(item.module, set())
        )

        # Evidence: coverage status is always cited.
        evidence.append(
            Evidence(
                source="coverage_db",
                detail=f"{item.coverage_id} has hits={item.hits} (goal={item.goal}) -> uncovered",
                ref=item.coverage_id,
            )
        )

        # --- deterministic decision tree -----------------------------------
        category = HoleCategory.UNKNOWN

        if dead_hint or item.exclusion_pragma:
            category = HoleCategory.LIKELY_UNREACHABLE
            if dead_hint:
                evidence.append(
                    Evidence(
                        source="rtl_intent_manifest",
                        detail=f"{item.module}:{item.source_line} flagged as likely-unreachable",
                        ref=f"{item.module}:{item.source_line}",
                    )
                )
            if item.exclusion_pragma:
                evidence.append(
                    Evidence(
                        source="coverage_db",
                        detail=f"{item.coverage_id} carries a coverage-exclusion pragma",
                        ref=item.coverage_id,
                    )
                )
            hypotheses.append(
                "Point may be structurally unreachable; inspect before proposing tests."
            )

        elif not linked_tests:
            category = HoleCategory.NO_LINKED_TEST
            evidence.append(
                Evidence(
                    source="test_manifest",
                    detail=f"No test lists {item.coverage_id} in its 'covers' set",
                    ref=item.coverage_id,
                )
            )
            hypotheses.append("No test is even intended to reach this point (testplan gap).")
            if not linked_reqs:
                hypotheses.append("No requirement maps to this point either (spec/plan gap).")

        else:
            # There are linked tests -- inspect their run status.
            statuses = {tid: self._tests_by_id.get(tid) for tid in linked_tests}
            not_run = [tid for tid, t in statuses.items() if t and t.status == TestStatus.NOT_RUN]
            failed = [
                tid
                for tid, t in statuses.items()
                if t
                and t.status in (TestStatus.FAIL, TestStatus.TIMEOUT, TestStatus.ERROR)
            ]
            passed = [tid for tid, t in statuses.items() if t and t.status == TestStatus.PASS]

            if failed:
                category = HoleCategory.TEST_RAN_BUT_FAILED
                for tid in failed:
                    st = statuses[tid].status.value if statuses[tid] else "unknown"
                    evidence.append(
                        Evidence(
                            source="test_manifest",
                            detail=f"Linked test {tid} finished with status={st} (not a pass)",
                            ref=tid,
                        )
                    )
                    for log in self._logs_for_test.get(tid, []):
                        evidence.append(
                            Evidence(
                                source="failure_log",
                                detail=f"{tid}: {log.kind}: {log.message}",
                                ref=(
                                    f"{log.source_file}:{log.source_line}"
                                    if log.source_file
                                    else tid
                                ),
                            )
                        )
                hypotheses.append(
                    "Coverage may be blocked by a failing/aborted test; fix the failure first."
                )

            elif not_run and not passed:
                category = HoleCategory.TEST_EXISTS_NOT_RUN
                for tid in not_run:
                    evidence.append(
                        Evidence(
                            source="test_manifest",
                            detail=f"Linked test {tid} has status=not_run",
                            ref=tid,
                        )
                    )
                hypotheses.append("A test targeting this point exists but was never executed.")

            else:
                # At least one linked test passed yet the point is still uncovered.
                category = HoleCategory.TEST_RAN_STILL_UNCOVERED
                for tid in passed:
                    evidence.append(
                        Evidence(
                            source="test_manifest",
                            detail=(
                                f"Linked test {tid} passed but "
                                f"{item.coverage_id} still uncovered"
                            ),
                            ref=tid,
                        )
                    )
                hypotheses.append(
                    "Stimulus does not exercise this point; needs directed/constrained-random work."
                )

        # Requirement-mapping evidence (independent of category above).
        if not linked_reqs:
            evidence.append(
                Evidence(
                    source="requirement_matrix",
                    detail=f"No requirement maps to {item.coverage_id}",
                    ref=item.coverage_id,
                )
            )
            # Only *promote* to NO_REQUIREMENT_MAPPING when nothing else is actionable.
            if category == HoleCategory.UNKNOWN:
                category = HoleCategory.NO_REQUIREMENT_MAPPING
        else:
            evidence.append(
                Evidence(
                    source="requirement_matrix",
                    detail=f"{item.coverage_id} maps to requirements {linked_reqs}",
                    ref=item.coverage_id,
                )
            )

        recommendations = self._rank_actions(item, category, linked_tests, linked_reqs)

        # Provenance is complete when we have cited evidence for status, tests,
        # and requirement mapping, and at least one recommendation.
        provenance_complete = (
            len(evidence) >= 2
            and len(hypotheses) >= 1
            and len(recommendations) >= 1
        )

        return HoleClassification(
            coverage_id=item.coverage_id,
            kind=item.kind,
            module=item.module,
            category=category,
            is_heuristic=True,
            root_cause_hypotheses=hypotheses,
            evidence=evidence,
            recommendations=recommendations,
            provenance_complete=provenance_complete,
        )

    # ------------------------------------------------------------------
    # Ranked action selection (only from AllowedAction)
    # ------------------------------------------------------------------
    def _rank_actions(
        self,
        item: CoverageItem,
        category: HoleCategory,
        linked_tests: list[str],
        linked_reqs: list[str],
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []

        def add(action: AllowedAction, rationale: str, impact: int, detail: str, note: str) -> None:
            recs.append(
                Recommendation(
                    action=action,
                    rationale=rationale,
                    priority_score=_ACTION_BASE_PRIORITY[action],
                    expected_impact_items=impact,
                    expected_impact_note=note,
                    detail=detail,
                    requires_human_approval=True,
                )
            )

        impact_note = "Hypothesis only; must be confirmed by independent coverage re-measurement."

        if category == HoleCategory.LIKELY_UNREACHABLE:
            add(
                AllowedAction.INSPECT_UNREACHABLE_CODE,
                "Point is flagged likely-unreachable; confirm before spending test effort.",
                0,
                f"Inspect {item.module} around line {item.source_line} for reachability.",
                impact_note,
            )
            add(
                AllowedAction.REQUEST_WAIVER_REVIEW,
                "If confirmed unreachable, a human may review a waiver (agent never waives).",
                1,
                f"Route {item.coverage_id} to a waiver reviewer with the reachability finding.",
                impact_note,
            )

        elif category == HoleCategory.TEST_EXISTS_NOT_RUN:
            for tid in linked_tests:
                t = self._tests_by_id.get(tid)
                seed = t.seed if t and t.seed is not None else "<pick a seed>"
                cfg = t.config if t and t.config else "<default>"
                add(
                    AllowedAction.RUN_EXISTING_TEST,
                    f"Test {tid} targets this point but was never run.",
                    1,
                    f"Run test {tid} with seed={seed} config={cfg}.",
                    impact_note,
                )

        elif category == HoleCategory.TEST_RAN_BUT_FAILED:
            add(
                AllowedAction.RUN_EXISTING_TEST,
                "Re-run the failing linked test after the failure is triaged (by a human).",
                1,
                f"After fix, re-run {linked_tests[0]} and re-measure coverage.",
                impact_note,
            )
            add(
                AllowedAction.REQUEST_SPEC_CLARIFICATION,
                "If the failure is a spec ambiguity, clarify intent before re-testing.",
                0,
                f"Ask spec owner whether {item.coverage_id} behavior is as intended.",
                impact_note,
            )

        elif category == HoleCategory.TEST_RAN_STILL_UNCOVERED:
            add(
                AllowedAction.ADD_DIRECTED_TEST,
                "Passing test does not reach this point; a directed test likely will.",
                1,
                f"Draft a directed test hitting {item.description or item.coverage_id}.",
                impact_note,
            )
            add(
                AllowedAction.ADD_CONSTRAINED_RANDOM_SCENARIO,
                "Alternatively widen constrained-random stimulus to reach the point.",
                1,
                f"Add a CR scenario biasing toward {item.kind.value} in {item.module}.",
                impact_note,
            )
            if item.kind == CoverageKind.ASSERTION:
                add(
                    AllowedAction.PROPOSE_ASSERTION_CANDIDATE,
                    "Assertion coverage suggests a candidate property for human review.",
                    1,
                    f"Propose an assertion for {item.description or item.coverage_id}.",
                    impact_note,
                )

        elif category == HoleCategory.NO_LINKED_TEST:
            add(
                AllowedAction.ADD_DIRECTED_TEST,
                "No test targets this point; add a directed test to close the plan gap.",
                1,
                f"Create a directed test for {item.description or item.coverage_id}.",
                impact_note,
            )
            add(
                AllowedAction.ADD_COVER_PROPERTY,
                "Add a cover property to make reaching this point observable.",
                1,
                f"Add a cover for {item.coverage_id} in {item.module}.",
                impact_note,
            )
            if not linked_reqs:
                add(
                    AllowedAction.REQUEST_SPEC_CLARIFICATION,
                    "No requirement maps here; confirm whether the point should be covered.",
                    0,
                    f"Ask whether {item.coverage_id} is in scope for this release.",
                    impact_note,
                )

        elif category == HoleCategory.NO_REQUIREMENT_MAPPING:
            add(
                AllowedAction.REQUEST_SPEC_CLARIFICATION,
                "Point has no requirement mapping; clarify intended coverage scope.",
                0,
                f"Confirm requirement ownership for {item.coverage_id}.",
                impact_note,
            )
            add(
                AllowedAction.ADD_DIRECTED_TEST,
                "If in scope, add a directed test after requirement is confirmed.",
                1,
                f"Directed test for {item.coverage_id} pending requirement confirmation.",
                impact_note,
            )

        else:  # UNKNOWN / WAIVER_CANDIDATE fallthrough
            add(
                AllowedAction.REQUEST_SPEC_CLARIFICATION,
                "Insufficient evidence to classify; escalate for human clarification.",
                0,
                f"Escalate {item.coverage_id}: cause unclear from available inputs.",
                impact_note,
            )

        # Stable ranking: priority desc, then action name for determinism.
        recs.sort(key=lambda r: (-r.priority_score, r.action.value, r.detail))
        return recs

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self, inputs: TriageInputs) -> TriageReport:
        self._build_indexes(inputs)

        holes = [it for it in inputs.coverage.items if not it.is_covered]
        holes.sort(key=lambda it: it.coverage_id)

        classifications = [self._classify_hole(it) for it in holes]

        independent = [
            IndependentMeasurementStep(
                coverage_id=c.coverage_id,
                instruction=(
                    f"After approved actions for {c.coverage_id}, re-export the coverage DB "
                    "and confirm the item is covered. "
                    "The agent does not and cannot mark it closed."
                ),
            )
            for c in classifications
        ]

        review_queue = [
            HumanReviewItem(
                coverage_id=c.coverage_id,
                reason=(
                    f"Heuristic category '{c.category.value}' with "
                    f"{len(c.recommendations)} proposed action(s) require human approval."
                ),
                recommendations=[r.action for r in c.recommendations],
            )
            for c in classifications
        ]

        provenance = ScopeProvenance(
            tool_version=__version__,
            input_hashes=_hash_inputs(inputs),
            seed=self.seed,
            coverage_format=inputs.coverage.format_version,
            total_items=len(inputs.coverage.items),
            total_holes=len(holes),
        )

        metrics = compute_metrics(classifications, sample=None)

        return TriageReport(
            classifications=classifications,
            independent_measurement=independent,
            human_review_queue=review_queue,
            scope_provenance=provenance,
            metrics=metrics,
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(
    classifications: list[HoleClassification],
    sample: SampleLabels | None,
) -> TriageMetrics:
    """Compute run metrics; sample-based metrics only when labels are supplied.

    * valid_proposal_rate    -- fraction of recommendations whose action is in
      the allowed set (always 1.0 by construction; measured, not assumed).
    * provenance_completeness -- fraction of classifications with complete,
      cited provenance.
    * accepted_proposal_rate  -- (sample) fraction of proposed actions a
      reviewer accepted.
    * false_positive_proposal_rate -- (sample) fraction of proposed actions a
      reviewer explicitly rejected.
    * category_precision      -- (sample) fraction of holes whose predicted
      category matches the ground-truth label.
    """
    total_holes = len(classifications)
    all_recs = [r for c in classifications for r in c.recommendations]
    total_recs = len(all_recs)

    valid = sum(1 for r in all_recs if r.action in AllowedAction)
    valid_rate = (valid / total_recs) if total_recs else 1.0

    prov_complete = sum(1 for c in classifications if c.provenance_complete)
    prov_rate = (prov_complete / total_holes) if total_holes else 1.0

    metrics = TriageMetrics(
        total_holes=total_holes,
        total_recommendations=total_recs,
        valid_proposal_rate=valid_rate,
        provenance_completeness=prov_rate,
    )

    if sample is not None and sample.labels:
        by_id = {c.coverage_id: c for c in classifications}
        label_map: dict[str, HoleLabel] = {lbl.coverage_id: lbl for lbl in sample.labels}

        accepted = 0
        rejected = 0
        proposed_in_sample = 0
        correct_cat = 0
        counted = 0

        for cov_id, lbl in label_map.items():
            cls = by_id.get(cov_id)
            if cls is None:
                continue
            counted += 1
            if cls.category == lbl.true_category:
                correct_cat += 1
            proposed_actions = {r.action for r in cls.recommendations}
            proposed_in_sample += len(proposed_actions)
            accepted += len(proposed_actions & set(lbl.proposals_accepted))
            rejected += len(proposed_actions & set(lbl.proposals_rejected))

        metrics.sample_size = counted
        if proposed_in_sample:
            metrics.accepted_proposal_rate = accepted / proposed_in_sample
            metrics.false_positive_proposal_rate = rejected / proposed_in_sample
        if counted:
            metrics.category_precision = correct_cat / counted

    return metrics


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


def _hash_inputs(inputs: TriageInputs) -> dict[str, str]:
    """Stable content hashes of each input sub-document for the run ledger."""

    def h(obj) -> str:
        payload = json.dumps(
            obj.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        return "sha256:" + hashlib.sha256(payload).hexdigest()[:16]

    return {
        "coverage": h(inputs.coverage),
        "tests": h(inputs.tests),
        "rtl": h(inputs.rtl),
        "requirements": h(inputs.requirements),
        "logs": h(inputs.logs),
    }
