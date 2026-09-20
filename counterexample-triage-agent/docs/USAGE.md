# Usage

## Input formats

### JSON trace

```json
{
  "timescale": "1ns",
  "signals": {
    "tb.clk":   {"width": 1, "samples": [[0, "0"], [5, "1"], [10, "0"]]},
    "tb.count": {"width": 4, "samples": [[0, "0000"], [35, "0001"]]}
  }
}
```

`samples` are `[time, value]` pairs. Scalar values are `"0"|"1"|"x"|"z"`; vector
values are MSB-first binary strings (e.g. `"0011"`). Between samples a signal
holds its last value.

### VCD

Standard VCD, common subset. See `examples/toy_counter/counter_fail.vcd`.
Supported: `$timescale`, `$scope`/`$upscope`, `$var wire|reg <w> <code> <name>
[range] $end`, `$enddefinitions`, `#<time>`, scalar (`0!`) and vector
(`b0011 !`) changes. Real (`r...`) dumps are skipped.

### Assertion-failure record

```json
{
  "property_name": "p_inc",
  "property_text": "en |=> count_advanced",
  "source_file": "counter.sva",
  "source_line": 18,
  "clock": "tb.clk",
  "clock_edge": "posedge",
  "reset": "tb.rst",
  "reset_active_high": true,
  "antecedent_signal": "tb.en",
  "consequent_signal": "tb.count_advanced",
  "implication": "non_overlapping",
  "delay_min": 1,
  "delay_max": 1,
  "failure_time": 65
}
```

`antecedent_signal` / `consequent_signal` are the trace signals whose truth the
tool uses to locate activation and divergence. For a plain invariant, omit
`antecedent_signal` and the tool checks that `consequent_signal == 1` every
non-reset cycle.

### RTL Intent Manifest (optional)

Provides the dependency edges (`drivers`) used for the cone of influence and the
source locations used for citations. See `examples/toy_counter/manifest.json`.

## Commands

```bash
cx-triage triage --trace T --failure F [--manifest M] [--out-md R.md] [--out-json R.json] [--narrate]
cx-triage parse  --trace T
cx-triage demo   [--out-md R.md] [--narrate/--no-narrate]
cx-triage schema {report|failure|manifest} [--out S.json]
```

## Regenerating goldens

If you intentionally change engine output:

```bash
cx-triage demo --narrate --out-md tests/golden/toy_counter_report.md
cx-triage triage \
  --trace examples/toy_counter/counter_fail.vcd \
  --failure examples/toy_counter/failure.json \
  --manifest examples/toy_counter/manifest.json \
  --out-json tests/golden/toy_counter_report.json
```
