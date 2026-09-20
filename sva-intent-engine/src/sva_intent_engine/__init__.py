"""sva-intent-engine: evidence-grounded candidate-SVA generation and review.

Deterministic core. An LLM (mock only, in this phase) may propose hypotheses;
deterministic engines ground symbols, choose clocks, and render SVA.
"""

from .models import SCHEMA_VERSION
from .rtl_intent_adapter import from_rtl_intent_manifest, load_manifest

__version__ = SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "__version__",
    "from_rtl_intent_manifest",
    "load_manifest",
]
