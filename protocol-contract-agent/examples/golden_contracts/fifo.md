# Interface Contract: sync_fifo__fifo

- Protocol: **fifo**
- Module: `sync_fifo`

> All items below are **candidates for human review**. Nothing here is verified, proven, or signoff-quality.

## Signal-role mapping

| Role | Signal | Ownership | Required | Source |
|------|--------|-----------|----------|--------|
| push | `wr_en` | env_input | yes | sync_fifo.sv:5 |
| pop | `rd_en` | env_input | yes | sync_fifo.sv:6 |
| full | `full` | dut_output | no | sync_fifo.sv:7 |
| empty | `empty` | dut_output | no | sync_fifo.sv:8 |
| count | `count` | dut_output | no | sync_fifo.sv:9 |

## Clock / reset mapping

- Clock: `clk` (env_input, id=sync_fifo.clk, sync_fifo.sv:3)
- Reset: `rst_n` (env_input, id=sync_fifo.rst_n, sync_fifo.sv:4)
- Reset polarity: **active_low**
- Reset sync: **asynchronous**
- Reset behavior: Asynchronous, active-low reset (rst_n): registers reset when rst_n==0; properties use `disable iff (!rst)`.

## Environmental assumptions

_None._

## Design guarantees

- **g_count_bound**: Occupancy count never exceeds depth 16 (models MULTIPLE outstanding entries, not a single transaction).
- **g_full_iff_count**: full is asserted exactly when count == depth (16).
- **g_empty_iff_count**: empty is asserted exactly when count == 0.
- **g_reset_empty**: While reset is asserted, the FIFO reports empty.

## Candidate SVA + cover properties

### p_sync_fifo_no_overflow  _( assert / negative )_
Overflow: a push while full must never occur (asserted as the negation of the bad event).
```systemverilog
p_sync_fifo_no_overflow: assert property (
  @(posedge clk) disable iff (!rst_n) !(full && wr_en)
);
```

### p_sync_fifo_no_underflow  _( assert / negative )_
Underflow: a pop while empty must never occur.
```systemverilog
p_sync_fifo_no_underflow: assert property (
  @(posedge clk) disable iff (!rst_n) !(empty && rd_en)
);
```

### p_sync_fifo_count_bound  _( assert / guarantee )_
Occupancy count never exceeds depth 16 (models MULTIPLE outstanding entries, not a single transaction).
```systemverilog
p_sync_fifo_count_bound: assert property (
  @(posedge clk) disable iff (!rst_n) count <= 16
);
```

### p_sync_fifo_full_iff_count  _( assert / guarantee )_
full is asserted exactly when count == depth (16).
```systemverilog
p_sync_fifo_full_iff_count: assert property (
  @(posedge clk) disable iff (!rst_n) full == (count == 16)
);
```

### p_sync_fifo_empty_iff_count  _( assert / guarantee )_
empty is asserted exactly when count == 0.
```systemverilog
p_sync_fifo_empty_iff_count: assert property (
  @(posedge clk) disable iff (!rst_n) empty == (count == 0)
);
```

### p_sync_fifo_reset_empty  _( assert / guarantee )_
While reset is asserted, the FIFO reports empty.
```systemverilog
p_sync_fifo_reset_empty: assert property (
  @(posedge clk) (!rst_n) |-> (empty)
);
```

### p_sync_fifo_fill_cover  _( cover / cover )_
Cover reaching full.
```systemverilog
p_sync_fifo_fill_cover: cover property (
  @(posedge clk) disable iff (!rst_n) full
);
```

### p_sync_fifo_drain_cover  _( cover / cover )_
Cover reaching empty after activity.
```systemverilog
p_sync_fifo_drain_cover: cover property (
  @(posedge clk) disable iff (!rst_n) empty
);
```

### p_sync_fifo_concurrent_cover  _( cover / cover )_
Cover simultaneous push and pop.
```systemverilog
p_sync_fifo_concurrent_cover: cover property (
  @(posedge clk) disable iff (!rst_n) wr_en && rd_en
);
```

## Negative scenarios

- **n_overflow** (assert): Overflow: a push while full must never occur (asserted as the negation of the bad event).
- **n_underflow** (assert): Underflow: a pop while empty must never occur.

## Property dependencies

_None._

## Review checklist

- [REVIEW] (info) **reset_polarity**: Confirm reset 'rst_n' is active_low and that disable-iff semantics match the intended reset behavior.
- [REVIEW] (warning) **fifo_outstanding**: Confirm occupancy is modeled with a real count/pointer (multiple outstanding entries), NOT collapsed to a single in-flight transaction.
- [REVIEW] (warning) **fifo_depth**: Confirm the declared depth matches the RTL parameter.
- [REVIEW] (info) **fifo_push_pop_ownership**: push (env_input) / pop (env_input): confirm which side drives each and whether push/pop can be asserted while full/empty (protocol choice).

## Limitations

- Every property is a CANDIDATE for human review. Nothing here is verified, proven, or signoff-quality. No formal tool or simulator is run.
- Candidate SVA is rendered deterministically and is intended to be compiled OFFLINE by a separate tool; syntactic acceptance would not imply semantic correctness.
- Role -> signal bindings come from the request; the tool does not infer which signal plays which protocol role.
- Clock/reset polarity is taken from the request or the manifest candidates and is NEVER inferred by name. Unknown polarity blocks polarity-dependent properties instead of guessing.
- Structural checks (combinational deadlock, real synchronizer presence, arbiter fairness, exact width matching) are NOT performed.
- FIFO/credit contracts require explicit depth/max_credits and a count/credit signal to bound occupancy; without them, occupancy bounds are omitted rather than invented.

