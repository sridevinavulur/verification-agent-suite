"""Performance Regression Agent — deterministic detection of perf regressions.

Detects and explains performance regressions across commits, configs, workload
traces, and platforms using a versioned metrics schema, controlled baseline
comparison, robust outlier rejection, and confidence/variance reporting.
"""

from .models import SCHEMA_VERSION

__version__ = "0.1.0"
__all__ = ["SCHEMA_VERSION", "__version__"]
