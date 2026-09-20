# Threat Model

Scope: risks specific to an automated **constraint-hygiene** reviewer whose
output influences whether verification engineers trust a formal proof.

## 1. False confidence / soundness overreach (highest risk)

**Risk:** A user reads "0 contradictions, empty review queue" as "the constraint
set is sound and the proof is valid." This is the single most dangerous failure
mode for this class of tool.

**Mitigations:**
- The tool has **no vocabulary for "proven/valid/sound."** `Confidence` is only
  `static_suspicion` or `static_fact`.
- A `disclaimer` field travels with every report and every Markdown render,
  explicitly stating that absence of findings is not soundness.
- A standing `VACUITY_RISK` INFO reminder is emitted on **every** run
  (`analysis/dependency.py`) restating that a clean report is not a soundness
  result. Tested in `test_disclaimer_never_claims_soundness`.
- The tool recommends running the formal tool's own vacuity/reachability checks;
  it never substitutes for them.

## 2. Hallucination / over-precise claims

**Risk:** Reporting a contradiction that does not actually exist (e.g. two
assumptions active in different clock/reset regimes), causing an engineer to
delete a needed assumption.

**Mitigations:**
- Facts are extracted **only from top-level conjuncts**, where the implication is
  unconditional; disjunctions and nested terms produce no facts
  (`test_extract_facts_only_top_level_conjuncts`).
- `x`/`z` constant values are treated as incomparable and never reported as a
  conflict (`test_xz_values_not_reported_as_contradiction`).
- Every contradiction finding's `evidence` states it is a static suspicion and
  that different clock/reset regimes may explain it.

## 3. Unsafe autonomous action

**Risk:** The tool modifying assumptions/RTL/scope on its own.

**Mitigations:** The tool is strictly read-only; there is no write path to any
design artifact. All findings require human review (`needs_human_review=True`,
enforced in `test_every_actionable_finding_is_static_suspicion`).

## 4. Missing-manifest degradation

**Risk:** Running without a manifest and silently classifying everything, hiding
overconstraint.

**Mitigation:** Without a manifest, every signal is `unknown` (with an explicit
rationale) and output-constraint checks downgrade to `UNKNOWN_SIGNAL` warnings
rather than false "clean" (`test_no_manifest_degrades_to_unknown`).

## 5. Parser blind spots (under-reporting)

**Risk:** Unsupported SVA forms are skipped, so a real overconstraint is never
seen and the report looks clean.

**Mitigations:** Scope is documented in README (constrained SVA subset). The
parser skips what it cannot understand rather than guessing. This is an accepted
v0.1 limitation; the honest framing (clean != sound) prevents it from being
mistaken for a completeness guarantee. Future work: emit an explicit
`unresolved` list, mirroring the manifest schema.

## 6. Data leakage / provenance

**Risk:** Committing proprietary RTL or SVA into the public corpus.

**Mitigations:** All bundled examples are synthetic and public. `.gitignore`
excludes local report outputs. Provenance stores SHA-256 hashes and relative
paths, not file contents. No secrets, employer/customer names, or internal tool
names appear anywhere in the repo.

## 7. Reproducibility

**Risk:** Non-deterministic output undermines diffable review.

**Mitigation:** All outputs sorted by stable keys; provenance captures input
hashes and the command. Golden tests pin the analysis payload.
