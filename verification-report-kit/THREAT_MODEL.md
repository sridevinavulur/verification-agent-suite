# Threat Model

`verification-report-kit` is a deterministic presentation library with no
network, no LLM, and no execution authority. Its risk surface is small but
real, because its output is read by engineers making signoff decisions.

## 1. Misrepresentation of results (integrity)

**Risk**: a report that makes an unproven/failed result *look* passed.

**Mitigations**:
- The library never invents, upgrades, or reclassifies a result. It renders the
  caller's `Status` verbatim; there is no code path that turns TIMEOUT / ERROR /
  INCONCLUSIVE into PASS.
- The result vocabulary is a closed enum (`Status`) matching `BUILD_STANDARD.md`,
  including `COMPILED` = "property compiled" (syntax only, not proven).
- Heuristic findings carry a `heuristic` flag rendered as a visible HEURISTIC
  badge so heuristic output is never presented as sound/formal.
- Tested: `test_findings_report_key_content` asserts the HEURISTIC badge and the
  COMPILED/INCONCLUSIVE outcomes survive rendering.

**Residual**: the library cannot detect a caller that *lies* in the model (e.g.
labels a real failure PASS). Correct classification is the caller's
responsibility; this tool only faithfully renders what it is given.

## 2. Content injection / XSS (data safety)

**Risk**: report text (finding descriptions, signal names, commands) containing
`<script>` or markup could inject code into the rendered HTML.

**Mitigations**:
- Every caller-supplied value passes through `html.escape(..., quote=True)`
  before entering the document. Only the fixed template + CSS are literal.
- Tested: `test_html_escaping` confirms `<b>` in a title is escaped, not emitted
  as a tag.

**Residual**: the report is meant to be opened locally/internally. It is not a
multi-tenant web page; there is no CSP because there are no external resources
at all (see #3).

## 3. Data exfiltration via external resources (data leakage)

**Risk**: a report that beacons out (loads a remote font/image/script) could leak
that the report was opened, or its context.

**Mitigations**:
- Output is 100% self-contained: inline CSS, no `<script>`, `<link>`, `src=`,
  `@import`, or `url(...)`, no `http(s)://`.
- Tested: `test_html_is_self_contained` greps the output for all of these.

## 4. Reproducibility (evidence integrity)

**Risk**: nondeterministic reports (embedded timestamps/ordering) break golden
tests and audit reproduction.

**Mitigations**:
- No `datetime.now()`/RNG in the render path; timestamps are caller-supplied.
- Stable JSON key order + trailing newline; stable HTML fragment ordering.
- Tested: `test_html_deterministic`, `test_json_deterministic`.

## 5. Sensitive data in examples (leakage)

**Risk**: shipping proprietary RTL / customer names / internal paths in fixtures.

**Mitigations**: `examples/` and `examples_data.py` use only invented toy DUTs
(`dut_alu`, `fifo_ctrl`) and placeholder hashes/SHAs. No secrets or real paths.
This is a review checklist item for any tool that ships its own example reports.

## 6. Denial of service (robustness)

**Risk**: pathologically large models (millions of rows) could produce huge HTML.

**Status**: out of scope for v0.1 — callers control their own report size. The
renderer streams nothing but is linear in input size; no quadratic blowups. A
future phase could add row caps (the reference capped unreachability rows).

## Non-claims

- This tool does **not** validate that verification results are correct.
- It does **not** enforce a human-approval gate; that belongs to the calling
  agent per `BUILD_STANDARD.md`.
- It provides no authentication/authorization — the report file's access control
  is whatever the filesystem/host provides.
