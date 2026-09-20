# Toy verification repo Makefile (public, synthetic - no proprietary content).
# Demonstrates a typical Verilator-based lint/build/run flow plus an Icarus path.

TOP      := counter
FILELIST := rtl/counter.f
BUILD    := build
SIM      := verilator

.PHONY: all lint build run test clean

all: build

lint:
	verilator --lint-only -Wall -f $(FILELIST)

build: $(FILELIST)
	verilator --binary -j 0 -f $(FILELIST) --top-module $(TOP) -o $(TOP)_sim

run: build
	./$(BUILD)/$(TOP)_sim

# Alternate simulator path using Icarus Verilog.
test:
	iverilog -g2012 -o $(BUILD)/$(TOP)_tb tb/counter_tb.sv rtl/counter.sv
	vvp $(BUILD)/$(TOP)_tb

clean:
	rm -rf $(BUILD)
