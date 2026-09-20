# Threat model (of the tool itself)

This document is about risks introduced by *using this tool*, per the shared
BUILD_STANDARD. It is **not** a threat model of any RTL design — the tool
explicitly refuses to infer design threat models (see below).

## 1. Hallucination / fabrication

**Risk:** the tool invents a signal, clock, reset, or trust boundary that does
not exist, producing an authoritative-looking but meaningless property.

**Mitigations:**
- Grounding uses the canonical Manifest as the *only* symbol evidence. Unknown
  terms become `unresolved_terms` / `MatchKind.UNRESOLVED`, never a real symbol
  (`test_unknown_signal_is_unresolved_not_invented`).
- Clock/reset come from the Manifest's candidate lists; the tool never fabricates
  them. If no clock exists, emission is skipped with a recorded reason.
- Trust boundaries are never inferred. Absence raises an ambiguity note
  (`test_no_trust_boundary_declared_raises_ambiguity`).
- Alias matches are labelled low-confidence and flagged for human confirmation.

## 2. Unsafe assumptions (mis-classification)

**Risk:** an environment assumption is emitted as an `assert`, over-constraining
the design or corrupting signoff; or a test objective is asserted as a
guarantee.

**Mitigations:**
- Three-way clause classification with emitted rationale.
- Hard rule: an `ENVIRONMENT_ASSUMPTION` clause is never emitted as `assert`
  (`test_environment_assumption_never_emitted_as_assert`,
  `test_env_assumption_requirement_not_emitted_as_assert`).
- Test objectives are forced to `cover` (`test_objective_becomes_cover`).
- Classification is a transparent, reviewer-overridable keyword heuristic and is
  labelled as heuristic in provenance notes.

## 3. Overclaiming (calling a candidate proven)

**Risk:** a reader treats a rendered property as verified.

**Mitigations:**
- `status` is always `candidate_rendered_offline`; `"verified"` never appears
  (`test_candidate_status_is_never_verified`).
- A non-claims block is emitted on every report and printed by the CLI.
- No formal/simulation tool is invoked; rendering != verification is stated
  everywhere.
- A TIMEOUT/ERROR/INCONCLUSIVE result is never produced as PASS — the tool does
  not run solvers at all, so it cannot mislabel their results.

## 4. Injection via untrusted text

**Risk:** requirement text or signal names inject arbitrary SV (system tasks,
macros, extra statements) into the emitted SVA.

**Mitigations:**
- Every expression passes `renderer.safe_expr`, a strict token whitelist that
  rejects `;`, `$`, backtick macros, comments, `\`, division, and the keywords
  `assert/assume/cover/property` inside expressions
  (`test_safe_expr_rejects_unsafe`).

## 5. Data leakage

**Risk:** proprietary content leaks into a public repo.

**Mitigations:**
- All bundled examples are public toy content authored for this repo.
- No secrets, hostnames, employer/customer names, or proprietary paths.
- Provenance records input **hashes**, not input contents.

## 6. Reproducibility

**Risk:** non-deterministic output undermines auditability.

**Mitigations:**
- No randomness, no network, no LLM. Byte-identical output for fixed inputs
  (`test_report_is_json_serializable_and_deterministic`).
- Provenance records tool version, git SHA placeholder, input hashes, command.

## Out of scope

- Modeling attacker capabilities against a specific RTL design.
- Any claim of soundness or completeness of the candidate property set.
