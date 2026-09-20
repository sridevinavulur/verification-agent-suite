# Interface Contract: arbiter__req_grant__port0

- Protocol: **req_grant**
- Module: `arbiter`
- Instance: `port0`

> All items below are **candidates for human review**. Nothing here is verified, proven, or signoff-quality.

## Signal-role mapping

| Role | Signal | Ownership | Required | Source |
|------|--------|-----------|----------|--------|
| req | `req0` | env_input | yes | arbiter.sv:4 |
| grant | `gnt0` | dut_output | yes | arbiter.sv:5 |

## Clock / reset mapping

- Clock: `clk` (env_input, id=arbiter.clk, arbiter.sv:2)
- Reset: `rst` (env_input, id=arbiter.rst, arbiter.sv:3)
- Reset polarity: **active_high**
- Reset sync: **synchronous**
- Reset behavior: Synchronous, active-high reset: registers reset on clock edge when reset==1; properties use `disable iff (rst)`.

## Environmental assumptions

- **a_req_stable**: A request is held stable until it is granted.  ⚠️ REVIEW: constrains non-input
  - review: assumption references non-input signal(s): gnt0(dut_output). Constraining a DUT output/internal as an environment assumption requires explicit human review.

## Design guarantees

- **g_no_spurious_grant**: Grant is asserted only while (or after) a request is present (no spurious grant).
- **g_grant_latency**: A sustained request receives a grant within [1:3] cycles.

## Candidate SVA + cover properties

### p_arbiter_no_spurious_grant  _( assert / guarantee )_
Grant is asserted only while (or after) a request is present (no spurious grant).
```systemverilog
p_arbiter_no_spurious_grant: assert property (
  @(posedge clk) disable iff (rst) (gnt0) |-> (req0)
);
```

### p_arbiter_grant_latency  _( assert / guarantee )_
A sustained request receives a grant within [1:3] cycles.
- depends on: p_arbiter_no_spurious_grant
```systemverilog
p_arbiter_grant_latency: assert property (
  @(posedge clk) disable iff (rst) (req0) |-> ##[1:3] (gnt0)
);
```

### p_arbiter_req_stable_assume  _( assume / assumption )_
A request is held stable until it is granted.
- note: assumption references non-input signal(s): gnt0(dut_output). Constraining a DUT output/internal as an environment assumption requires explicit human review.
```systemverilog
p_arbiter_req_stable_assume: assume property (
  @(posedge clk) disable iff (rst) (req0 && !gnt0) |=> (req0)
);
```

### p_arbiter_grant_cover  _( cover / cover )_
Cover at least one request that is granted.
```systemverilog
p_arbiter_grant_cover: cover property (
  @(posedge clk) disable iff (rst) req0 && gnt0
);
```

## Negative scenarios

_None._

## Property dependencies

- `p_arbiter_grant_latency` -> p_arbiter_no_spurious_grant  (consequent property assumes the antecedent property holds (e.g. latency guarantee assumes no-spurious guarantee).)

## Review checklist

- [REVIEW] (info) **reset_polarity**: Confirm reset 'rst' is active_high and that disable-iff semantics match the intended reset behavior.
- [REVIEW] (warning) **rg_multi_requestor**: If multiple requestors share this grant, confirm this single-requestor contract is per-requestor and mutual exclusion of grants is a SEPARATE property (not modeled as one).
- [REVIEW] (warning) **rg_ownership**: Confirm grant (dut_output) is a DUT output and req (env_input) is the requestor side.

## Warnings

- **WARNING** [assume_on_output] [a_req_stable] assumption references non-input signal(s): gnt0(dut_output). Constraining a DUT output/internal as an environment assumption requires explicit human review.

## Limitations

- Every property is a CANDIDATE for human review. Nothing here is verified, proven, or signoff-quality. No formal tool or simulator is run.
- Candidate SVA is rendered deterministically and is intended to be compiled OFFLINE by a separate tool; syntactic acceptance would not imply semantic correctness.
- Role -> signal bindings come from the request; the tool does not infer which signal plays which protocol role.
- Clock/reset polarity is taken from the request or the manifest candidates and is NEVER inferred by name. Unknown polarity blocks polarity-dependent properties instead of guessing.
- Structural checks (combinational deadlock, real synchronizer presence, arbiter fairness, exact width matching) are NOT performed.
- FIFO/credit contracts require explicit depth/max_credits and a count/credit signal to bound occupancy; without them, occupancy bounds are omitted rather than invented.

