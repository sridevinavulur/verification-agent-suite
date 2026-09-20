# Threat Model

Scope: a read-only, deterministic SVA static-review tool with an optional,
mocked LLM explanation layer. Risks below are framed per BUILD_STANDARD.

## 1. Hallucination / overclaiming

* **Risk:** presenting heuristic results as sound, especially vacuity.
* **Mitigation:** `VACUITY_RISK` and other heuristic findings carry
  `heuristic=True` and are rendered `[heuristic]`. README, ARCHITECTURE, and the
  checklist item all state that this is **not** complete vacuity detection. The
  tool never emits PASS/proven and never calls an assertion correct.

## 2. Unsafe assumptions / soundness

* **Risk:** an assumption silently constraining design outputs or internal state
  can mask real bugs and unsoundly restrict a proof.
* **Mitigation:** `ASSUME_CONSTRAINS_OUTPUT` (ERROR) flags any `assume` that
  references a manifest `output`/`internal` signal, and recommends a human
  decision rather than an automatic rewrite. The tool never converts a guarantee
  to an assumption or vice-versa.

## 3. Ungrounded identifiers

* **Risk:** a property referencing a signal that does not exist (typo, wrong
  name) looks fine but verifies nothing meaningful.
* **Mitigation:** `UNDECLARED_SIGNAL` (ERROR) requires every identifier to exist
  in the RTL Intent Manifest (or be a clock/reset candidate). Sized literals are
  stripped before grounding to avoid false positives.

## 4. False negatives from parser limits

* **Risk:** the constrained parser misclassifies exotic SVA and skips checks.
* **Mitigation:** unsupported constructs are captured as raw text (never coerced
  into false structure); fields the parser cannot determine are `None`, so checks
  reason about "missing" vs "present". Limitations are documented in the README.
  This tool is explicitly a *pre-filter*, not a replacement for a real front-end
  or a formal engine.

## 5. Data leakage

* **Risk:** committing proprietary RTL, signal names, or paths.
* **Mitigation:** examples are toy public modules (counter/handshake/FIFO
  patterns). No employer/customer names, credentials, or internal tool names.
  `.gitignore` excludes venvs, caches, and local artifacts.

## 6. Reproducibility

* **Risk:** non-deterministic output makes golden tests flaky.
* **Mitigation:** all logic is pure/deterministic; findings are sorted by a
  stable key; the mock LLM is deterministic and used by default; golden fixtures
  are checked in and regenerated only via an explicit script. No network in
  tests or CI.

## 7. LLM layer misuse

* **Risk:** an LLM inventing or suppressing findings.
* **Mitigation:** the LLM layer is architecturally confined to setting the
  `explanation` field on already-produced findings; a test asserts findings are
  unchanged in count, `check_id`, severity, and location after annotation.
