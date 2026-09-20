# RTL Intent Manifest

- **Tool**: rtl-intent v0.1.0
- **Schema version**: 0.1.0
- **Parser adapter**: builtin v0.1.0
- **Top module**: vr_top
- **Modules**: 3
- **Input files**: valid_ready.sv

## Hierarchy graph

| Parent | Instance | Child module | Defined in inputs |
| --- | --- | --- | --- |
| `vr_top` | `u_producer` | `vr_producer` | yes |
| `vr_top` | `u_consumer` | `vr_consumer` | yes |

## Module inventory

| Module | Ports | Params | Nets | Registers | assign | always_ff | always_comb |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `vr_producer` | 6 | 1 | 1 | 3 | 0 | 1 | 0 |
| `vr_consumer` | 6 | 1 | 0 | 2 | 0 | 1 | 0 |
| `vr_top` | 4 | 1 | 3 | 0 | 0 | 0 | 0 |

## Module `vr_producer`

_Declared at valid_ready.sv:5:1._

### Parameters

| Name | Default | Kind | Location |
| --- | --- | --- | --- |
| `WIDTH` | `8` | parameter | valid_ready.sv:6:5 |

### Ports

| Name | Direction | Type | Width | Location |
| --- | --- | --- | --- | --- |
| `clk` | input | wire | `` | valid_ready.sv:8:5 |
| `rst_n` | input | wire | `` | valid_ready.sv:9:5 |
| `start` | input | wire | `` | valid_ready.sv:10:5 |
| `out_valid` | output | reg | `` | valid_ready.sv:11:5 |
| `out_ready` | input | wire | `` | valid_ready.sv:12:5 |
| `out_data` | output | reg | `[WIDTH - 1:0]` | valid_ready.sv:13:5 |

### Nets

| Name | Kind | Width | Unpacked | Location |
| --- | --- | --- | --- | --- |
| `counter` | reg | `[WIDTH - 1:0]` | `` | valid_ready.sv:16:5 |

### Registers (nonblocking targets under always_ff)

| Name | Driven in proc # | Location |
| --- | ---: | --- |
| `out_valid` | 0 | valid_ready.sv:20:13 |
| `out_data` | 0 | valid_ready.sv:21:13 |
| `counter` | 0 | valid_ready.sv:22:13 |

### Procedures

| # | Kind | Sensitivity | Targets | Location |
| ---: | --- | --- | --- | --- |
| 0 | always_ff | posedge clk, negedge rst_n | `out_valid, out_data, counter` | valid_ready.sv:18:5 |

### Clock & reset candidates (heuristic)

**Clocks**

| Signal | Confidence | Rationale |
| --- | ---: | --- |
| `clk` | 1.000 | edge-sensitive in always_ff (proc #0); name matches clock convention |

**Resets**

| Signal | Confidence | Polarity | Sync | Rationale |
| --- | ---: | --- | --- | --- |
| `rst_n` | 0.900 | active_low | asynchronous | edge-sensitive in always_ff (proc #0) with reset-like name; name matches reset convention |

## Module `vr_consumer`

_Declared at valid_ready.sv:37:1._

### Parameters

| Name | Default | Kind | Location |
| --- | --- | --- | --- |
| `WIDTH` | `8` | parameter | valid_ready.sv:38:5 |

### Ports

| Name | Direction | Type | Width | Location |
| --- | --- | --- | --- | --- |
| `clk` | input | wire | `` | valid_ready.sv:40:5 |
| `rst_n` | input | wire | `` | valid_ready.sv:41:5 |
| `in_valid` | input | wire | `` | valid_ready.sv:42:5 |
| `in_ready` | output | reg | `` | valid_ready.sv:43:5 |
| `in_data` | input | wire | `[WIDTH - 1:0]` | valid_ready.sv:44:5 |
| `last_data` | output | reg | `[WIDTH - 1:0]` | valid_ready.sv:45:5 |

### Registers (nonblocking targets under always_ff)

| Name | Driven in proc # | Location |
| --- | ---: | --- |
| `in_ready` | 0 | valid_ready.sv:50:13 |
| `last_data` | 0 | valid_ready.sv:51:13 |

### Procedures

| # | Kind | Sensitivity | Targets | Location |
| ---: | --- | --- | --- | --- |
| 0 | always_ff | posedge clk, negedge rst_n | `in_ready, last_data` | valid_ready.sv:48:5 |

### Clock & reset candidates (heuristic)

**Clocks**

| Signal | Confidence | Rationale |
| --- | ---: | --- |
| `clk` | 1.000 | edge-sensitive in always_ff (proc #0); name matches clock convention |

**Resets**

| Signal | Confidence | Polarity | Sync | Rationale |
| --- | ---: | --- | --- | --- |
| `rst_n` | 0.900 | active_low | asynchronous | edge-sensitive in always_ff (proc #0) with reset-like name; name matches reset convention |

## Module `vr_top`

_Declared at valid_ready.sv:62:1._

### Parameters

| Name | Default | Kind | Location |
| --- | --- | --- | --- |
| `WIDTH` | `8` | parameter | valid_ready.sv:63:5 |

### Ports

| Name | Direction | Type | Width | Location |
| --- | --- | --- | --- | --- |
| `clk` | input | wire | `` | valid_ready.sv:65:5 |
| `rst_n` | input | wire | `` | valid_ready.sv:66:5 |
| `start` | input | wire | `` | valid_ready.sv:67:5 |
| `observed` | output | wire | `[WIDTH - 1:0]` | valid_ready.sv:68:5 |

### Nets

| Name | Kind | Width | Unpacked | Location |
| --- | --- | --- | --- | --- |
| `valid` | wire | `` | `` | valid_ready.sv:71:5 |
| `ready` | wire | `` | `` | valid_ready.sv:72:5 |
| `data` | wire | `[WIDTH - 1:0]` | `` | valid_ready.sv:73:5 |

### Instances

| Instance | Module | Connections | Location |
| --- | --- | ---: | --- |
| `u_producer` | `vr_producer` | 6 | valid_ready.sv:75:5 |
| `u_consumer` | `vr_consumer` | 6 | valid_ready.sv:84:5 |

### Clock & reset candidates (heuristic)

**Clocks**

| Signal | Confidence | Rationale |
| --- | ---: | --- |
| `clk` | 0.400 | name matches clock convention |

**Resets**

| Signal | Confidence | Polarity | Sync | Rationale |
| --- | ---: | --- | --- | --- |
| `rst_n` | 0.400 | active_low | unknown | name matches reset convention |

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

