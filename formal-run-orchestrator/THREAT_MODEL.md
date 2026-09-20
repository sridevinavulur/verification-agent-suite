# Threat Model

Scope: this repo is an orchestration + offline-evaluation harness with a **mock**
executor. The threats below cover (a) safety/soundness of the orchestration and (b)
scientific validity of the policy comparison.

## 1. Treating a non-conclusive run as a pass (soundness)
- **Risk:** a TIMEOUT/ERROR/INCONCLUSIVE run is silently counted as success.
- **Mitigation:** `classifier.classify` uses safety-first precedence and cannot emit
  PASS without a clean conclusion + return code 0. `RunRecord` has a validator that
  rejects `PASS` with a nonzero return code. Metrics count only PASS+FAIL as "solved".
- **Tests:** `test_classifier.py` (`test_*_never_pass`), `test_split_reward_metrics.py`.

## 2. Overclaiming — presenting heuristic orchestration as formal capability
- **Risk:** readers infer the tool proves properties or optimizes a real solver.
- **Mitigation:** README/ARCHITECTURE label the executor as MOCK and policies as
  heuristic; explicit non-claims section; `EVIDENCE.md` ties every claim to code/tests.
  No claim of solver optimization or signoff is made.

## 3. Benchmark leakage (validity)
- **Risk:** correlated designs (variants of one design family) appear in both train
  and test, inflating a learned policy's apparent skill.
- **Mitigation:** `split.group_holdout_split` splits at the **group** level; a whole
  design family lands entirely in train or entirely in test. Assignment is by a stable
  hash of the group, so adding items to a group never moves it across the boundary.
- **Test:** `test_split_reward_metrics.py::test_split_has_no_group_leakage`.

## 4. Correlated designs / small samples
- **Risk:** the toy suite has few groups; test metrics on a handful of designs have
  wide variance and weak generalization.
- **Mitigation:** confidence intervals are reported only when n ≥ 3 (else `n/a`);
  per-design reward variance is reported; docs state the suite is a *toy* and results
  do not transfer to real tools. This is a demonstration harness, not a benchmark study.

## 5. Non-determinism
- **Risk:** irreproducible runs undermine comparison.
- **Mitigation:** the mock is a pure function of `(item, config, seed)`; no global RNG,
  no wall-clock in the result values (only in provenance timestamps). Deterministic
  ordering everywhere user-visible.
- **Test:** `test_executor.py::test_simulate_is_deterministic`,
  `test_planner_policies.py::test_planner_is_deterministic_and_idempotent`.

## 6. Tool-version drift
- **Risk:** results compared across different backend/tool versions are not comparable.
- **Mitigation:** `tool_name`, `tool_version`, and `catalog_version` are recorded on
  every run; the catalog is versioned. A future real adapter must record its exact
  version. Cross-version comparison is called out as a validity threat here and in the
  comparison report footer.

## 7. Selective reporting / reward hacking
- **Risk:** cherry-picking splits/seeds/policies, or a policy gaming the reward by
  choosing configs that "look" cheap but never conclude.
- **Mitigation:** the reward penalizes TIMEOUT, ERROR, INCONCLUSIVE, near/over-cap
  memory, and invalid configs, so "cheap but useless" configs score poorly. The
  comparison always reports all requested policies and both splits; the ablation
  reports all feature-group removals. Split salt/fraction are explicit parameters.

## 8. Data leakage of proprietary content
- **Risk:** committing proprietary RTL, internal names, credentials, or paths.
- **Mitigation:** only synthetic public toy data; SHAs are clearly placeholders
  (`sha256:...` of a design name); machine metadata is limited to hostname/platform.
  See `RELEASE_CHECKLIST.md` and `.gitignore` (ledger DBs and artifacts are ignored).

## 9. Ingestion of malformed/hostile run records
- **Risk:** `ingest-result` accepts corrupt or forged provenance.
- **Mitigation:** ingestion validates against the `RunRecord` schema (rejecting missing
  fields / bad statuses) before persisting.
- **Test:** `test_ledger.py::test_ingest_rejects_malformed`.

## Residual risks (documented, not eliminated)
- The mock cost model is invented; comparative results are about the *harness*, not any
  real solver. Do not port the numbers to a real tool without re-running.
- The toy suite is too small for statistically strong claims; treat CIs as indicative.
