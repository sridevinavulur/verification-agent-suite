# CDC/RDC Structural Triage Report

> **STRUCTURAL HEURISTIC TRIAGE ONLY. This is NOT a CDC/RDC signoff tool and does not prove any crossing safe or unsafe. Use commercial CDC/RDC signoff for verification-quality results.**

- tool: `cdc-rdc-triage-agent` v0.1.0
- top: `cdc_sync`

## Non-claims
- Does NOT claim the design is CDC clean.
- Does NOT claim the design is RDC clean.
- Does NOT claim any synchronizer is correct.
- Does NOT prove metastability is handled.
- Findings are heuristic and may contain false positives and false negatives.

## Summary
- cdc_crossings: 2
- crossings_without_sync_evidence: 1
- high_severity: 1
- low_severity: 0
- medium_severity: 0
- multi_bit_crossings: 1
- rdc_crossings: 0
- total_crossings: 2

## Findings by module

### Module `cdc_sync`

- clock domains: clk_a, clk_b
- reset domains: rst_a, rst_b

#### [HIGH] score=85 CDC: `bus_a` -> `bus_b` (module `cdc_sync`)

- source domain: `clk=clk_a;rst=rst_a` @ cdc_sync.sv:32:13
- destination domain: `clk=clk_b;rst=rst_b` @ cdc_sync.sv:61:13
- width: 8  (MULTI-BIT)
- synchronizer evidence: no_synchronizer_evidence
- HEURISTIC finding
- rationale:
  - register 'bus_b' (clk=clk_b) reads register 'bus_a' (clk=clk_a) across clock domains
  - no back-to-back single-fan-in flop chain detected at the sampling flop -- no structural synchronizer evidence
  - transferred signal 'bus_a' is 8 bits wide -- multi-bit CDC needs gray-code/handshake; a plain FF sync is insufficient

#### [INFO] score=25 CDC: `flag_a` -> `sync_ff1` (module `cdc_sync`)

- source domain: `clk=clk_a;rst=rst_a` @ cdc_sync.sv:31:13
- destination domain: `clk=clk_b;rst=rst_b` @ cdc_sync.sv:42:13
- width: 1
- synchronizer evidence: multi_ff_synchronizer_candidate (depth 3)
- HEURISTIC finding
- rationale:
  - register 'sync_ff1' (clk=clk_b) reads register 'flag_a' (clk=clk_a) across clock domains
  - 3 back-to-back flops in destination clock domain 'clk_b' with single fan-in starting at the sampling flop 'sync_ff1' -- 3-FF synchronizer candidate (HEURISTIC; clock/domain evidence only, correctness NOT proven)

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

