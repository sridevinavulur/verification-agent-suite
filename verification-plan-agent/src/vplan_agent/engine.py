"""Deterministic verification-plan engine.

Given a :class:`SpecDocument`, an :class:`InterfaceGlossary`, an optional
:class:`ManifestView` and an optional :class:`ExistingTestplan`, this module
produces a complete :class:`VerificationPlan` draft using **deterministic rules
only**. The mock LLM is used solely to phrase assertion rationale.

Pipeline (each step is a pure function of its inputs):

1. classify + decompose requirements -> Features (keyword rules)
2. propose techniques per feature (category -> technique rules)
3. score risk + assign priority (weighted deterministic rubric)
4. generate scenarios, assertion sketches, coverage targets per feature
5. cross-check against interface glossary + manifest -> ambiguities
6. build the requirement -> tests -> coverage traceability matrix

Everything is emitted as ``ApprovalState.PROPOSED``; promotion to ``APPROVED``
happens only via :mod:`vplan_agent.approval`.

Determinism note: iteration order follows the input requirement order and
sorted signal names, so the output (and golden reports) are stable.
"""

from __future__ import annotations

import re

from .llm import LLMAdapter, MockLLM
from .models import Ambiguity as AmbiguityModel
from .models import (
    AmbiguityKind,
    ApprovalState,
    AssertionCandidate,
    Category,
    CoverageTarget,
    ExistingTestplan,
    Feature,
    InterfaceGlossary,
    ManifestView,
    PlanItem,
    Priority,
    Provenance,
    Requirement,
    SpecDocument,
    Technique,
    TestScenario,
    TraceRow,
    VerificationPlan,
)

# --------------------------------------------------------------------------- #
# 1. Classification rules
# --------------------------------------------------------------------------- #
# Ordered: first matching category wins. Order encodes precedence so that, e.g.,
# a "reset" mention is classified as RESET even if the word "data" also appears.
_CATEGORY_KEYWORDS: list[tuple[Category, tuple[str, ...]]] = [
    (Category.SECURITY, ("secure", "security", "access control", "privilege",
                         "encrypt", "tamper", "lock", "authenticat")),
    (Category.CDC_RDC, ("clock domain", "cdc", "rdc", "asynchronous clock",
                        "metastab", "synchroniz")),
    (Category.LOW_POWER, ("low power", "low-power", "power gating", "clock gating",
                          "retention", "sleep", "power domain", "upf")),
    (Category.RESET, ("reset", "power-on", "power on", "por", "initializ")),
    (Category.ERROR_HANDLING, ("error", "overflow", "underflow", "illegal",
                               "invalid", "fault", "timeout", "exception",
                               "parity", "ecc")),
    (Category.PERFORMANCE, ("throughput", "latency", "bandwidth", "performance",
                            "back-to-back", "back to back", "cycles per",
                            "stall", "rate")),
    (Category.INTEGRATION, ("integration", "top-level", "top level", "system",
                            "interconnect", "arbiter", "bus protocol", "end-to-end",
                            "end to end")),
]

# Techniques recommended per category (deterministic mapping).
_CATEGORY_TECHNIQUES: dict[Category, list[Technique]] = {
    Category.FUNCTIONAL: [Technique.DIRECTED_SIM, Technique.CONSTRAINED_RANDOM,
                          Technique.SVA, Technique.COVER],
    Category.PERFORMANCE: [Technique.CONSTRAINED_RANDOM, Technique.EMULATION,
                           Technique.COVER, Technique.POST_SILICON],
    Category.RESET: [Technique.DIRECTED_SIM, Technique.FORMAL, Technique.SVA],
    Category.ERROR_HANDLING: [Technique.DIRECTED_SIM, Technique.CONSTRAINED_RANDOM,
                              Technique.SVA, Technique.FORMAL],
    Category.SECURITY: [Technique.FORMAL, Technique.SVA, Technique.DIRECTED_SIM],
    Category.LOW_POWER: [Technique.DIRECTED_SIM, Technique.FORMAL, Technique.EMULATION],
    Category.CDC_RDC: [Technique.FORMAL, Technique.SVA, Technique.COVER],
    Category.INTEGRATION: [Technique.CONSTRAINED_RANDOM, Technique.EMULATION,
                           Technique.DIRECTED_SIM, Technique.POST_SILICON],
}

# Base risk contribution per category (0..100 scale, combined with modifiers).
_CATEGORY_BASE_RISK: dict[Category, int] = {
    Category.SECURITY: 55,
    Category.CDC_RDC: 50,
    Category.ERROR_HANDLING: 45,
    Category.RESET: 40,
    Category.INTEGRATION: 40,
    Category.PERFORMANCE: 35,
    Category.LOW_POWER: 35,
    Category.FUNCTIONAL: 30,
}


