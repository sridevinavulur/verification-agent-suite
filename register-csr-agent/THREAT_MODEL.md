# Threat Model

Scope: risks specific to an LLM-assisted CSR verification package builder. The
tool is deterministic at its core; the only LLM surface is an offline mock
explainer.

## 1. Hallucination / invented semantics

- **Risk:** an LLM invents an access type or a signal mapping, silently
  legitimizing wrong behavior.
- **Mitigation:** `AccessType` is a closed enum. Parsers reject unknown access
  tokens (`ParseError`). The LLM adapter can only write to a discrepancy's
  `explanation` string; it cannot create discrepancies or alter
  `code`/`severity`/`message`. Enforced by
  `test_llm_cannot_change_code_or_severity` and
  `test_llm_does_not_fabricate_discrepancies`.

## 2. False PASS / over-claiming

- **Risk:** presenting candidate assertions as proven, or a clean discrepancy
  report as a correctness proof.
- **Mitigation:** SVA `status` is a constant `"candidate"` and never upgraded.
  README non-claims and the SVA file header state the tool runs no formal engine.
  A clean report is documented as "no defect found by these checks", not proof.

## 3. Unsafe assumptions in grounding

- **Risk:** a normalized-name match is a false positive (e.g. `CTRL` vs
  `ctrl_shadow`), leading to a wrong RTL cross-check.
- **Mitigation:** matching is lexical only (exact / normalized), never value-
  inferred; every match records `match_kind`; the review checklist item RC-001
  requires human confirmation of grounding. Unmatched names are reported.

## 4. Silent data loss on parse

- **Risk:** malformed rows dropped silently, hiding registers/fields.
- **Mitigation:** parsers raise on missing name/address, bad integers, unknown
  access, and (via Pydantic) reset values that overflow a field width. Tests
  cover these rejection paths.

## 5. Data leakage / proprietary content

- **Risk:** committing internal register maps, tool names, or paths.
- **Mitigation:** only public toy examples (`timer`, `gpio`, `uart`, a synthetic
  `buggy_block`) are bundled. No secrets, no network access. CI needs no secrets.

## 6. Reproducibility

- **Risk:** non-deterministic output prevents review/diffing.
- **Mitigation:** stable sort of discrepancies; deterministic mock explainer;
  golden-output tests; `Provenance` with input SHA-256 hashes.

## 7. Misused exit codes in CI

- **Risk:** treating a parse ERROR or a discrepancy as a PASS.
- **Mitigation:** `check`/`package` exit 1 on any ERROR-severity discrepancy;
  `normalize` exits 2 on parse error. Distinct, documented codes.
