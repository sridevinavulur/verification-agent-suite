# RTL Intent Manifest

- **Tool**: rtl-intent v0.1.0
- **Schema version**: 0.1.0
- **Parser adapter**: builtin v0.1.0
- **Top module**: fifo_queue
- **Modules**: 1
- **Input files**: fifo_queue.sv

## Hierarchy graph

_No instantiations found (flat / leaf design)._

## Module inventory

| Module | Ports | Params | Nets | Registers | assign | always_ff | always_comb |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fifo_queue` | 8 | 3 | 5 | 3 | 4 | 3 | 0 |

## Module `fifo_queue`

_Declared at fifo_queue.sv:3:1._

### Parameters

| Name | Default | Kind | Location |
| --- | --- | --- | --- |
| `WIDTH` | `8` | parameter | fifo_queue.sv:4:5 |
| `DEPTH` | `4` | parameter | fifo_queue.sv:4:5 |
| `ADDR` | `2` | parameter | fifo_queue.sv:4:5 |

### Ports

| Name | Direction | Type | Width | Location |
| --- | --- | --- | --- | --- |
| `clk` | input | wire | `` | fifo_queue.sv:8:5 |
| `rst` | input | wire | `` | fifo_queue.sv:9:5 |
| `wr_en` | input | wire | `` | fifo_queue.sv:10:5 |
| `wr_data` | input | wire | `[WIDTH - 1:0]` | fifo_queue.sv:11:5 |
| `rd_en` | input | wire | `` | fifo_queue.sv:12:5 |
| `rd_data` | output | reg | `[WIDTH - 1:0]` | fifo_queue.sv:13:5 |
| `full` | output | wire | `` | fifo_queue.sv:14:5 |
| `empty` | output | wire | `` | fifo_queue.sv:15:5 |

### Nets

| Name | Kind | Width | Unpacked | Location |
| --- | --- | --- | --- | --- |
| `mem` | reg | `[WIDTH - 1:0]` | `[0:DEPTH - 1]` | fifo_queue.sv:18:5 |
| `wr_ptr` | reg | `[ADDR:0]` | `` | fifo_queue.sv:19:5 |
| `rd_ptr` | reg | `[ADDR:0]` | `` | fifo_queue.sv:20:5 |
| `do_write` | wire | `` | `` | fifo_queue.sv:22:5 |
| `do_read` | wire | `` | `` | fifo_queue.sv:23:5 |

### Registers (nonblocking targets under always_ff)

| Name | Driven in proc # | Location |
| --- | ---: | --- |
| `wr_ptr` | 0 | fifo_queue.sv:33:13 |
| `rd_ptr` | 1 | fifo_queue.sv:41:13 |
| `rd_data` | 2 | fifo_queue.sv:49:13 |

### Continuous assignments

| LHS | RHS | Location |
| --- | --- | --- |
| `do_write` | `wr_en & ~full` | fifo_queue.sv:25:5 |
| `do_read` | `rd_en & ~empty` | fifo_queue.sv:26:5 |
| `full` | `(wr_ptr[ADDR] != rd_ptr[ADDR]) && (wr_ptr[ADDR - 1 : 0] == rd_ptr[ADDR - 1 : 0])` | fifo_queue.sv:27:5 |
| `empty` | `(wr_ptr == rd_ptr)` | fifo_queue.sv:29:5 |

### Procedures

| # | Kind | Sensitivity | Targets | Location |
| ---: | --- | --- | --- | --- |
| 0 | always_ff | posedge clk | `wr_ptr` | fifo_queue.sv:31:5 |
| 1 | always_ff | posedge clk | `rd_ptr` | fifo_queue.sv:39:5 |
| 2 | always_ff | posedge clk | `rd_data` | fifo_queue.sv:47:5 |

### Clock & reset candidates (heuristic)

**Clocks**

| Signal | Confidence | Rationale |
| --- | ---: | --- |
| `clk` | 1.000 | edge-sensitive in always_ff (proc #0); edge-sensitive in always_ff (proc #1); edge-sensitive in always_ff (proc #2); name matches clock convention |

**Resets**

| Signal | Confidence | Polarity | Sync | Rationale |
| --- | ---: | --- | --- | --- |
| `rst` | 1.000 | unknown | synchronous | name matches reset convention; reset-like name in always_ff control condition (proc #0); reset-like name in always_ff control condition (proc #1) |

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

