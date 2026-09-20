# Threat model

This tool generates *candidate* interface contracts. The dangerous failure mode
is a contract that **looks authoritative but silently encodes an unsound
assumption**. The design mitigates the following risks.

## 1. Silently-added assumptions
- **Risk:** an environmental assumption is emitted that the environment does not
  actually satisfy, masking real design bugs (vacuous / over-constrained proof).
- **Mitigation:** assumptions are only placed on signals classified as
  `env_input`. Any assumption referencing a `dut_output`/`internal`/`unknown`
  signal is emitted with `ownership_ok=false`, a human-readable `review_reason`,
  and an `assume_on_output` warning. Nothing is auto-accepted.
- **Test:** `test_assume_never_silently_constrains_output`.

## 2. Output signals treated as environment inputs
- **Risk:** constraining a DUT output as if the environment drives it.
- **Mitigation:** ownership is derived from the manifest port `direction`. The
  same protocol role produces an **assert** (guarantee) when it is a DUT output
  and an **assume** only when it is an env input.
- **Tests:** `test_output_role_produces_guarantee_not_assumption`,
  `test_input_valid_produces_assumption`.

## 3. Hallucinated / ungrounded signals
- **Risk:** a property references a signal that does not exist in the RTL.
- **Mitigation:** every referenced symbol is resolved from the manifest into a
  `GroundedSymbol` with a stable `symbol_id` and source location. A role bound to
  a missing signal raises `GroundingError`. Missing *required* roles block
  property generation entirely (partial contract + warning).
- **Tests:** `test_every_property_is_grounded`,
  `test_require_signal_raises_when_absent`,
  `test_missing_required_role_blocks_generation`.

## 4. Guessed reset behavior
- **Risk:** wrong reset polarity flips the meaning of `disable iff` and reset
  properties.
- **Mitigation:** polarity comes from the request override or the manifest
  candidate — **never inferred by name**. Unknown polarity produces no
  `disable iff` clause and **skips** polarity-dependent properties with a warning.
  Reset-behavior is stated explicitly in the contract.
- **Tests:** `test_disable_iff_never_guesses_polarity`,
  `test_unknown_reset_polarity_skips_polarity_properties`,
  `test_reset_state_property_has_no_disable_iff`.

## 5. Multiple outstanding transactions collapsed to one
- **Risk:** modeling a FIFO / credit interface as a single in-flight transaction
  hides overflow/ordering bugs.
- **Mitigation:** occupancy/credit bounds require a real `count`/`credit_count`
  signal plus an explicit `depth`/`max_credits`; otherwise the bound is omitted
  (warning) rather than invented. The checklist forces the reviewer to confirm
  multi-outstanding modeling.
- **Tests:** `test_fifo_models_multiple_outstanding_not_single`,
  `test_credit_no_send_without_credit_is_assert`.

## 6. Injection via expressions
- **Risk:** untrusted text in a role/expression injecting SVA/statements.
- **Mitigation:** all expressions pass through `sva.safe_expr`, a strict
  whitelist tokenizer that rejects statement terminators, comments, macros,
  system tasks, and division. Only signal names from the manifest reach templates.
- **Test:** `test_safe_expr_rejects_unsafe`.

## 7. Over-claiming (reproducibility / integrity)
- **Risk:** presenting candidates as verified.
- **Mitigation:** every contract carries a `limitations` block and non-claims;
  output SVA files carry a "CANDIDATE, not verified" header; the CLI prints
  non-claims. No formal tool is invoked, so no PASS/proven vocabulary is used.

## 8. Data leakage
- **Risk:** committing proprietary RTL/paths.
- **Mitigation:** examples are public toy manifests authored here; no employer,
  customer, or proprietary content. Provenance records only input file basenames
  and sha256 hashes.

## Non-goals / residual risk
- No detection of *whether* a user's role binding is correct (garbage-in →
  candidate-out); the checklist asks the reviewer to confirm role/direction.
- No formal soundness argument for any property; all output is heuristic template
  instantiation for human review.
