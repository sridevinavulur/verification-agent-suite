# Interface Contract: vr_producer__valid_ready__out_stream

- Protocol: **valid_ready**
- Module: `vr_producer`
- Instance: `out_stream`

> All items below are **candidates for human review**. Nothing here is verified, proven, or signoff-quality.

## Signal-role mapping

| Role | Signal | Ownership | Required | Source |
|------|--------|-----------|----------|--------|
| valid | `out_valid` | dut_output | yes | valid_ready.sv:5 |
| ready | `out_ready` | env_input | yes | valid_ready.sv:6 |
| data | `out_data` | dut_output | no | valid_ready.sv:7 |

## Clock / reset mapping

- Clock: `clk` (env_input, id=vr_producer.clk, valid_ready.sv:3)
- Reset: `rst_n` (env_input, id=vr_producer.rst_n, valid_ready.sv:4)
- Reset polarity: **active_low**
- Reset sync: **asynchronous**
- Reset behavior: Asynchronous, active-low reset (rst_n): registers reset when rst_n==0; properties use `disable iff (!rst)`.

## Environmental assumptions

_None._

## Design guarantees

- **g_valid_stable**: While valid is asserted and not accepted, valid remains asserted (DUT source holds valid until handshake).
- **g_data_stable**: Payload data is held stable while valid is asserted and not yet accepted.

## Candidate SVA + cover properties

### p_vr_producer_valid_stable  _( assert / guarantee )_
While valid is asserted and not accepted, valid remains asserted (DUT source holds valid until handshake).
```systemverilog
p_vr_producer_valid_stable: assert property (
  @(posedge clk) disable iff (!rst_n) (out_valid && !out_ready) |=> (out_valid)
);
```

### p_vr_producer_data_stable  _( assert / guarantee )_
Payload data is held stable while valid is asserted and not yet accepted.
```systemverilog
p_vr_producer_data_stable: assert property (
  @(posedge clk) disable iff (!rst_n) (out_valid && !out_ready) |=> $stable(out_data)
);
```

### p_vr_producer_handshake_cover  _( cover / cover )_
Cover at least one completed valid/ready handshake.
```systemverilog
p_vr_producer_handshake_cover: cover property (
  @(posedge clk) disable iff (!rst_n) out_valid && out_ready
);
```

### p_vr_producer_accept_without_valid_cover  _( cover / negative )_
A transfer (ready high) must not be claimed complete without valid; assert ready implies valid is meaningful only when valid is set. Here we cover the illegal combination for review, not assert it away.
```systemverilog
p_vr_producer_accept_without_valid_cover: cover property (
  @(posedge clk) disable iff (!rst_n) out_ready && !out_valid
);
```

## Negative scenarios

- **n_accept_without_valid** (cover): A transfer (ready high) must not be claimed complete without valid; assert ready implies valid is meaningful only when valid is set. Here we cover the illegal combination for review, not assert it away.

## Property dependencies

_None._

## Review checklist

- [REVIEW] (info) **reset_polarity**: Confirm reset 'rst_n' is active_low and that disable-iff semantics match the intended reset behavior.
- [REVIEW] (warning) **vr_direction**: Confirm role directions: valid=dut_output, ready=env_input. Is 'valid' produced by the side you intend to constrain?
- [REVIEW] (info) **vr_no_combinational_deadlock**: Confirm ready does not combinationally depend on valid in a way that creates a deadlock (not checked structurally here).

## Limitations

- Every property is a CANDIDATE for human review. Nothing here is verified, proven, or signoff-quality. No formal tool or simulator is run.
- Candidate SVA is rendered deterministically and is intended to be compiled OFFLINE by a separate tool; syntactic acceptance would not imply semantic correctness.
- Role -> signal bindings come from the request; the tool does not infer which signal plays which protocol role.
- Clock/reset polarity is taken from the request or the manifest candidates and is NEVER inferred by name. Unknown polarity blocks polarity-dependent properties instead of guessing.
- Structural checks (combinational deadlock, real synchronizer presence, arbiter fairness, exact width matching) are NOT performed.
- FIFO/credit contracts require explicit depth/max_credits and a count/credit signal to bound occupancy; without them, occupancy bounds are omitted rather than invented.

