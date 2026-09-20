"""Constraint Hygiene Agent.

Static, deterministic hygiene review of SVA assumptions/assertions/covers
against an RTL Intent Manifest and formal configuration.

Non-claim: this package performs STATIC structural analysis only. It never
concludes that a proof is valid, that a constraint set is consistent, or that
any result is non-vacuous. All findings are static suspicions requiring human
review; no assumption may be changed without human approval.
"""

__version__ = "0.1.0"
