"""Deterministic MOCK backends for the four coordinated agents.

Each backend has a ``Protocol`` interface so a real integration can be dropped in
later. The mocks are fully deterministic (seeded, no network) so the whole
workflow is testable in CI before real integrations exist.

The mocks intentionally support "bad" tasks (ungrounded property, missing clock,
etc.) so the red-team tests can drive the supervisor's rejection paths.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Protocol, runtime_checkable

from .models import (
    CandidateProperty,
    ExecutionRequest,
    FormalResult,
    PartitionReport,
    PartitionRequest,
    ReviewState,
    RtlIngestRequest,
    RtlManifest,
    RunRecord,
    SignalInfo,
    SvaProposalRequest,
    SymbolMapping,
)


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Protocols (interfaces for future real integrations)
# ---------------------------------------------------------------------------


@runtime_checkable
class RtlIngestorBackend(Protocol):
    def ingest(self, req: RtlIngestRequest) -> RtlManifest: ...


@runtime_checkable
class SvaAgentBackend(Protocol):
    def propose(self, req: SvaProposalRequest) -> CandidateProperty: ...


@runtime_checkable
class PartitionAgentBackend(Protocol):
    def analyze(self, req: PartitionRequest, manifest: RtlManifest) -> PartitionReport: ...


@runtime_checkable
class OrchestratorBackend(Protocol):
    def execute(self, req: ExecutionRequest, repo_revision: str, manifest_hash: str) -> RunRecord:
        ...


# ---------------------------------------------------------------------------
# Mock: RTL Intent Ingestor
# ---------------------------------------------------------------------------


class MockRtlIngestor:
    """Deterministic mock producing a small req/grant manifest."""

    def ingest(self, req: RtlIngestRequest) -> RtlManifest:
        signals = [
            SignalInfo(name="clk", direction="input", width=1, source_loc="handshake.sv:3"),
            SignalInfo(name="rst_n", direction="input", width=1, source_loc="handshake.sv:4"),
            SignalInfo(name="req", direction="input", width=1, source_loc="handshake.sv:5"),
            SignalInfo(name="req_accepted", direction="internal", width=1,
                       source_loc="handshake.sv:12"),
            SignalInfo(name="grant", direction="output", width=1, source_loc="handshake.sv:6"),
        ]
        return RtlManifest(
            task_id=req.task_id,
            repo_revision=req.repo_revision,
            design_top="handshake",
            signals=signals,
            clock_candidates=["clk"],
            reset_candidates=["rst_n"],
            reset_polarity={"rst_n": "active_low"},
            unresolved_constructs=[],
            manifest_hash=_hash(req.repo_revision, "handshake", *(s.name for s in signals)),
        )


# ---------------------------------------------------------------------------
# Mock: SVA Intent Agent
# ---------------------------------------------------------------------------


class MockSvaAgent:
    """Deterministic mock. Produces a well-grounded req/grant property.

    A ``defect`` switch lets tests request deliberately unsafe proposals so the
    supervisor's rejection gates can be exercised (red-team).
    """

    def __init__(self, defect: str | None = None) -> None:
        # defect in {None, "ungrounded", "no_clock", "syntax", "ambiguous_reset"}
        self.defect = defect

    def propose(self, req: SvaProposalRequest) -> CandidateProperty:
        groundings = [
            SymbolMapping(term="req accepted", symbol="req_accepted",
                          source_loc="handshake.sv:12", confidence=0.95),
            SymbolMapping(term="grant", symbol="grant",
                          source_loc="handshake.sv:6", confidence=0.98),
        ]
        sva = ("(req_accepted |-> ##[1:3] grant) or (!rst_n)")
        clock: str | None = "clk"
        reset: str | None = "rst_n"
        polarity = "active_low"
        syntax_ok = True

        if self.defect == "ungrounded":
            groundings = [
                SymbolMapping(term="req accepted", symbol=None, confidence=0.0),
                SymbolMapping(term="grant", symbol="grant",
                              source_loc="handshake.sv:6", confidence=0.98),
            ]
        elif self.defect == "no_clock":
            clock = None
        elif self.defect == "syntax":
            sva = "(req_accepted |-> ##[1:3] grant"  # unbalanced paren
            syntax_ok = False
        elif self.defect == "ambiguous_reset":
            polarity = "unknown"

        return CandidateProperty(
            property_id=f"{req.task_id}-P1",
            task_id=req.task_id,
            requirement_text=req.requirement_text,
            sva_text=sva,
            property_kind="assert",
            clock_signal=clock,
            reset_signal=reset,
            reset_polarity=polarity,  # type: ignore[arg-type]
            groundings=groundings,
            syntax_ok=syntax_ok,
            review_state=ReviewState.UNREVIEWED,
        )


# ---------------------------------------------------------------------------
# Mock: Formal Partition Agent
# ---------------------------------------------------------------------------


class MockPartitionAgent:
    """Deterministic COI/partition mock.

    ``needs_cut_assumptions`` makes the report emit unproven cut obligations,
    which the supervisor treats as "affects assumptions" -> human gate required.
    """

    def __init__(self, needs_cut_assumptions: bool = False) -> None:
        self.needs_cut_assumptions = needs_cut_assumptions

    def analyze(self, req: PartitionRequest, manifest: RtlManifest) -> PartitionReport:
        coi = ["req", "req_accepted", "grant", "clk", "rst_n"]
        cut_assumptions: list[str] = []
        risk: list[str] = []
        if self.needs_cut_assumptions:
            cut_assumptions = ["assume req is stable until grant at partition cut 'req'"]
            risk = ["cut on 'req' introduces an unproven environment obligation"]
        return PartitionReport(
            task_id=req.task_id,
            property_id=req.property_id,
            coi_signals=coi,
            excluded_signals=[s.name for s in manifest.signals if s.name not in coi],
            partitions=["handshake_top"],
            cut_signals=["req"] if self.needs_cut_assumptions else [],
            cut_assumptions=cut_assumptions,
            soundness_risk_flags=risk,
            heuristic=True,
        )


# ---------------------------------------------------------------------------
# Mock: Formal Run Orchestrator
# ---------------------------------------------------------------------------


class MockOrchestrator:
    """Deterministic mock executor.

    Refuses to run unless the request is approved. The result is seeded by the
    config id so tests are reproducible. It NEVER maps a timeout/error to PASS.
    """

    def __init__(self, forced_result: FormalResult | None = None) -> None:
        self.forced_result = forced_result

    def execute(
        self, req: ExecutionRequest, repo_revision: str, manifest_hash: str
    ) -> RunRecord:
        if not req.approved:
            raise PermissionError(
                "MockOrchestrator refused: execution request is not approved."
            )
        # Deterministic result derived from config id unless forced by a test.
        if self.forced_result is not None:
            result = self.forced_result
        else:
            digest = int(_hash(req.config.config_id, req.property_id), 16)
            # Bias toward PASS for the nominal catalog, but keep it deterministic.
            result = [FormalResult.PASS, FormalResult.FAIL,
                      FormalResult.TIMEOUT][digest % 3]
            if req.config.config_id == "CFG-BMC-DEEP":
                result = FormalResult.PASS

        rec = RunRecord(
            task_id=req.task_id,
            property_id=req.property_id,
            config_id=req.config.config_id,
            repo_revision=repo_revision,
            manifest_hash=manifest_hash,
            command=(
                f"mock-formal --engine {req.config.engine} "
                f"--bmc-depth {req.config.bmc_depth} "
                f"--timeout {req.config.timeout_s}"
            ),
            seed=0,
            cpu_time_s=1.5,
            wall_time_s=1.6,
            peak_mem_mb=128.0,
            return_code=0 if result != FormalResult.ERROR else 1,
            result=result,
            artifact_paths=[f"artifacts/{req.property_id}/{req.config.config_id}.log"],
            rationale=(
                f"Ran approved config {req.config.config_id}; "
                f"backend classified result as {result.value}."
            ),
        )
        rec.end_time = rec.start_time + timedelta(seconds=rec.wall_time_s)
        return rec
