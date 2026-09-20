"""Multi-Agent Verification Supervisor.

A state-machine workflow coordinator for RTL Intent Ingestor, SVA Intent Agent,
Formal Partition Agent, and Formal Run Orchestrator. Coordinates via typed
messages and deterministic gates; never declares assertions valid, proofs
complete, or signoff achieved.
"""

from .models import (
    CandidateProperty,
    EvidencePacket,
    FormalResult,
    VerificationTask,
    WorkflowState,
)
from .supervisor import Supervisor

__all__ = [
    "Supervisor",
    "VerificationTask",
    "EvidencePacket",
    "CandidateProperty",
    "FormalResult",
    "WorkflowState",
]

__version__ = "0.1.0"
