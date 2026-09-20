# Threat Model

This document enumerates the ways this tool could mislead a verification
engineer and the mitigations built into the design.

## 1. Overclaiming detection (false confidence)

- **Risk:** A high mutation score is read as "the assertion suite is complete /
  the design is verified."
- **Mitigation:** README, report footer, and Markdown output state explicitly
  that the score is a heuristic property-quality signal, not formal signoff or
  coverage closure. The score denominator excludes only invalid/inconclusive
  mutants, so it is not inflated by discarding survivors.

## 2. Mock executor mistaken for a real check

- **Risk:** The shipped `MockExecutor` decides detection by signal-reference
  overlap, not by compiling/simulating. A reader could assume real evidence.
- **Mitigation:** The executor is named `mock`, its heuristic is documented in
  code and README, and every report records `executor: mock` in provenance. Real
  adapters must implement the same `ExecutorAdapter` interface and would report
  their own name.

## 3. Calling a surviving mutant an assertion bug

- **Risk:** Treating "survived" as proof an assertion is wrong.
- **Mitigation:** Vocabulary is fixed everywhere: a survivor is an "undetected
  mutation requiring investigation." A survivor can indicate a missing property,
  an equivalent mutant, or an out-of-scope signal — not necessarily a defect.

## 4. Invalid / equivalent mutants distorting the score

- **Risk:** No-op or equivalent mutants pollute the numerator/denominator.
- **Mitigation:** Mutations that do not change the source are classified
  `invalid` and excluded from the score. `generate_mutants` also drops no-op
  mutants up front. (Semantic equivalent-mutant detection is future work and is
  disclosed as such.)

## 5. Timeout/error laundered into a pass

- **Risk:** Execution failures counted as detections.
- **Mitigation:** `compute_score` counts only `detected` in the numerator and
  only `detected + survived` in the denominator; `timeout`/`error`/`invalid`/
  `inconclusive` can never become a pass.

## 6. Unsound source mutation (uncompilable mutants)

- **Risk:** A textual splice produces syntactically invalid RTL, giving
  misleading results with a real executor.
- **Mitigation:** Operators only fire at points that are syntactically safe in
  the subset (e.g. width truncation only on a bare RHS identifier; operand swap
  only between two plain identifiers). Where safety cannot be established, no
  mutant is emitted rather than an unsafe one. A real compile adapter would
  additionally reject any that slip through as `error`.

## 7. Hallucinated / silently-guessed signals

- **Risk:** Inventing signals not in the source.
- **Mitigation:** All signals come from the actual token stream. `mutated_signals`
  are extracted from the mutated statement; SVA references from the property
  text. Nothing is inferred beyond the text.

## 8. Data leakage / proprietary content

- **Risk:** Committing employer/customer RTL, credentials, or internal paths.
- **Mitigation:** Only public toy RTL is bundled. Provenance stores content
  hashes, not paths beyond what the user passes on the CLI. See
  `RELEASE_CHECKLIST` guidance in EVIDENCE.md and the public-release audit prompt.

## 9. Non-reproducible results

- **Risk:** Scores that vary run-to-run undermine trust.
- **Mitigation:** Deterministic IDs, stable sort order, content-hash provenance,
  and a golden-report regression test.
