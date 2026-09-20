# Threat Model

Scope: risks specific to a **structural CDC/RDC triage** tool used by real
verification engineers. The overarching risk is a human trusting a heuristic
result as if it were signoff.

## 1. Over-trust / false confidence (highest risk)

- **Risk:** a reviewer reads "2-FF synchronizer candidate" or an empty crossing
  list and concludes the design is CDC/RDC clean.
- **Mitigations:**
  - Every finding sets `heuristic: true`; every synchronizer result is a
    *candidate*, worded "correctness NOT proven".
  - The report carries a `disclaimer` and `non_claims` in JSON and Markdown.
  - A zero-crossing module renders an explicit "absence is NOT a clean result"
    note (`report.render_markdown`).
  - Tests: `test_every_finding_is_heuristic`, `test_report_never_claims_clean`.

## 2. Wrong domain candidates propagate

- **Risk:** the manifest's clock/reset candidates are themselves heuristic; a
  mislabeled clock makes every downstream domain wrong.
- **Mitigation:** the reviewer checklist's first item is "confirm the clocks are
  genuinely asynchronous, not just differently named"; limitations state that a
  wrong candidate propagates.

## 3. Data-flow under/over-reporting

- **Risk:** RHS identifiers are extracted from expression *text*, not a full
  AST, so complex expressions can miss or invent references → false negatives
  (missed crossing) or false positives (spurious crossing).
- **Mitigation:** extraction is conservative and deterministic (`rhs.py`,
  tested); limitations document the AST gap; combinational paths are flagged so
  a reviewer looks closer.

## 4. Silent input drift / schema mismatch

- **Risk:** an incompatible or malicious manifest yields garbage findings.
- **Mitigation:** input is validated by Pydantic; unknown fields are ignored
  (forward-compatible) but typed fields are strictly validated
  (`test_manifest_validates_types`).

## 5. Non-reproducible results

- **Risk:** unstable ordering/output breaks review diffing and audit.
- **Mitigation:** all collections are sorted; JSON is emitted with sorted keys;
  golden + determinism tests enforce byte-stability.

## 6. Data leakage / proprietary content

- **Risk:** committing customer RTL, internal tool names, or paths.
- **Mitigation:** bundled examples are public toy designs only; no network/API
  calls; no secrets. The tool reads local files the user supplies and writes
  only where told.

## 7. Glossary trust

- **Risk:** a glossary entry falsely declares a module a synchronizer, lowering
  a real hazard's priority.
- **Mitigation:** the glossary is explicitly *user-declared* human input, and
  its use is recorded in the finding rationale ("glossary synchronizer cell") so
  a reviewer sees the assumption.

## Out of scope

Metastability/functional correctness, glitch analysis, timing, and any claim of
signoff quality. Use a commercial CDC/RDC tool for those.
