# Testbench Recovery Report

- tool: testbench-recovery-agent v0.1.0
- repo root: `.`
- git SHA: (not a git checkout)
- inspected files: 4

## Recommended minimal smoke test

- `make run` [EXTRACTED] phase=run _(evidence: .github/workflows/ci.yml:22)_

## Candidate commands

### build
- `make build` [EXTRACTED] phase=build _(evidence: .github/workflows/ci.yml:21)_
- `verilator --binary -j 0 -f rtl/counter.f --top-module counter -o counter_sim` [EXTRACTED] phase=build _(evidence: Makefile:17)_

### run
- `make run` [EXTRACTED] phase=run _(evidence: .github/workflows/ci.yml:22)_
- `make test` [EXTRACTED] phase=run _(evidence: .github/workflows/ci.yml:31)_
- `./build/counter_sim` [EXTRACTED] phase=run _(evidence: Makefile:20)_
- `iverilog -g2012 -o build/counter_tb tb/counter_tb.sv rtl/counter.sv` [EXTRACTED] phase=run _(evidence: Makefile:24)_
- `vvp build/counter_tb` [EXTRACTED] phase=run _(evidence: Makefile:25)_

### analyze
- `verilator --lint-only -Wall -f rtl/counter.f` [EXTRACTED] phase=analyze _(evidence: .github/workflows/ci.yml:18)_
- `make lint` [EXTRACTED] phase=analyze _(evidence: Makefile:13)_

### clean
- `make clean` [EXTRACTED] phase=clean **[destructive]** _(evidence: Makefile:27)_
- `rm -rf build` [EXTRACTED] phase=clean **[destructive]** _(evidence: Makefile:28)_

### setup
- `sudo apt-get update` [EXTRACTED] phase=setup _(evidence: .github/workflows/ci.yml:15)_
- `sudo apt-get install -y verilator iverilog` [EXTRACTED] phase=setup _(evidence: .github/workflows/ci.yml:16)_
- `sudo apt-get install -y iverilog` [EXTRACTED] phase=setup _(evidence: .github/workflows/ci.yml:29)_

### unknown
- `make all` [EXTRACTED] phase=unknown _(evidence: Makefile:11)_

## Tool / simulator requirements

- **make** (build) [EXTRACTED]
- **icarus-verilog** (simulator) [EXTRACTED]
- **verilator** (simulator) [EXTRACTED]

## Dependency inventory

- iverilog (via apt)
- verilator (via apt)

## Target -> source mapping

- **build**: (none) | filelists: rtl/counter.f
- **lint**: (none) | filelists: rtl/counter.f
- **rtl/counter.f**: rtl/counter.sv, tb/counter_tb.sv
- **test**: rtl/counter.sv, tb/counter_tb.sv

