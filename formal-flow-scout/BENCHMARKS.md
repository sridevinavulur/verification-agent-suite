# Benchmarks

All benchmark inputs are **public toy RTL authored in this repository** (MIT).
There is no proprietary content and no external dataset dependency.

## Correctness benchmarks (golden COIs)

| Example | Property seeds | Expected COI highlight | Test |
| --- | --- | --- | --- |
| `counter.v` | `at_max, value` | includes `cnt`, `clk`, `rst`, guard `en` | `test_counter_known_coi` |
| `fifo_ctrl.v` | `full, push, occ` | **excludes** `wr_ptr`, `rd_ptr`; flags `occ↔full` cycle | `test_fifo_excludes_unrelated_pointers`, `test_fifo_has_sequential_cycle` |
| `two_clock.v` | `mismatch` | 2 clock domains → HIGH multi-clock risk | `test_two_clock_flags_multi_clock_risk` |

## Scaling smoke test (generated RTL)

`tests/test_perf.py::test_generated_pipeline_coi_scales` builds a synthetic
shift-register pipeline of `stages=200 × width=64` (~12,801 nodes, ~25k edges),
computes a COI, and asserts:

- exact expected COI size (`stages + 1`), and
- completion well under a 5 s bound (typically single-digit milliseconds).

This validates the CSR core on a non-trivial graph. It is **not** a calibrated
throughput benchmark — no absolute performance numbers are claimed. To measure
wall-clock on your machine:

```bash
python - <<'PY'
import time
from tests.test_perf import _generate_pipeline
from formal_flow_scout.graph_core import PackedGraph
g = _generate_pipeline(2000, 128)          # ~256k regs
pg = PackedGraph(g)
seed = 1 + (2000-1)*128
t = time.perf_counter()
coi = pg.backward_coi([seed], combinational_only=False, include_control=False)
print(len(coi), "nodes in", round(time.perf_counter()-t, 4), "s")
PY
```

## C++ vs Python

The optional C++ core is validated for **equality** with Python
(`test_cpp_agrees_with_python`), not benchmarked for speed here. Any speed claim
would require controlled runs on stated hardware/compiler — out of scope for
v0.1.

## Exclusions / threats to validity

- Generated graphs are regular (pipeline structure); real RTL has irregular
  fan-in/out. Scaling on generated graphs does not predict worst-case behaviour.
- Single-machine, single-run timings are not statistically robust; treat the
  smoke test as a correctness-at-scale check only.
