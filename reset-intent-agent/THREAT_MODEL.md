# Threat Model

This tool is a **structural triage and candidate-generation** aid. The risks
below are about it being *misused as authoritative*. Mitigations are enforced in
code and labelling.

## 1. Hallucinated / silent inference

- **Risk:** Reporting a reset polarity that the RTL does not unambiguously
  support; a reviewer trusts it and writes a wrong assertion.
- **Mitigation:** Polarity is decided by explicit evidence voting
  (`analyzer._vote_polarity`). Conflicting or absent evidence yields `unknown`
  plus an `Ambiguity`; candidate SVA emits a `/* REVIEW: polarity ... */`
  placeholder instead of a guess. Test: `test_ambiguous_polarity_not_inferred`,
  `test_vote_conflict_yields_unknown`, `test_unknown_polarity_emits_review_placeholder`.

## 2. Structural detection mistaken for verified intent

- **Risk:** Treating "reset candidate detected" as "reset verified", or
  "domain crossing flagged" as "RDC bug".
- **Mitigation:** Every domain and crossing carries `heuristic=True`; the report
  header and every section label STRUCTURAL vs HEURISTIC. README non-claims are
  explicit. Candidate SVA `status` is always `candidate`.

## 3. Over-claiming CDC/RDC signoff

- **Risk:** Presenting reset-domain-crossing output as signoff-quality RDC.
- **Mitigation:** README states it is **not** a signoff tool. Crossings are
  structural feed-through detections requiring RDC review, ranked but not proven.

## 4. Parser blind spots (silent drops)

- **Risk:** Unsupported constructs silently ignored → false "no reset" or
  missing targets.
- **Mitigation:** The subset is documented; unsupported constructs are surfaced
  as `UnresolvedConstruct`/ambiguities. A `no_reset` HIGH risk is raised when
  sequential logic exists but no reset was found, prompting review rather than
  implying safety. Test: `test_no_reset_flags_high_risk`.

## 5. Data leakage

- **Risk:** Proprietary RTL, paths, or names committed.
- **Mitigation:** Only public toy RTL in `examples/`. Provenance stores input
  **hashes**, not contents. No network calls; no credentials. `.gitignore`
  excludes venvs and generated artifacts.

## 6. Reproducibility

- **Risk:** Non-deterministic output undermines audit/diff.
- **Mitigation:** No LLM in the analysis path. All outputs sorted; DOT is
  byte-stable (`test_dot_is_deterministic`). Provenance records tool version,
  command, and input SHA-256.

## 7. Reward-hacking / result laundering

- **Risk:** Mutants presented as "assertion proven wrong".
- **Mitigation:** `mutations.py` only **injects** defects and records the exact
  source change; it does not classify detection (no execution adapter in v0.1),
  so it cannot fabricate a mutation score.

## Authority boundary

The tool proposes structural facts, heuristics, candidate properties, and
recommendations. It does **not** modify RTL, assumptions, proof scope, or make
signoff conclusions. Human review is required before any candidate SVA, polarity
call, or crossing is acted upon.
