# Threat Model

This tool advises verification engineers on *where* an equivalence mismatch
likely originates. The main risks are giving false confidence, leaking data, or
being non-reproducible. Mitigations below are enforced in code and tests.

## 1. Hallucinated / overstated conclusions

- **Risk:** claiming a design is (non-)equivalent, or presenting a heuristic
  guess as a formal result.
- **Mitigation:**
  - `reported_status` is **copied verbatim** from the tool log
    (`TriageEngine._status_evidence` records the source line). The engine has no
    code path that invents a status.
  - Every cause is a `LikelyCause` with `is_heuristic=True`, a bounded
    `confidence ∈ [0,1]`, and an explicit `rationale`/`evidence_refs`. The
    Markdown renderer prints "(heuristic)" on every cause and a top-of-report
    disclaimer.
  - The offline narrator (`llm.py`) appends "hypothesis, not a proof" / "advisory"
    language and invents no new facts.
  - Tests: `test_status_is_echoed_not_inferred`, `test_cli_narrate_disclaimer`,
    `test_inconclusive_status_warns_and_no_false_claim`.

## 2. Misclassifying non-conclusive results as PASS/FAIL

- **Risk:** treating `TIMEOUT`/`INCONCLUSIVE`/`ERROR`/`ABORTED` as a
  non-equivalence proof.
- **Mitigation:** those statuses trigger an explicit advisory warning; no
  non-equivalence claim is produced. Test: `test_inconclusive_status_warns_and_no_false_claim`.

## 3. Concealed configuration / constraint differences

- **Risk:** the two runs used different constraints/abstractions, so mismatches
  are a setup artifact rather than an RTL bug — and the report hides that.
- **Mitigation:** `config_deltas` is a mandatory, always-rendered field. Any real
  difference raises a warning, adds a `config_constraint` likely-cause, and moves
  "reconcile configuration differences first" to the top of the debug packet.
  Tests: `test_config_delta_surfaced_and_warned`, `test_debug_packet_built`.

## 4. Unsafe assumptions from incomplete inputs

- **Risk:** inferring reset polarity/width when the manifest doesn't say.
- **Mitigation:** reset comparison only flags a difference when **both** sides are
  known (`ResetPolarity.UNKNOWN`/`ResetSync.UNKNOWN` are treated as "no claim").
  Unresolvable parameterized widths in the canonical manifest are dropped rather
  than guessed (`parser._range_width` returns `None`).

## 5. Data leakage / proprietary content

- **Risk:** committing customer RTL, tool names, or internal paths.
- **Mitigation:** only public toy designs and a synthetic `mock-lec` tool name
  are bundled. No secrets, credentials, or proprietary identifiers. Inputs are
  hashed (SHA-256) for provenance, not embedded verbatim beyond what the user
  supplies.

## 6. Reproducibility / determinism

- **Risk:** non-deterministic grouping/ranking making reports unstable.
- **Mitigation:** all ordering uses explicit, total sort keys; no randomness, no
  wall-clock, no dict-iteration-order dependence in outputs. Provenance records
  tool version, git SHA, command, and input hashes. Tests:
  `test_determinism_same_input_same_output` and the golden tests.

## 7. Malformed input handling

- **Risk:** silently mis-parsing a corrupt log.
- **Mitigation:** the parser raises `LogParseError` on a missing header, unknown
  tag, unknown status, bad `compare_points`/`config`/`cex` lines, or a CEX that
  references an undeclared compare point. Models use `extra="forbid"`. Tests:
  `test_parse_rejects_*`, `test_extra_keys_rejected`.

## Out-of-scope trust assumptions

- The upstream equivalence tool's status and reported fan-in are trusted as
  inputs; this tool triages them, it does not re-prove equivalence.
