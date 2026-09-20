# Supported RTL forms (v0.1)

The subset parser is intentionally narrow. Everything in the subset works;
anything outside it is surfaced, not silently dropped.

## Supported

| Construct | Example | Notes |
|---|---|---|
| Module | `module m(...); ... endmodule` | first module with sequential logic is analyzed |
| ANSI/non-ANSI ports | `input wire clk`, `output reg [7:0] q` | direction + name captured |
| Edge-sensitive block | `always @(posedge clk or negedge rst_n)` / `always_ff` | classified async if reset in edge list |
| Level block | `always_comb`, `always @*` | not treated as sequential/reset |
| Reset guard | `if (!rst_n) ...` / `if (rst) begin ... end` | **first** if in an edge block only |
| begin/end and single-statement branches | `if (rst) begin a<=0; b<=0; end else ...` | nesting handled |
| Nonblocking assign | `q <= d;` | reset value attributed only when RHS is constant |
| Constants | `8'b0`, `4'd0`, `0`, `1'b1` | recognised as reset values |
| Comments | `// ...`, `/* ... */` | stripped, offsets preserved |

## Reset polarity evidence

| Evidence | Vote |
|---|---|
| `negedge rst_n` (async) | active-low |
| `posedge rst` (async) | active-high |
| `if (!rst_n)` / `if (~rst)` / `== 0` | active-low |
| `if (rst)` (bare) / `== 1` | active-high |
| name suffix `_n` | active-low (weak) |

Conflicting or absent evidence → `unknown` + ambiguity. Never guessed.

## Not supported (surfaced as unresolved / out of scope)

- `always_latch`, generate blocks, `case`-based reset decode
- functions/tasks, interfaces, packages, classes, assertions in RTL
- parameterised width arithmetic evaluation (ranges kept as text)
- reset synchronizer *correctness* (structural detection only)
- multiple `if`-guards competing as resets within one block
