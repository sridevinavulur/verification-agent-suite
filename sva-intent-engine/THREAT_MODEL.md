# Threat Model

Scope: risks specific to an NL-to-SVA candidate generator used by verification
engineers. This tool is advisory; formal/simulation results and human review
remain authoritative.

## 1. Hallucinated grounding (inventing signals)

- **Risk**: mapping a requirement term to a signal that does not exist or is the
  wrong one.
- **Mitigation**: `grounding.py` matches only against manifest symbols
  (exact > case-insensitive > listed alias). Unresolved terms are recorded and
  `pipeline.build_intent` returns `None`, stopping emission. Multiple
  equally-ranked matches are kept and flagged `ambiguous`, never silently
  collapsed. `expr_normalize.normalize` only emits an expression when the signal
  is in the resolved set.
- **Residual risk**: a term may match the wrong same-named symbol; grounding is
  lexical, not semantic. Reviewer must confirm.

## 2. Unsafe assumptions (inventing clocks / resets / bounds / polarity)

- **Risk**: fabricating a clock, reset, cycle bound, or reset polarity.
- **Mitigation**: bounds come only from literal text (`decompose._extract_bounds`);
  clock/reset come only from manifest candidates (`grounding._select_clock/_select_reset`);
  a single candidate is selected, multiples are deferred (not chosen); reset
  polarity is set only from lexical/type evidence, else `UNKNOWN`. The renderer
  rejects an absent clock and rejects reset-state properties with unknown
  polarity. `disable iff` is omitted when polarity is unknown rather than guessed.

## 3. Injection / unsafe rendering

- **Risk**: requirement text smuggling raw SV (`$system` tasks, `;`, comments,
  backticks) into a rendered property.
- **Mitigation**: `renderer.safe_expr` whitelists a small token grammar and
  bans `;`, `$`, `//`, `/*`, backtick, backslash, newlines, and nested SVA
  keywords. Anything outside the whitelist raises `RenderError` and blocks
  emission.

## 4. Overclaiming (compiled ≠ verified)

- **Risk**: treating a rendered property as correct or proven.
- **Mitigation**: `CandidateProperty.status` is `candidate_compiled_offline`;
  README/ARCHITECTURE state non-claims; the review checklist requires
  independent validation before signoff. No PASS/proof vocabulary is emitted by
  this tool. Note: this phase performs **no** compile/formal run at all — the
  status denotes offline rendering only.

## 5. Data leakage

- **Risk**: committing proprietary RTL, internal names, or credentials.
- **Mitigation**: examples are public toy fixtures only. No network calls; LLM
  adapter is a mock. See `RELEASE_CHECKLIST.md` for the disclosure audit.

## 6. Reproducibility

- **Risk**: non-deterministic output undermining audits.
- **Mitigation**: fully deterministic pipeline (sorted, stable ordering in
  grounding and schema export); provenance records; golden tests pin
  intent/SVA output; CI runs lint + tests + demo on a fresh checkout with no
  secrets.

## 7. Incorrect decomposition

- **Risk**: mis-splitting or mis-classifying a compound requirement.
- **Mitigation**: conservative sentence/semicolon splitting; vague terms force
  an `ambiguity` classification (no emission); unsupported performance/analog
  concerns are flagged. Original wording and source spans are retained for
  audit. Reviewer confirms classification.
