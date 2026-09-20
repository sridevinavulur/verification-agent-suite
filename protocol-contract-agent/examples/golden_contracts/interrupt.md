# Interface Contract: irq_ctrl__interrupt

- Protocol: **interrupt**
- Module: `irq_ctrl`

> All items below are **candidates for human review**. Nothing here is verified, proven, or signoff-quality.

## Signal-role mapping

| Role | Signal | Ownership | Required | Source |
|------|--------|-----------|----------|--------|
| irq | `irq` | dut_output | yes | irq_ctrl.sv:6 |
| source | `event_in` | env_input | no | irq_ctrl.sv:4 |
| clear | `irq_clear` | env_input | no | irq_ctrl.sv:5 |

## Clock / reset mapping

- Clock: `clk` (env_input, id=irq_ctrl.clk, irq_ctrl.sv:2)
- Reset: `rst_n` (env_input, id=irq_ctrl.rst_n, irq_ctrl.sv:3)
- Reset polarity: **active_low**
- Reset sync: **asynchronous**
- Reset behavior: Asynchronous, active-low reset (rst_n): registers reset when rst_n==0; properties use `disable iff (!rst)`.

## Environmental assumptions

_None._

## Design guarantees

- **g_irq_sticky**: Interrupt remains asserted until it is cleared/acknowledged (level-sensitive, sticky).
- **g_irq_clears**: After a clear with no pending source event, the interrupt deasserts on the next cycle.
- **g_irq_raise**: A source event raises the interrupt within [1:2] cycles.
- **g_irq_reset_low**: While reset is asserted, the interrupt is deasserted.

## Candidate SVA + cover properties

### p_irq_ctrl_irq_sticky  _( assert / guarantee )_
Interrupt remains asserted until it is cleared/acknowledged (level-sensitive, sticky).
```systemverilog
p_irq_ctrl_irq_sticky: assert property (
  @(posedge clk) disable iff (!rst_n) (irq && !irq_clear) |=> (irq)
);
```

### p_irq_ctrl_irq_clears  _( assert / guarantee )_
After a clear with no pending source event, the interrupt deasserts on the next cycle.
- depends on: p_irq_ctrl_irq_sticky
```systemverilog
p_irq_ctrl_irq_clears: assert property (
  @(posedge clk) disable iff (!rst_n) (irq_clear && !event_in) |=> (!irq)
);
```

### p_irq_ctrl_irq_raise  _( assert / guarantee )_
A source event raises the interrupt within [1:2] cycles.
```systemverilog
p_irq_ctrl_irq_raise: assert property (
  @(posedge clk) disable iff (!rst_n) (event_in) |-> ##[1:2] (irq)
);
```

### p_irq_ctrl_irq_cover  _( cover / cover )_
Cover the interrupt being asserted.
```systemverilog
p_irq_ctrl_irq_cover: cover property (
  @(posedge clk) disable iff (!rst_n) irq
);
```

### p_irq_ctrl_irq_reset_low  _( assert / guarantee )_
While reset is asserted, the interrupt is deasserted.
```systemverilog
p_irq_ctrl_irq_reset_low: assert property (
  @(posedge clk) (!rst_n) |-> (!irq)
);
```

## Negative scenarios

_None._

## Property dependencies

- `p_irq_ctrl_irq_clears` -> p_irq_ctrl_irq_sticky  (consequent property assumes the antecedent property holds (e.g. latency guarantee assumes no-spurious guarantee).)

## Review checklist

- [REVIEW] (info) **irq_source_env**: Confirm the interrupt source is an environment event and not gated by the DUT in a way that changes the contract.
- [REVIEW] (info) **reset_polarity**: Confirm reset 'rst_n' is active_low and that disable-iff semantics match the intended reset behavior.
- [REVIEW] (warning) **irq_edge_vs_level**: Confirm whether the interrupt is level or edge sensitive; these templates assume LEVEL-sensitive sticky behavior.

## Limitations

- Every property is a CANDIDATE for human review. Nothing here is verified, proven, or signoff-quality. No formal tool or simulator is run.
- Candidate SVA is rendered deterministically and is intended to be compiled OFFLINE by a separate tool; syntactic acceptance would not imply semantic correctness.
- Role -> signal bindings come from the request; the tool does not infer which signal plays which protocol role.
- Clock/reset polarity is taken from the request or the manifest candidates and is NEVER inferred by name. Unknown polarity blocks polarity-dependent properties instead of guessing.
- Structural checks (combinational deadlock, real synchronizer presence, arbiter fairness, exact width matching) are NOT performed.
- FIFO/credit contracts require explicit depth/max_credits and a count/credit signal to bound occupancy; without them, occupancy bounds are omitted rather than invented.

