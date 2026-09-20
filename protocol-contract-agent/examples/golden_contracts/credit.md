# Interface Contract: credit_src__credit

- Protocol: **credit**
- Module: `credit_src`

> All items below are **candidates for human review**. Nothing here is verified, proven, or signoff-quality.

## Signal-role mapping

| Role | Signal | Ownership | Required | Source |
|------|--------|-----------|----------|--------|
| send | `send` | dut_output | yes | credit_src.sv:4 |
| credit_return | `credit_ret` | env_input | yes | credit_src.sv:5 |
| credit_count | `credits` | dut_output | no | credit_src.sv:6 |

## Clock / reset mapping

- Clock: `clk` (env_input, id=credit_src.clk, credit_src.sv:2)
- Reset: `rst_n` (env_input, id=credit_src.rst_n, credit_src.sv:3)
- Reset polarity: **active_low**
- Reset sync: **synchronous**
- Reset behavior: Synchronous, active-low reset: registers reset on clock edge when reset==0; properties use `disable iff (!rst)`.

## Environmental assumptions

_None._

## Design guarantees

- **g_credit_bound**: Available credits never exceed max_credits 8 (tracks MULTIPLE outstanding credits).

## Candidate SVA + cover properties

### p_credit_src_no_send_without_credit  _( assert / negative )_
A send must never occur when no credits are available (credit underflow).
```systemverilog
p_credit_src_no_send_without_credit: assert property (
  @(posedge clk) disable iff (!rst_n) !(send && (credits == 0))
);
```

### p_credit_src_credit_bound  _( assert / guarantee )_
Available credits never exceed max_credits 8 (tracks MULTIPLE outstanding credits).
```systemverilog
p_credit_src_credit_bound: assert property (
  @(posedge clk) disable iff (!rst_n) credits <= 8
);
```

### p_credit_src_send_cover  _( cover / cover )_
Cover a send.
```systemverilog
p_credit_src_send_cover: cover property (
  @(posedge clk) disable iff (!rst_n) send
);
```

### p_credit_src_credit_exhausted_cover  _( cover / cover )_
Cover credits reaching zero (back-pressure exercised).
```systemverilog
p_credit_src_credit_exhausted_cover: cover property (
  @(posedge clk) disable iff (!rst_n) credits == 0
);
```

## Negative scenarios

- **n_send_without_credit** (assert): A send must never occur when no credits are available (credit underflow).

## Property dependencies

_None._

## Review checklist

- [REVIEW] (warning) **credit_return_source**: Confirm credit_return is only asserted by the receiver when it genuinely frees a buffer slot (conservation of credits). This is an environment assumption that must be justified.
- [WARN] (warning) **credit_reset_value**: Confirm the credit count's reset/initial value. It is NOT assumed here (no init value is invented).
- [REVIEW] (info) **reset_polarity**: Confirm reset 'rst_n' is active_low and that disable-iff semantics match the intended reset behavior.

## Limitations

- Every property is a CANDIDATE for human review. Nothing here is verified, proven, or signoff-quality. No formal tool or simulator is run.
- Candidate SVA is rendered deterministically and is intended to be compiled OFFLINE by a separate tool; syntactic acceptance would not imply semantic correctness.
- Role -> signal bindings come from the request; the tool does not infer which signal plays which protocol role.
- Clock/reset polarity is taken from the request or the manifest candidates and is NEVER inferred by name. Unknown polarity blocks polarity-dependent properties instead of guessing.
- Structural checks (combinational deadlock, real synchronizer presence, arbiter fairness, exact width matching) are NOT performed.
- FIFO/credit contracts require explicit depth/max_credits and a count/credit signal to bound occupancy; without them, occupancy bounds are omitted rather than invented.

