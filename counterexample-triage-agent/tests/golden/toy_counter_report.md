# Counterexample Triage Report: `p_inc`

> Heuristic triage. Hypotheses are ranked evidence-based guesses,
> not conclusions. No RTL or assertions were modified.

## Property context

- **Property:** `p_inc`
- **Location:** `examples/toy_counter/counter.sva:18`
- **Text:** `@(posedge clk) disable iff (rst) en |=> count_advanced`
- **Clock:** `tb.clk`
- **Reset:** `tb.rst`

## Key cycles

- **Antecedent activation:** cycle 2 (time 25)
- **First divergence:** cycle 6 (time 65)

## Event timeline

| Cycle | Time | Kind | Description | Signals |
| --- | --- | --- | --- | --- |
| 0 | 5 | reset | reset active | tb.clk=1, tb.count_advanced=0, tb.en=0, tb.rst=1 |
| 1 | 15 | reset | reset active | tb.clk=1, tb.count_advanced=0, tb.en=0, tb.rst=1 |
| 2 | 25 | antecedent | antecedent 'tb.en' activated | tb.clk=1, tb.count_advanced=0, tb.en=1, tb.rst=0 |
| 3 | 35 | sample | sampled clock edge | tb.clk=1, tb.count_advanced=1, tb.en=1, tb.rst=0 |
| 5 | 55 | sample | sampled clock edge | tb.clk=1, tb.count_advanced=1, tb.en=1, tb.rst=0 |
| 6 | 65 | failure | consequent failed to hold within window; tool-reported failure of 'p_inc' | tb.clk=1, tb.count_advanced=0, tb.en=1, tb.rst=0 |
| 7 | 75 | sample | sampled clock edge | tb.clk=1, tb.count_advanced=1, tb.en=0, tb.rst=0 |

## Relevant RTL cone

_Heuristic structural cone (backward dependency reachability):_

- `tb.count`
- `tb.count_advanced`
- `tb.en`
- `tb.rst`
- `tb.stall`

## Source citations

- `examples/toy_counter/counter.sva:18` (`p_inc`) — Property whose failure is being triaged.
- `examples/toy_counter/counter.v:24` (`tb.count`) — In cone of influence (reg).
- `examples/toy_counter/counter.sva:11` (`tb.count_advanced`) — In cone of influence (wire).
- `examples/toy_counter/counter.v:19` (`tb.en`) — In cone of influence (port_in).
- `examples/toy_counter/counter.v:18` (`tb.rst`) — In cone of influence (port_in).
- `examples/toy_counter/counter.v:20` (`tb.stall`) — In cone of influence (port_in).

## Ranked root-cause hypotheses

### 1. design_bug — confidence 0.60

Logic in the cone of 'tb.count_advanced' fails to satisfy the property after 'tb.en'. Inspect the cone drivers.

Evidence:
- Antecedent 'tb.en' activated at cycle 2 (time 25).
- Consequent 'tb.count_advanced' did NOT hold within the required [1,1] window; first divergence at cycle 6 (time 65).
- Reset 'tb.rst' was inactive at the divergence cycle.
- Consequent value at divergence was a defined 0 (not x/z).
- Cone of influence: tb.count, tb.count_advanced, tb.en, tb.rst, tb.stall.

### 2. property_issue — confidence 0.30

The property (timing window, implication style, or antecedent/consequent choice) may not match design intent.

Evidence:
- The property text/timing bounds should be reviewed against the requirement to confirm [min,max] and implication style are correct.

## Unresolved questions

- (none)

## Reproduction

```
cx-triage demo
```

Artifacts:
- `examples/toy_counter/counter_fail.vcd`
- `examples/toy_counter/failure.json`
- `examples/toy_counter/manifest.json`

## LLM narrative (advisory, not evidence)

Property 'p_inc' produced a counterexample (defined at examples/toy_counter/counter.sva:18). The antecedent first activated at cycle 2. The first divergence from expected behavior is at cycle 6. The highest-ranked hypothesis is 'design_bug' (confidence 0.60), but alternatives are retained and should be ruled out before concluding a root cause. This narrative is advisory only and is derived from the deterministic evidence above; it is not itself evidence and does not establish a design bug.
