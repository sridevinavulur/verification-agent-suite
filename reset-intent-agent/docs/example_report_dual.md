# Reset Intent Report — `dual_reset_domains`

> **Structural detection, not verified intent.** All reset-domain relationships are **HEURISTIC** until reviewed. Reset polarity is never inferred silently. Candidate SVA is **candidate** only — not verified.

- Tool: `reset-intent-agent` v0.1.0
- Schema: 0.1.0

## Reset candidates (STRUCTURAL)

| Signal | Polarity | Sync | Confidence | Port | Fanout |
|---|---|---|---|---|---|
| `rst_a_n` (dual_reset_domains.sv:14:5) | active_low | asynchronous | 1.00 | True | 1 reg |
| `rst_b` (dual_reset_domains.sv:21:5) | active_high | synchronous | 0.85 | True | 1 reg |

### Polarity evidence
- **`rst_a_n`** → `active_low`
  - [edge] async negedge -> active-low → votes `active_low`
  - [guard_expr] guard negates reset -> active-low: `!rst_a_n` → votes `active_low`
  - [name_suffix] name suffix _n suggests active-low → votes `active_low`
- **`rst_b`** → `active_high`
  - [guard_expr] bare reset guard -> active-high: `rst_b` → votes `active_high`

## Reset domains (HEURISTIC)

- **D0** — reset `rst_a_n` (active_low, asynchronous) — members: `reg_a`
- **D1** — reset `rst_b` (active_high, synchronous) — members: `reg_b`

## Possible reset-domain crossings (HEURISTIC)

- `reg_a` (D0) → `reg_b` (D1) — medium (dual_reset_domains.sv:25:13)
  - 'reg_a' (reset rst_a_n) feeds 'reg_b' (reset rst_b); possible reset-domain crossing

## Candidate reset-behavior SVA (CANDIDATE — not verified)

### P001 `p_reset_state_reg_a` — status: candidate

```systemverilog
p_reset_state_reg_a: assert property (
  @(posedge clk) (!rst_a_n) |-> (reg_a == 8'h00)
);
```
- Rationale: Register 'reg_a' is assigned '8'h00' under reset 'rst_a_n'.
- Review: Candidate only. Not verified. Confirm clock, polarity, and value.

### P002 `p_reset_state_reg_b` — status: candidate

```systemverilog
p_reset_state_reg_b: assert property (
  @(posedge clk) (rst_b) |-> (reg_b == 8'h00)
);
```
- Rationale: Register 'reg_b' is assigned '8'h00' under reset 'rst_b'.
- Review: Candidate only. Not verified. Confirm clock, polarity, and value.

## Risks & ambiguities

### Risks
- **MEDIUM** (mixed_sync) [HEURISTIC]: Module mixes synchronous and asynchronous resets. Verify reset assertion/deassertion ordering and recovery.
- **MEDIUM** (rdc) [HEURISTIC]: Possible reset-domain crossing reg_a (D0) -> reg_b (D1). Heuristic; requires RDC review. (dual_reset_domains.sv:25:13)

## Test / cover recommendations

- [cover] REC001 (`rst_a_n`): Cover that reset 'rst_a_n' is asserted at least once (reset-assertion reachability).
- [cover] REC002 (`rst_a_n`): Cover reset deassertion of 'rst_a_n' followed by normal operation (reset recovery).
- [cover] REC003 (`rst_b`): Cover that reset 'rst_b' is asserted at least once (reset-assertion reachability).
- [cover] REC004 (`rst_b`): Cover reset deassertion of 'rst_b' followed by normal operation (reset recovery).
- [directed_test] REC005: Directed test: assert reset mid-transaction and confirm all reset targets return to their reset values (interface quiescence).