def _keyword_hit(keyword: str, haystack: str) -> bool:
    """Match ``keyword`` at a word boundary, allowing a trailing suffix.

    This treats short keywords as whole words (so ``lock`` does not match inside
    ``clock``) while still catching morphological variants like
    ``authenticat`` -> ``authenticated`` via the trailing ``\\w*``.
    """
    pattern = r"\b" + re.escape(keyword) + r"\w*"
    return re.search(pattern, haystack) is not None


def classify_requirement(req: Requirement) -> Category:
    """Deterministic keyword classification; defaults to FUNCTIONAL."""
    haystack = (req.text + " " + " ".join(req.tags)).lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw and _keyword_hit(kw, haystack):
                return category
    return Category.FUNCTIONAL


# --------------------------------------------------------------------------- #
# 2. Decompose requirements -> features
# --------------------------------------------------------------------------- #
def _feature_name(req: Requirement) -> str:
    text = req.text.strip().rstrip(".")
    words = text.split()
    return " ".join(words[:8]) + ("…" if len(words) > 8 else "")


def decompose(spec: SpecDocument) -> list[Feature]:
    features: list[Feature] = []
    for i, req in enumerate(spec.requirements, start=1):
        category = classify_requirement(req)
        features.append(
            Feature(
                id=f"FEAT-{i:03d}",
                name=_feature_name(req),
                category=category,
                description=req.text,
                source_requirements=[req.id],
                approval=ApprovalState.PROPOSED,
            )
        )
    return features


# --------------------------------------------------------------------------- #
# 3. Risk scoring
# --------------------------------------------------------------------------- #
def _risk_for_feature(
    feature: Feature, manifest: ManifestView
) -> tuple[int, list[str]]:
    base = _CATEGORY_BASE_RISK[feature.category]
    score = base
    rationale = [f"base risk for category '{feature.category.value}' = {base}"]

    text = feature.description.lower()

    # Modifier: explicit "must"/"shall" strong obligations raise risk.
    if any(w in text for w in ("must ", "shall ", "never", "always")):
        score += 10
        rationale.append("strong obligation keyword (+10)")

    # Modifier: designs with memory / many registers imply more state to cover.
    max_regs = max((m.register_count for m in manifest.modules), default=0)
    if feature.category is Category.FUNCTIONAL and max_regs >= 8:
        score += 8
        rationale.append(f"state-heavy design (max registers={max_regs}) (+8)")
    if any(m.has_memory for m in manifest.modules) and feature.category in (
        Category.FUNCTIONAL,
        Category.ERROR_HANDLING,
    ):
        score += 7
        rationale.append("design contains memory array (+7)")

    # Modifier: multiple clock candidates => CDC exposure raises risk.
    if feature.category is Category.CDC_RDC:
        clocks = {c for m in manifest.modules for c in m.clock_candidate_signals}
        if len(clocks) >= 2:
            score += 10
            rationale.append(f"{len(clocks)} clock candidates in manifest (+10)")

    score = max(0, min(100, score))
    return score, rationale


def _priority_from_score(score: int) -> Priority:
    if score >= 55:
        return Priority.P0
    if score >= 45:
        return Priority.P1
    if score >= 35:
        return Priority.P2
    return Priority.P3


# --------------------------------------------------------------------------- #
# 4. Scenarios / assertions / coverage per feature
# --------------------------------------------------------------------------- #
def _assertion_sketch(feature: Feature, glossary: InterfaceGlossary) -> str:
    """Produce a category-appropriate SVA *sketch* (non-compiling template)."""
    names = {s.role or "": s.name for s in glossary.signals}
    clk = next((s.name for s in glossary.signals if s.role == "clock"), "clk")
    rst = next((s.name for s in glossary.signals if s.role == "reset"), "rst_n")
    handshake = [s.name for s in glossary.signals if s.role == "handshake"]
    _ = names  # documented dependency

    if feature.category is Category.RESET:
        return (
            f"assert property (@(posedge {clk}) !{rst} |-> "
            f"##1 <state> == RESET_VALUE);  // review reset value/polarity"
        )
    if feature.category is Category.ERROR_HANDLING:
        return (
            f"assert property (@(posedge {clk}) disable iff (!{rst}) "
            f"<error_cond> |-> <error_response>);  // review error signals"
        )
    if feature.category is Category.CDC_RDC:
        return (
            f"assert property (@(posedge {clk}) <sync_stage_stable>);  "
            f"// CDC: confirm synchronizer depth and gray coding"
        )
    if feature.category is Category.SECURITY and handshake:
        return (
            f"assert property (@(posedge {clk}) <priv_required> |-> "
            f"<access_granted_only_when_authorized>);  // security invariant"
        )
    if handshake and len(handshake) >= 2:
        a, b = handshake[0], handshake[1]
        return (
            f"assert property (@(posedge {clk}) disable iff (!{rst}) "
            f"{a} && !{b} |-> ##[0:$] {b});  // handshake progress (review bound)"
        )
    return (
        f"assert property (@(posedge {clk}) disable iff (!{rst}) "
        f"<antecedent> |-> <consequent>);  // functional invariant sketch"
    )


