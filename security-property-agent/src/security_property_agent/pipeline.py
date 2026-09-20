"""End-to-end deterministic pipeline.

    requirement set + Manifest
        -> decompose -> ground -> generate candidates -> mutations -> validate
        -> SecurityReviewReport

No network, no LLM, fully reproducible for a given (input, git_sha, seed).
"""

from __future__ import annotations

from .decompose import decompose
from .generate import generate_candidates, generate_mutations
from .grounding import ground
from .manifest import ManifestView
from .models import (
    Provenance,
    RequirementArtifacts,
    RequirementSet,
    SecurityReviewReport,
    ValidationCheck,
)
from .validate import validate_candidate

# The non-claims block is emitted on every report. These are load-bearing:
# the tool's entire posture is "candidate artifacts for human review".
NON_CLAIMS = [
    "This tool does NOT prove any security property. All output is candidate "
    "material for human review.",
    "Rendering or compiling a property is NOT verification. No formal or "
    "simulation tool was run by this pipeline.",
    "Threat models and trust boundaries are NOT inferred. Boundary-dependent "
    "properties require an explicit human-declared boundary.",
    "Symbol groundings marked as heuristic aliases are low-confidence and must "
    "be confirmed against the RTL by a human.",
    "Mutation examples are should-fail witnesses, not proof the original "
    "property holds.",
    "Information-flow-adjacent checks are structural comparisons only and are "
    "NOT non-interference proofs.",
]


def _checklist_items() -> list[dict[str, str]]:
    return [
        {"item": "Confirm each clause classification (property vs assumption vs objective)"},
        {"item": "Confirm every symbol grounding against the actual RTL"},
        {"item": "Confirm the trust boundary for boundary-dependent properties"},
        {"item": "Run each candidate through a formal/simulation tool before signoff"},
        {"item": "Confirm each mutation actually fails under the tool"},
    ]


def run_pipeline(
    reqset: RequirementSet,
    manifest: ManifestView,
    run_id: str,
    git_sha: str = "UNKNOWN",
    command: str | None = None,
    input_hashes: dict[str, str] | None = None,
) -> SecurityReviewReport:
    from .models import ReviewChecklistItem

    artifacts: list[RequirementArtifacts] = []

    for req in reqset.requirements:
        decomp = decompose(req, git_sha=git_sha)
        grounding = ground(req, manifest, git_sha=git_sha)
        candidates, skips = generate_candidates(
            req, decomp.clauses, grounding, git_sha=git_sha
        )

        mutations = []
        for cand in candidates:
            mutations.extend(generate_mutations(cand, git_sha=git_sha))

        checks: list[ValidationCheck] = []
        for cand in candidates:
            checks.extend(validate_candidate(cand, grounding))
        # Surface skips as INFO checks so nothing is silently dropped.
        from .models import Severity

        for reason in skips:
            checks.append(
                ValidationCheck(
                    name="candidate_skipped",
                    passed=True,
                    severity=Severity.INFO,
                    detail=reason,
                )
            )

        emitted = len(candidates) > 0
        artifacts.append(
            RequirementArtifacts(
                requirement=req,
                decomposition=decomp,
                grounding=grounding,
                candidates=candidates,
                mutations=mutations,
                checks=checks,
                emitted=emitted,
            )
        )

    prov = Provenance(
        stage="pipeline",
        git_sha=git_sha,
        command=command,
        input_hashes=input_hashes or {},
        notes=["deterministic pipeline; no LLM/network involved"],
    )
    return SecurityReviewReport(
        run_id=run_id,
        design=reqset.design,
        manifest_top=manifest.top,
        artifacts=artifacts,
        checklist=[ReviewChecklistItem(**i) for i in _checklist_items()],
        non_claims=list(NON_CLAIMS),
        provenance=prov,
    )
