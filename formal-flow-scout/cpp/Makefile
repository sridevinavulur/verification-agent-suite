# Optional C++17 graph core. Building is NOT required: the pure-Python core is
# authoritative and tests run without a compiler. Build only for large-graph
# performance, then run the CLI with `--use-cpp`.
#
#   make            # builds ./coi_core
#   make clean

CXX ?= c++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra

coi_core: coi_core.cpp
	$(CXX) $(CXXFLAGS) -o coi_core coi_core.cpp

.PHONY: clean
clean:
	rm -f coi_core
