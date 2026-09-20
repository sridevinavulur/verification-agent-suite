# Review-Quality Scoring Rubric

The score answers **"how clean is this SVA file per the deterministic
reviewer?"** It is a *review-quality signal*, not a correctness proof and not a
formal result.

## Formula

```
penalty      = 10*ERRORs + 4*WARNINGs + 1*INFO
max_penalty  = property_count * 20   (min 20)
score        = round(100 * (1 - min(penalty/max_penalty, 1)), 1)   in [0, 100]
```

Weights (`src/assertion_review/scoring.py`):

| Severity | Weight | Rationale |
| --- | --- | --- |
| ERROR   | 10 | Almost certainly wrong; would produce a misleading formal result. |
| WARNING |  4 | Likely defect or strong smell; needs human review. |
| INFO    |  1 | Advisory / style / traceability. |

`max_penalty` scales with the number of properties so a large file is not
unfairly capped, and a single-property file still has a 20-point budget.

## Grade bands

| Score | Grade | Interpretation |
| --- | --- | --- |
| 90–100 | A | Clean; ready for human review / formal run. |
| 75–89  | B | Minor advisories. |
| 60–74  | C | Several smells; review before running. |
| 40–59  | D | Multiple likely defects. |
| 0–39   | F | Serious issues (errors present); do not run as-is. |

## What the score does NOT mean

* It does **not** mean the assertions are semantically correct.
* It does **not** account for vacuity soundly (see `VACUITY_RISK`, heuristic).
* A grade A file can still be functionally wrong; static review is a filter, not
  a verdict.

## Corpus calibration (checked-in golden fixtures)

| File | ERR / WARN / INFO | Score | Grade |
| --- | --- | --- | --- |
| `good/handshake_good.sv` | 0 / 0 / 2 | 96.7 | A |
| `good/fifo_good.sv`      | 0 / 0 / 0 | 100.0 | A |
| `bad/handshake_bad.sv`   | 5 / 3 / 13 | ~37.5 | F |
| `bad/fifo_bad.sv`        | 4 / 2 / 10 | 42.0 | D |

Regenerate after intended changes: `python scripts/regen_golden.py`.
