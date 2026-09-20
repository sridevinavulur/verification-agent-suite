# Container Strategy (design note — not implemented in v0.1)

v0.1 uses a **mock executor** and runs in-process, so no container is required. This
note records the intended strategy for when a real backend adapter is added, so the
authority and reproducibility boundaries are designed up front.

## Goals
- **Isolation:** a formal run cannot touch the host filesystem outside a mounted,
  read-only inputs dir and a writable artifacts dir.
- **Resource caps enforced by the runtime**, matching the catalog's `timeout_s` and
  `memory_cap_mb` tiers (so a policy's declared budget is actually enforced).
- **Reproducibility:** pinned base image + pinned tool version recorded in
  `RunRecord.tool_version` and the image digest recorded in provenance.

## Intended shape
- One base image per formal tool, tagged by exact tool version (e.g.
  `formal-backend:<tool>-<version>`), digest pinned.
- The execution worker would:
  1. Mount design/property inputs **read-only**.
  2. Apply `--memory` / `--cpus` limits from the selected catalog tier.
  3. Apply a wall-clock timeout equal to the config's `timeout_s`.
  4. Capture stdout/stderr + tool logs to the artifacts dir; hash them into
     `artifact_hash`.
  5. Emit a `RunRecord` JSON validated by this package's schema, then
     `ingest-result` it into the ledger.
- The interface the classifier consumes (`RawResult`) is unchanged, so swapping the
  mock for a container-backed real run touches only the executor internals.

## Safety
- No network in the run container by default.
- Inputs read-only; the tool cannot modify RTL/SVA/assumptions (see `HUMAN_GATE.md`).
- Non-zero/timeout/OOM exits map to `ERROR`/`TIMEOUT` via the existing classifier —
  never to `PASS`.

**Status:** TODO. Tracked in the README roadmap.
