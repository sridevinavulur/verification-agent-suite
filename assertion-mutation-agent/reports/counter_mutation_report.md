# Mutation Report - `counter`

- RTL file: `examples/counter.v`
- Property files: `examples/counter.sva`
- Executor: `mock` (mock; no real simulator)
- Tool version: `0.1.0`
- RTL hash: `aba53383c2345f76`

## Score (excludes invalid + inconclusive)

- **Mutation score: 63.64%** (7/11 scored)
- Total mutants: 11
- detected=7 survived=4 invalid=0 timeout=0 error=0 inconclusive=0

## Surviving mutants by operator

- `boolean_negation`: 2 survivor(s)
- `enable_removal`: 1 survivor(s)
- `relational_flip`: 1 survivor(s)

## Surviving mutants (undetected mutations requiring investigation)

### `counter.boolean_negation.22.fec45a66` (boolean_negation)
Negate if-condition: cond -> !(cond)

```diff
@@ counter:22 @@
-             if (load) begin
+             if (!(load)) begin
```

### `counter.boolean_negation.24.829acd6b` (boolean_negation)
Negate if-condition: cond -> !(cond)

```diff
@@ counter:24 @@
-             end else if (en) begin
+             end else if (!(en)) begin
```

### `counter.enable_removal.24.63d00eda` (enable_removal)
Remove enable guard 'en' (force condition true)

```diff
@@ counter:24 @@
-             end else if (en) begin
+             end else if (1'b1) begin
```

### `counter.relational_flip.25.61871fd5` (relational_flip)
Flip relational operator '<' -> '>'

```diff
@@ counter:25 @@
-                 if (count < MAX_COUNT) begin
+                 if (count > MAX_COUNT) begin
```


> A surviving mutant is an *undetected mutation requiring investigation*, NOT proof that an assertion is wrong. Mutation scoring is a heuristic property-quality signal, not formal signoff.
