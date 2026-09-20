"""Reset Intent Agent.

Deterministic, structural extraction of reset topology from a constrained
Verilog/SystemVerilog subset (or an RTL Intent Manifest), plus generation of
reviewable *candidate* reset-behavior SVA.

STRUCTURAL detection is separated from *verified* intent everywhere. All
inferred reset-domain relationships are labelled HEURISTIC until reviewed.
Reset polarity is never inferred silently: when the evidence is ambiguous the
polarity is reported as ``unknown`` with an explicit ambiguity record.
"""

__version__ = "0.1.0"
