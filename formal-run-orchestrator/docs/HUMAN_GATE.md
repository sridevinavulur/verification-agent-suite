# Human Approval Gate (Authority Boundary)

The Formal Run Orchestrator is a **coordinator**, not an authority on correctness. The
following actions are **prohibited** for the tool and require explicit human approval
before they may happen (outside this tool):

| Action | Who may do it | Why gated |
| --- | --- | --- |
| Modify RTL | Human (design/DV owner) | Changing the DUT invalidates all prior results. |
| Modify SVA / properties | Human | Alters what is being checked. |
| Add or weaken assumptions/constraints | Human | Can create vacuous or unsound proofs. |
| Change proof scope / abstraction boundary | Human | Affects soundness of any conclusion. |
| Change resource budget beyond catalog tiers | Human | Budgets are part of the recorded experiment. |
| Declare proof / signoff | Human | The tool never claims proof or signoff. |

## What the tool *is* allowed to do
- Select among **pre-approved** configurations in the versioned catalog.
- Execute (mock) runs and record complete provenance.
- Classify results into the fixed vocabulary and report them honestly, including
  failures, timeouts, errors, and inconclusive runs (never hidden, never upgraded).
- Recommend the *next permitted configuration* from the catalog (heuristic).

## Enforcement in code
- No code path mutates any RTL/SVA/assumption input; inputs are read-only descriptors
  (`BenchmarkItem`) with placeholder SHAs.
- `RunStatus` has no "signoff"/"proven-complete" value; `PASS` means only "the recorded
  backend returned a passing result under the exact recorded configuration".
- Out-of-catalog configurations are rejected and recorded as `ERROR` /
  `INVALID_CONFIG`, never executed.

If a workflow needs any gated action, it must stop and route to a human reviewer.
