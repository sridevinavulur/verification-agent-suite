# Threat Model

Scope: a deterministic verification-plan draft generator with a mock LLM. The
risks below are the ones called out by `BUILD_STANDARD.md`.

## 1. Hallucination / over-claiming

- **Risk:** readers treat generated features, techniques, or assertions as an
  approved, complete, or correct plan.
- **Mitigations:**
  - Every generated item is `proposed` until a human approves it; the report
    header lists explicit **non-claims**.
  - Assertion candidates are labelled **sketches**; they intentionally contain
    placeholder tokens (`<antecedent>`, `<error_cond>`) and are never claimed to
    compile or be sound.
  - Classification/technique/risk are labelled **heuristics** in the report.
  - The mock LLM only phrases rationale text; it makes no structural decisions.

## 2. Unsafe assumptions

- **Risk:** silently dropping requirements or signals, or assuming coverage.
- **Mitigations:**
  - Interface signals never referenced by a requirement are surfaced as explicit
    `ASSUMPTION` ambiguities (not hidden).
  - Manifest reset/clock candidates missing from the spec/glossary are surfaced
    as `MISSING_REQUIREMENT` / `UNMAPPED_MANIFEST_RESET`.
  - The traceability matrix marks uncovered requirements with ❌ and a warning.

## 3. Data leakage

- **Risk:** proprietary/employer/customer content entering the repo.
- **Mitigations:**
  - Examples are public, generic toy designs (a sync FIFO, a GPIO controller).
  - No secrets, credentials, internal tool names, or proprietary paths.
  - The mock LLM performs **no network calls**; a non-`mock` adapter is refused.

## 4. Reproducibility

- **Risk:** non-deterministic output undermines review and audit.
- **Mitigations:**
  - Deterministic rules; hash-seeded mock LLM; sorted-key JSON.
  - Provenance records tool/version, LLM adapter, command, input files, and
    input SHA-256 hashes for real runs.
  - Golden tests assert byte-stable Markdown/JSON.

## 5. Authority / integrity

- **Risk:** the agent promoting its own content or editing source-of-truth data.
- **Mitigations:**
  - Approval is a separate, human-driven step (`apply_decisions`); the agent
    cannot emit `APPROVED`.
  - The tool never writes back to RTL, spec, or manifest inputs.

## Residual risk

Keyword classification and the risk rubric are heuristics and can mis-categorize
unusual requirement phrasings. This is why **human approval is mandatory** before
any item is treated as part of the real plan.
