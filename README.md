# verification-agent-suite

A suite of **bounded, evidence-grounded, LLM-assisted verification agents** for RTL and
formal design verification. Each tool is an independent, installable Python package with a
typed CLI, deterministic core logic, a mock-by-default LLM boundary, reproducible provenance,
tests, and CI.

The design philosophy is **deterministic-first**: an LLM may *propose* hypotheses, mappings,
candidate assertions, or configurations, but deterministic tools validate syntax, symbols,
constraints, and results. No tool modifies RTL, assumptions, proof scope, budgets, or signoff
conclusions without a documented human-approval gate. A candidate assertion is never called
"verified" merely because it compiles; a TIMEOUT / ERROR / INCONCLUSIVE result is never a PASS.

> Public, non-proprietary content only. See [`BUILD_STANDARD.md`](BUILD_STANDARD.md) for the
> shared engineering, safety, and evidence rules every package follows.

## Layout

This is a monorepo of independent packages — install whichever you need with
`pip install -e <dir>` (Python 3.11+).

### Core pipeline tools
| Package | What it does |
|---|---|
| [`rtl-intent-ingestor`](rtl-intent-ingestor/) | Constrained-Verilog parser → canonical RTL Intent Manifest (the interop hub every other tool consumes) |
| [`sva-intent-engine`](sva-intent-engine/) | Natural-language requirement → grounded candidate SystemVerilog Assertions |
| [`assertion-review-agent`](assertion-review-agent/) | Static SVA defect + vacuity-risk review |
| [`assertion-mutation-agent`](assertion-mutation-agent/) | RTL mutation → property-quality (mutation) score |
| [`formal-flow-scout`](formal-flow-scout/) | Cone-of-influence + SCC + heuristic proof partitioning |
| [`formal-run-orchestrator`](formal-run-orchestrator/) | Reproducible formal-run planner, SQLite ledger, mock executor, solver policy |
| [`counterexample-triage-agent`](counterexample-triage-agent/) | VCD/trace → ranked, evidence-linked root-cause hypotheses |
| [`coverage-closure-agent`](coverage-closure-agent/) | Coverage-hole triage → ranked next actions |
| [`multi-agent-verification-supervisor`](multi-agent-verification-supervisor/) | State-machine workflow coordinating the agents, with approval gates |

### Domain agents
| Package | What it does |
|---|---|
| [`verification-plan-agent`](verification-plan-agent/) | Spec → risk-ranked verification plan + traceability matrix |
| [`protocol-contract-agent`](protocol-contract-agent/) | Interface contracts + candidate SVA for valid/ready, req/grant, FIFO, interrupt, credit |
| [`register-csr-agent`](register-csr-agent/) | Register maps (JSON/YAML/CSV/MD) → CSR verification package |
| [`reset-intent-agent`](reset-intent-agent/) | Reset topology, polarity voting, reset-domain-crossing checks |
| [`cdc-rdc-triage-agent`](cdc-rdc-triage-agent/) | Structural clock/reset-domain-crossing triage (not signoff) |
| [`equivalence-triage-agent`](equivalence-triage-agent/) | Equivalence-log mismatch localization |
| [`constraint-hygiene-agent`](constraint-hygiene-agent/) | Assumption ownership + contradiction / overconstraint detection |
| [`security-property-agent`](security-property-agent/) | Security requirements → reviewable candidate verification artifacts |

### Intelligence & tooling
| Package | What it does |
|---|---|
| [`formal-regression-intelligence-agent`](formal-regression-intelligence-agent/) | Flaky/slow/duplicate clustering + regression alerts over run ledgers |
| [`performance-regression-agent`](performance-regression-agent/) | Robust-statistics performance-regression detection |
| [`testbench-recovery-agent`](testbench-recovery-agent/) | Statically recover build/run commands from a repo, with evidence |
| [`verification-knowledge-graph`](verification-knowledge-graph/) | SQLite graph over requirements/properties/tests/coverage/runs + queries |
| [`verification-agent-factory`](verification-agent-factory/) | Generator: manifest schema + `init-agent` scaffolder for new agents |
| [`verification-report-kit`](verification-report-kit/) | Shared, dependency-free HTML/JSON report library any tool can feed |

### Reference
| Package | What it does |
|---|---|
| [`spec-to-cov-agent`](spec-to-cov-agent/) | Prior end-to-end 16-stage spec→coverage-closure pipeline (formerly `veri-forge`), kept as reference. Its deterministic building blocks (coverage parsing, sim runner, HTML dashboard) are reused by the bounded tools above; its LLM-generates-RTL and auto-closure stages are intentionally not adopted there. Sanitized of proprietary content. |

## Interoperability

`rtl-intent-ingestor` produces the canonical **RTL Intent Manifest**
(`rtl-intent-ingestor/schemas/manifest.schema.json`); the consuming tools ingest it directly.
`formal-run-orchestrator` produces the canonical **run ledger**, which
`formal-regression-intelligence-agent` consumes. Candidate SVA is emitted in a consistent
`sva-intent-engine` style (always tagged *candidate*, never *verified*).

## Quick start

```bash
cd rtl-intent-ingestor
python3.11 -m venv .venv && . .venv/bin/activate   # any Python >= 3.11
pip install -e ".[dev]"
pytest
rtl-intent ingest examples/counter.sv
```

## Getting help / conventions

Every package ships `README.md`, `ARCHITECTURE.md`, `THREAT_MODEL.md`, and `EVIDENCE.md`
(claims tied to code, tests, and reproduce commands). All LLM usage defaults to a deterministic
mock adapter, so tests and CI run offline with no API keys.

## Non-claims

These are research-grade prototypes and triage aids. They do **not** perform formal signoff,
do **not** prove designs correct or equivalent, and do **not** replace commercial CDC/RDC,
LEC, or formal tools. Heuristic results are labeled as heuristic. Human review is required
before acting on any output.
