"""Protocol Contract Agent.

Generate reviewable interface contracts (signal-role mapping, assumptions,
guarantees, candidate SVA + cover properties, negative scenarios, property
dependencies, and a review checklist) for common RTL handshake / flow-control
protocols, grounded to symbols in a canonical RTL Intent Manifest.

Everything produced is a *candidate* contract for human review. Nothing here is
"verified", "proven", or "signoff-quality". Candidate SVA is emitted in the same
compiled-offline style as sva-intent-engine; it is not run against any tool here.
"""

__version__ = "0.1.0"
