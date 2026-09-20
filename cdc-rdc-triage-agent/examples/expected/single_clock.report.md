# CDC/RDC Structural Triage Report

> **STRUCTURAL HEURISTIC TRIAGE ONLY. This is NOT a CDC/RDC signoff tool and does not prove any crossing safe or unsafe. Use commercial CDC/RDC signoff for verification-quality results.**

- tool: `cdc-rdc-triage-agent` v0.1.0
- top: `single_clock`

## Non-claims
- Does NOT claim the design is CDC clean.
- Does NOT claim the design is RDC clean.
- Does NOT claim any synchronizer is correct.
- Does NOT prove metastability is handled.
- Findings are heuristic and may contain false positives and false negatives.

## Summary
- cdc_crossings: 0
- crossings_without_sync_evidence: 0
- high_severity: 0
- low_severity: 0
- medium_severity: 0
- multi_bit_crossings: 0
- rdc_crossings: 0
- total_crossings: 0

## Findings by module

### Module `single_clock`

- clock domains: clk
- reset domains: rst_n

_No candidate CDC/RDC crossings detected in this module._

> Absence of detected crossings is NOT a clean result -- it may reflect the limits of structural heuristics.

## Reviewer checklist
- [ ] Confirm the source and destination clocks are genuinely asynchronous (different frequency/phase or unrelated), not just differently named.
- [ ] For each flagged crossing, confirm an appropriate synchronizer exists and matches the transfer type (single-bit -> N-FF; multi-bit -> gray-code or handshake/FIFO).
- [ ] For every '2-FF synchronizer candidate', verify the flops are actually in the destination domain and have no combinational logic between stages.
- [ ] For every multi-bit crossing, verify a coherent transfer scheme (gray-code counter, req/ack handshake, async FIFO) -- FF sync alone is unsafe.
- [ ] Verify reset-domain crossings: source and destination resets must be sequenced/synchronized so a reset assert/deassert cannot corrupt the destination.
- [ ] Confirm no CDC path is fed by combinational reconvergence of differently-synchronized bits.
- [ ] Run a commercial CDC/RDC signoff tool -- this triage is heuristic and NOT a substitute for structural+functional CDC/RDC verification.

## Limitations
- Structural only: no metastability, glitch, or functional analysis.
- Clock/reset domains come from heuristic candidates in the manifest; a wrong candidate propagates to every finding.
- Data flow is derived from expression *text* (no full AST); complex expressions may under- or over-report identifier references.
- Cross-module (hierarchical) crossings are NOT traced through port connections in this version -- analysis is per-module.
- Parameterized widths that the manifest keeps as text cannot be evaluated, so some multi-bit crossings show width=unknown.
- A '2-FF synchronizer candidate' is structural evidence only and does NOT prove correct metastability handling.
- Generate blocks, functions/tasks, and memories are not modeled by the upstream subset parser and are therefore invisible here.

