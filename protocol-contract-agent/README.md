# protocol-contract-agent

Generate **reviewable interface contracts** for common RTL protocols, grounded to
symbols in a canonical **RTL Intent Manifest**. For each protocol instance the tool
emits a signal-role mapping, clock/reset mapping, environmental assumptions,
design guarantees, **candidate** SVA + cover properties, negative scenarios,
property dependencies, and a review checklist.

Supported protocols (v0.1):

| Protocol | Required roles | Optional roles |
|----------|----------------|----------------|
| `valid_ready` | `valid`, `ready` | `data` |
| `req_grant`   | `req`, `grant` | — |
| `fifo`        | `push`, `pop` | `full`, `empty`, `count` |
| `interrupt`   | `irq` | `source`, `clear` |
| `credit`      | `send`, `credit_return` | `credit_count` |

## What this is (and is NOT)

This is an **evidence-grounded candidate-contract generator**. Everything it
produces is a **candidate for human review**.

- It does **not** claim any property is correct, verified, proven, or
  signoff-quality.
- It does **not** run any formal tool or simulator. Candidate SVA is rendered
  deterministically in the same *compiled-offline* style as `sva-intent-engine`;
  syntactic acceptance by a downstream compiler would **not** imply semantic
  correctness.
- It does **not** infer which signal plays which protocol role — you (or a
  reviewed upstream tool) supply the role bindings.

## Interop

- **Input (consumed):** the canonical RTL Intent Manifest schema from
  `rtl-intent-ingestor` (`schemas/manifest.schema.json`). We validate only the
  subset we consume (module → ports/nets/registers, directions, widths,
  clock/reset candidates, source locations) and *ignore* everything else, so a
  real `rtl-intent` manifest loads unchanged.
- **Output (emitted):** candidate SVA in the same style as `sva-intent-engine`
  (`p_<name>: assert property (@(posedge clk) disable iff (!rst_n) ...);`),
  always labeled *candidate*, never *verified*.

## Install

```bash
python3.13 -m venv .venv          # 3.11+ works; 3.13 used in CI
.venv/bin/pip install -e ".[dev]"
```

## Quickstart

```bash
# list supported protocols and roles
protocol-contract protocols

# generate a contract as Markdown / JSON / SVA
protocol-contract generate examples/specs/fifo.json examples/rtl_manifests/fifo.json -f markdown
protocol-contract generate examples/specs/fifo.json examples/rtl_manifests/fifo.json -f sva

# run all five bundled examples end to end
protocol-contract demo

# show property mutations (property-quality aid)
protocol-contract mutate examples/specs/req_grant.json examples/rtl_manifests/req_grant.json

# export JSON Schema for the public contracts
protocol-contract export-schemas schemas
```

A contract request is a small JSON/YAML file binding roles to manifest signals:

```json
{
  "protocol": "fifo",
  "module": "sync_fifo",
  "roles": { "push": "wr_en", "pop": "rd_en", "full": "full",
             "empty": "empty", "count": "count" },
  "clock": "clk", "reset": "rst_n", "depth": 16
}
```

## Enforced safety rules

These are implemented, not aspirational (see `EVIDENCE.md` for the test names):

1. **No silently-added assumptions.** An assumption that references a non-input
   signal is emitted with `ownership_ok=false`, a `review_reason`, and an
   `assume_on_output` warning — never silently accepted.
2. **Output signals are not treated as env inputs without review.** Ownership is
   derived from the manifest port direction; a `valid` that is a DUT output
   becomes a *guarantee* (assert), while an input `valid` becomes an *assumption*
   (assume).
3. **Every property is grounded to RTL symbols.** Each referenced symbol carries
   a stable `symbol_id` and source location resolved from the manifest; a
   role bound to a missing signal raises an error.
4. **Explicit reset behavior.** Reset polarity comes from the request or the
   manifest candidate and is *never* inferred by name. Unknown polarity **skips**
   polarity-dependent properties (with a warning) instead of guessing.
5. **Multiple outstanding transactions are not modeled as one.** FIFO occupancy
   and credit counts are bounded with real `count`/`credit` signals + an explicit
   depth/`max_credits`; without them the bound is *omitted*, not invented. The
   checklist explicitly asks the reviewer to confirm this.

## Limitations

- No formal/simulation execution; no vacuity or reachability analysis.
- No structural checks (combinational deadlock, real synchronizer presence,
  arbiter fairness, exact width matching).
- Cycle bounds (`min_delay`/`max_delay`), FIFO `depth`, and `max_credits` must be
  supplied; they are never invented.
- Interrupt templates assume **level-sensitive sticky** behavior; edge-sensitive
  interrupts must be reviewed/adjusted.
- Role bindings are user-supplied; the tool does not discover protocol instances.

See `docs/protocols.md` for per-protocol property catalogs and `THREAT_MODEL.md`
for failure modes.

## License

MIT (placeholder) — see `LICENSE`. Public, non-proprietary examples only.
