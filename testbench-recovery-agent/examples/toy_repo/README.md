# Toy Counter (public example)

A tiny, synthetic verification project used as a fixture for the Testbench
Recovery Agent. It contains a counter, a testbench, a Verilator flow, an Icarus
flow, and CI. No proprietary content.

## Requirements

- [Verilator](https://verilator.org) 5.x
- [Icarus Verilog](https://steveicarus.github.io/iverilog/) (`iverilog`, `vvp`)
- GNU `make`

## Quickstart

Lint the design:

```sh
verilator --lint-only -Wall -f rtl/counter.f
```

Build and run the Verilator simulation:

```sh
make build
make run
```

Run the Icarus testbench instead:

```sh
make test
```

Clean build artifacts:

```sh
make clean
```