def build_children(
    feature: Feature,
    glossary: InterfaceGlossary,
    llm: LLMAdapter,
) -> tuple[list[TestScenario], list[AssertionCandidate], list[CoverageTarget]]:
    idx = feature.id.split("-")[-1]
    techniques = _CATEGORY_TECHNIQUES[feature.category]

    scenarios: list[TestScenario] = []
    for j, tech in enumerate(techniques, start=1):
        scenarios.append(
            TestScenario(
                id=f"SCN-{idx}-{j:02d}",
                feature_id=feature.id,
                technique=tech,
                description=_scenario_text(feature, tech),
                approval=ApprovalState.PROPOSED,
            )
        )

    assertions: list[AssertionCandidate] = []
    if Technique.SVA in techniques or Technique.FORMAL in techniques:
        sketch = _assertion_sketch(feature, glossary)
        assertions.append(
            AssertionCandidate(
                id=f"ASRT-{idx}-01",
                feature_id=feature.id,
                sva_sketch=sketch,
                rationale=llm.rationale_for_assertion(feature.name, sketch),
                approval=ApprovalState.PROPOSED,
            )
        )

    coverage: list[CoverageTarget] = []
    if Technique.COVER in techniques or Technique.CONSTRAINED_RANDOM in techniques:
        coverage.append(
            CoverageTarget(
                id=f"COV-{idx}-01",
                feature_id=feature.id,
                metric="functional_bin",
                description=f"Cover key states/transitions of: {feature.name}",
                approval=ApprovalState.PROPOSED,
            )
        )
    return scenarios, assertions, coverage


def _scenario_text(feature: Feature, tech: Technique) -> str:
    templates = {
        Technique.DIRECTED_SIM: "Directed test hitting the nominal path of: {n}",
        Technique.CONSTRAINED_RANDOM: "Constrained-random stimulus stressing: {n}",
        Technique.SVA: "Bind SVA checkers for the invariants of: {n}",
        Technique.FORMAL: "Formal property/proof scope for: {n}",
        Technique.COVER: "Coverage collection for the behavior of: {n}",
        Technique.EMULATION: "Emulation/FPGA soak scenario for: {n}",
        Technique.POST_SILICON: "Post-silicon observability hook for: {n}",
    }
    return templates[tech].format(n=feature.name)


# --------------------------------------------------------------------------- #
# 5. Ambiguity / missing-requirement / assumption detection
# --------------------------------------------------------------------------- #
# Word-level verifiability hints (matched against tokens, not substrings, to
# avoid e.g. "if" matching inside "fifo").
_VERIFIABILITY_WORDS = frozenset(
    {"shall", "must", "when", "if", "within", "cycles", "cycle", "assert",
     "never", "always", "equal", "==", "less", "greater", "than", "before",
     "after", "at"}
)


def find_ambiguities(
    spec: SpecDocument,
    glossary: InterfaceGlossary,
    manifest: ManifestView,
    features: list[Feature],
) -> list[AmbiguityModel]:
    out: list[AmbiguityModel] = []
    counter = 0

    def _new_id() -> str:
        nonlocal counter
        counter += 1
        return f"AMB-{counter:03d}"

    categories_present = {f.category for f in features}

    # (a) Requirements that read as unverifiable (no measurable/temporal hint).
    for req in spec.requirements:
        tokens = {t.strip(".,;:()") for t in req.text.lower().split()}
        if not (tokens & _VERIFIABILITY_WORDS):
            out.append(
                AmbiguityModel(
                    id=_new_id(),
                    kind=AmbiguityKind.UNVERIFIABLE_REQUIREMENT,
                    detail=(
                        "Requirement lacks a measurable/temporal condition; "
                        "hard to turn into a check."
                    ),
                    ref=req.id,
                )
            )

    # (b) Missing requirement categories that the manifest/interface imply.
    if manifest.modules:
        reset_signals = {
            s for m in manifest.modules for s in m.reset_candidate_signals
        }
        if reset_signals and Category.RESET not in categories_present:
            out.append(
                AmbiguityModel(
                    id=_new_id(),
                    kind=AmbiguityKind.MISSING_REQUIREMENT,
                    detail=(
                        "RTL manifest exposes reset candidate(s) "
                        f"{sorted(reset_signals)} but the spec has no reset "
                        "requirement."
                    ),
                    ref="reset",
                )
            )
        clock_signals = {
            s for m in manifest.modules for s in m.clock_candidate_signals
        }
        if len(clock_signals) >= 2 and Category.CDC_RDC not in categories_present:
            out.append(
                AmbiguityModel(
                    id=_new_id(),
                    kind=AmbiguityKind.MISSING_REQUIREMENT,
                    detail=(
                        f"Multiple clock candidates {sorted(clock_signals)} in "
                        "manifest but no CDC/RDC requirement in the spec."
                    ),
                    ref="cdc_rdc",
                )
            )

    # (c) Reset candidates in manifest not present in the interface glossary.
    glossary_names = {s.name for s in glossary.signals}
    for m in manifest.modules:
        for rc in m.reset_candidate_signals:
            if rc not in glossary_names:
                out.append(
                    AmbiguityModel(
                        id=_new_id(),
                        kind=AmbiguityKind.UNMAPPED_MANIFEST_RESET,
                        detail=(
                            f"Reset candidate '{rc}' (module {m.name}) is not "
                            "described in the interface glossary."
                        ),
                        ref=rc,
                    )
                )

    # (d) Interface signals never referenced by any requirement (assumptions).
    referenced = " ".join(r.text for r in spec.requirements).lower()
    for sig in glossary.signals:
        if sig.name.lower() not in referenced and sig.role not in ("clock", "reset"):
            out.append(
                AmbiguityModel(
                    id=_new_id(),
                    kind=AmbiguityKind.ASSUMPTION,
                    detail=(
                        f"Interface signal '{sig.name}' is not mentioned by any "
                        "requirement; assuming it is out of verification scope "
                        "unless a reviewer says otherwise."
                    ),
                    ref=sig.name,
                )
            )

    return out


