# Threat Model

Risks specific to an LLM-adjacent verification triage tool, and the mitigations
implemented here.

## 1. Hallucinated / overstated conclusions

**Risk:** presenting a heuristic guess as a proven design bug; inventing a root
cause not supported by the trace.

**Mitigations:**
- Every evidence line in the report is derived from the trace/manifest, not
  generated prose.
- `RootCauseHypothesis` rejects an evidence-free `design_bug` at the model layer
  (`test_design_bug_hypothesis_requires_evidence`).
- The engine proposes `design_bug` only with a real divergence outside reset and
  a defined consequent; otherwise it is omitted
  (`test_no_design_bug_when_antecedent_never_fires`,
  `test_reset_active_at_divergence_yields_reset_hypothesis`).
- Reports carry an explicit "heuristic triage … not conclusions" banner.

## 2. Unsafe assumptions

**Risk:** treating x/z as `1`; assuming reset polarity; assuming a failing
property is a design bug.

**Mitigations:**
- `_is_true` treats only `"1"` as true; x/z/None are never true.
- Reset polarity is an explicit input field; reset-active cycles are excluded
  from antecedent/divergence detection.
- Alternative hypotheses (property / environment / reset / modeling) are always
  retained (`test_alternatives_always_retained`).

## 3. Modifying protected artifacts

**Risk:** an agent editing RTL, assertions, or traces.

**Mitigation:** the tool only reads inputs; there is no code path that writes to
RTL/assertion/trace files. Outputs go only to user-specified report paths.

## 4. Data leakage

**Risk:** committing proprietary RTL, waveforms, tool logs, credentials, or
internal paths.

**Mitigations:**
- All bundled examples are public toy content authored for this repo.
- No network calls anywhere (the LLM adapter is an offline mock).
- `.gitignore` excludes venvs, caches, and generated reports.
- Run a public-release audit (pack §7.1) before publishing.

## 5. Reproducibility risks

**Risk:** non-deterministic output; results that cannot be reproduced.

**Mitigations:**
- No RNG / clock / network in the deterministic path; cone and hypothesis
  ordering are explicitly sorted.
- VCD and JSON traces of the same scenario produce identical reports.
- Golden tests pin the toy_counter report; each report includes its exact
  reproduction command and artifact list.

## 6. Parser robustness

**Risk:** malformed or unsupported VCD crashing or silently mis-parsing.

**Mitigations:**
- Fatal structural errors (bad timestamp, malformed `$var`) raise
  `VCDParseError` (`test_parse_vcd_bad_timestamp_raises`,
  `test_parse_vcd_malformed_var_raises`).
- Unsupported-but-safe constructs (real-valued dumps, unknown scalar codes) are
  handled conservatively (skip / normalize to `x`) and documented, never
  silently treated as functional values.
