# register-csr-agent

Deterministic **Register / CSR verification package builder** for public RTL and
register specifications. It ingests a register map (JSON, YAML, CSV, or Markdown
table) plus RTL symbols, and produces a reviewable CSR verification package:

- **normalized register manifest**
- **RTL grounding report** (manifest names mapped onto RTL symbols)
- **candidate SVA** and **directed-test cases**
- **coverage matrix**
- **discrepancy report** (real defects: overlaps, bad resets, OOB fields, ...)
- **human-review checklist**

Implements spec section 6.5 of the verification agent prompt pack, following the
shared `BUILD_STANDARD.md`.

## What is real here (not a skeleton)

- **Four working parsers** (`parsers.py`): JSON, YAML, CSV, and Markdown pipe
  tables all normalize to one `RegisterMap`. Hex (`0x..`, `8'hFF`, `FFh`),
  decimal, and bit-range notations (`7:0`, `[7:0]`, single bit) are handled.
  Unknown access tokens are **rejected**, never guessed.
- **Nine deterministic check families** (`checks.py`) that actually catch
  defects on the bundled `examples/register_maps/buggy_block.json`:
  `ADDR_OVERLAP`, `ADDR_DUP`, `ADDR_MISALIGN`, `FIELD_OOB`, `FIELD_OVERLAP`,
  `FIELD_GAP`, `RESET_OOB`, `RESET_FIELD_SUM`, `ACCESS_RESERVED_RESET`,
  `ACCESS_CONFLICT`, `IRQ_STATUS_ACCESS`, `SIDE_EFFECT_UNREVIEWED`,
  `PRIV_ACCESS_DECLARED`, plus RTL cross-checks (`RTL_WIDTH_MISMATCH`,
  `RTL_RESET_MISMATCH`, `RTL_ACCESS_MISMATCH`, `RTL_UNMAPPED`).
- **Candidate SVA templates** (`generators.py`) per access type: RO write-ignore,
  RW readback, W1C clear, W1S set, RC read-clear, reserved-reads-zero, plus a
  reset-value assertion per field. All emitted in the `sva-intent-engine` style
  and always tagged `candidate`.
- **INTEROP**: RTL symbols can be a simple JSON export *or* the canonical
  **RTL Intent Manifest** from `rtl-intent-ingestor`
  (`schemas/manifest.schema.json`). Only its deterministic facts (module
  `registers`, `ports`, `nets`) are consumed.

## Install

```bash
python3 -m venv .venv           # python3.13 works; requires >=3.11
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# End-to-end on the bundled examples
register-csr demo

# Full package into ./csr_package/ (clean map + matching RTL)
register-csr package examples/register_maps/timer_block.yaml \
                     examples/rtl_symbols/timer_block.json --out csr_package

# Run checks on a deliberately buggy map (exits 1, prints 7 errors)
register-csr check examples/register_maps/buggy_block.json

# Normalize any supported format to the canonical manifest JSON
register-csr normalize examples/register_maps/gpio_block.csv
register-csr normalize examples/register_maps/uart_block.md

# Ground against an RTL intent manifest (INTEROP path)
register-csr ground examples/register_maps/timer_block.json \
                    examples/rtl_symbols/timer_block.intent.json
```

## CLI commands

| command | purpose |
|---|---|
| `normalize` | parse a map (json/yaml/csv/md) -> normalized manifest JSON |
| `ground` | map manifest onto RTL symbols -> grounding report |
| `check` | run deterministic checks (exit 1 on any ERROR) |
| `generate` | render candidate SVA to stdout |
| `package` | full run -> package.json + rendered artifacts on disk |
| `demo` | run bundled examples end to end |
| `export-schema` | write JSON Schema for the Pydantic contracts |

## SVA bus-handle convention

Candidate SVA uses **abstract** CSR-interface handles that you must bind to your
real interface before use:

`csr_write`, `csr_read`, `csr_addr`, `csr_wdata`, `csr_rdata`, and a stored-value
handle `csr.<REG>.<FIELD>`. Clock/reset are `clk` / `rst_n`.

## Authority boundary (safety)

- The **deterministic layer** (parsers + checks) is authoritative. It maps
  access tokens onto a **closed** `AccessType` enum and validates every finding.
- The **LLM adapter** (`llm_adapter.py`) is a deterministic offline mock that can
  *only attach an `explanation` string* to an existing discrepancy. It cannot
  create discrepancies, change codes/severities, invent access semantics, or
  invent signal mappings. Tests enforce this (`test_llm_cannot_change_*`).
- Grounding is purely lexical (exact or normalized-name). It never guesses a
  mapping from width/reset similarity and reports unmatched names explicitly.

## Non-claims (explicit)

- Candidate SVA is **candidate**, never *proven* or *verified*. This tool runs no
  formal engine or simulator.
- A clean discrepancy report means "no defect found by these checks" — **not** a
  correctness proof of the register block.
- Grounding matches are lexical hypotheses requiring human confirmation.

## Limitations / roadmap (v0.1 scope)

- Field-level grounding inherits register grounding (per-field RTL symbol
  matching is future work).
- No IP-XACT XML parser yet (JSON/YAML/CSV/Markdown only).
- SVA handles are abstract; no automatic bind-file generation.
- Alignment check assumes power-of-two-ish sizing via byte-size boundary; exotic
  addressing schemes should be reviewed manually.

## Layout

```
src/register_csr_agent/  models, parsers, rtl_symbols, grounding, checks,
                         generators, llm_adapter, pipeline, renderer, cli
examples/                register_maps/ rtl_symbols/ golden/
schemas/                 exported JSON Schema for the Pydantic contracts
tests/                   pytest suite (parsers, checks, grounding, golden, CLI)
```

## License

MIT (placeholder). Public, non-proprietary example content only.
