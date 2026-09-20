# RTL Intent Manifest

- **Tool**: rtl-intent v0.1.0
- **Schema version**: 0.1.0
- **Parser adapter**: builtin v0.1.0
- **Top module**: counter
- **Modules**: 1
- **Input files**: counter.sv

## Hierarchy graph

_No instantiations found (flat / leaf design)._

## Module inventory

| Module | Ports | Params | Nets | Registers | assign | always_ff | always_comb |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `counter` | 7 | 1 | 1 | 1 | 2 | 1 | 0 |

## Module `counter`

_Declared at counter.sv:3:1._

### Parameters

| Name | Default | Kind | Location |
| --- | --- | --- | --- |
| `WIDTH` | `8` | parameter | counter.sv:4:5 |

### Ports

| Name | Direction | Type | Width | Location |
| --- | --- | --- | --- | --- |
| `clk` | input | wire | `` | counter.sv:6:5 |
| `rst_n` | input | wire | `` | counter.sv:7:5 |
| `en` | input | wire | `` | counter.sv:8:5 |
| `load` | input | wire | `` | counter.sv:9:5 |
| `load_value` | input | wire | `[WIDTH - 1:0]` | counter.sv:10:5 |
| `count` | output | reg | `[WIDTH - 1:0]` | counter.sv:11:5 |
| `overflow` | output | wire | `` | counter.sv:12:5 |

### Nets

| Name | Kind | Width | Unpacked | Location |
| --- | --- | --- | --- | --- |
| `next_count` | wire | `[WIDTH - 1:0]` | `` | counter.sv:15:5 |

### Registers (nonblocking targets under always_ff)

| Name | Driven in proc # | Location |
| --- | ---: | --- |
| `count` | 0 | counter.sv:22:13 |

### Continuous assignments

| LHS | RHS | Location |
| --- | --- | --- |
| `next_count` | `count + 1'b1` | counter.sv:17:5 |
| `overflow` | `en & (count == {WIDTH {1'b1}})` | counter.sv:18:5 |

### Procedures

| # | Kind | Sensitivity | Targets | Location |
| ---: | --- | --- | --- | --- |
| 0 | always_ff | posedge clk, negedge rst_n | `count` | counter.sv:20:5 |

### Clock & reset candidates (heuristic)

**Clocks**

| Signal | Confidence | Rationale |
| --- | ---: | --- |
| `clk` | 1.000 | edge-sensitive in always_ff (proc #0); name matches clock convention |

**Resets**

| Signal | Confidence | Polarity | Sync | Rationale |
| --- | ---: | --- | --- | --- |
| `rst_n` | 0.900 | active_low | asynchronous | edge-sensitive in always_ff (proc #0) with reset-like name; name matches reset convention |

## Unresolved constructs

_None. Every construct in the input was within the supported subset._

## Parser limitations (v0.1 subset)

Supported constructs:

- module/endmodule
- ANSI and non-ANSI port lists
- parameter/localparam
- input/output/inout ports with width
- wire/reg/logic declarations
- continuous assign
- always/always_ff/always_comb blocks
- blocking and nonblocking assignments
- basic module instances (named and positional)

**Not** supported (not full SystemVerilog semantics):

- generate/for-generate blocks
- functions and tasks
- structs/unions/enums/typedefs
- interfaces/modports/packages
- SystemVerilog assertions (SVA)
- preprocessor macros beyond raw passthrough
- case/casez/casex statement bodies (recorded, body not modeled)
- hierarchical/dotted assignment targets
- parameter expression evaluation (ranges kept as text)

> Clock/reset candidates and confidence scores are **heuristic** name- and structure-based signals, not a formal determination of clocking or reset intent.