# --------------------------------------------------------------------------- #
# 6. Traceability matrix
# --------------------------------------------------------------------------- #
def build_traceability(
    spec: SpecDocument,
    features: list[Feature],
    scenarios: list[TestScenario],
    assertions: list[AssertionCandidate],
    coverage: list[CoverageTarget],
    existing: ExistingTestplan,
) -> list[TraceRow]:
    rows: list[TraceRow] = []
    for req in spec.requirements:
        feats = [f for f in features if req.id in f.source_requirements]
        feat_ids = [f.id for f in feats]
        scn = [s.id for s in scenarios if s.feature_id in feat_ids]
        asr = [a.id for a in assertions if a.feature_id in feat_ids]
        cov = [c.id for c in coverage if c.feature_id in feat_ids]
        existing_ids = [
            e.id for e in existing.items if req.id in e.covers_requirements
        ]
        covered = bool(scn or asr or existing_ids)
        rows.append(
            TraceRow(
                requirement_id=req.id,
                feature_ids=feat_ids,
                scenario_ids=scn,
                assertion_ids=asr,
                coverage_ids=cov,
                existing_testplan_ids=existing_ids,
                covered=covered,
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def build_plan(
    spec: SpecDocument,
    glossary: InterfaceGlossary,
    manifest: ManifestView | None = None,
    existing: ExistingTestplan | None = None,
    provenance: Provenance | None = None,
    llm: LLMAdapter | None = None,
) -> VerificationPlan:
    manifest = manifest or ManifestView()
    existing = existing or ExistingTestplan()
    provenance = provenance or Provenance()
    llm = llm or MockLLM()

    features = decompose(spec)

    all_scenarios: list[TestScenario] = []
    all_assertions: list[AssertionCandidate] = []
    all_coverage: list[CoverageTarget] = []
    plan_items: list[PlanItem] = []

    for feature in features:
        scn, asr, cov = build_children(feature, glossary, llm)
        all_scenarios.extend(scn)
        all_assertions.extend(asr)
        all_coverage.extend(cov)

        score, why = _risk_for_feature(feature, manifest)
        plan_items.append(
            PlanItem(
                id=f"PLAN-{feature.id.split('-')[-1]}",
                feature_id=feature.id,
                category=feature.category,
                priority=_priority_from_score(score),
                risk_score=score,
                risk_rationale=why,
                techniques=_CATEGORY_TECHNIQUES[feature.category],
                scenario_ids=[s.id for s in scn],
                assertion_ids=[a.id for a in asr],
                coverage_ids=[c.id for c in cov],
                approval=ApprovalState.PROPOSED,
            )
        )

    # Risk-rank plan items (stable: by descending score then id).
    plan_items.sort(key=lambda p: (-p.risk_score, p.id))

    ambiguities = find_ambiguities(spec, glossary, manifest, features)
    trace = build_traceability(
        spec, features, all_scenarios, all_assertions, all_coverage, existing
    )

    return VerificationPlan(
        design_name=spec.design_name,
        provenance=provenance,
        features=features,
        plan_items=plan_items,
        scenarios=all_scenarios,
        assertions=all_assertions,
        coverage_targets=all_coverage,
        ambiguities=ambiguities,
        traceability=trace,
    )
