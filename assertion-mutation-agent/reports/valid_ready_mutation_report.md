# Mutation Report - `valid_ready`

- RTL file: `examples/valid_ready.v`
- Property files: `examples/valid_ready.sva`
- Executor: `mock` (mock; no real simulator)
- Tool version: `0.1.0`
- RTL hash: `049f8e620465bed7`

## Score (excludes invalid + inconclusive)

- **Mutation score: 70.00%** (7/10 scored)
- Total mutants: 10
- detected=7 survived=3 invalid=0 timeout=0 error=0 inconclusive=0

## Surviving mutants by operator

- `boolean_negation`: 1 survivor(s)
- `reset_value_change`: 1 survivor(s)
- `width_truncation`: 1 survivor(s)

## Surviving mutants (undetected mutations requiring investigation)

### `valid_ready.reset_value_change.19.0989f878` (reset_value_change)
Change reset/assign value '8'h00' -> '8'h01'

```diff
@@ valid_ready:19 @@
-             out_data  <= 8'h00;
+             out_data  <= 8'h01;
```

### `valid_ready.boolean_negation.21.75a06936` (boolean_negation)
Negate if-condition: cond -> !(cond)

```diff
@@ valid_ready:21 @@
-             if (accept) begin
+             if (!(accept)) begin
```

### `valid_ready.width_truncation.23.bfb8ef7f` (width_truncation)
Truncate width of RHS 'in_data' -> 'in_data[0]'

```diff
@@ valid_ready:23 @@
-                 out_data  <= in_data;
+                 out_data  <= in_data[0];
```


> A surviving mutant is an *undetected mutation requiring investigation*, NOT proof that an assertion is wrong. Mutation scoring is a heuristic property-quality signal, not formal signoff.
