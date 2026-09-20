"""Test the optional synchronizer-cell glossary path with a synthetic module.

A glossary cell instance sits between the two clock domains: its output net is
sampled by the destination register, so the crossing should be reported with
``synchronizer_cell_from_glossary`` evidence rather than ``no_synchronizer``.
"""

from __future__ import annotations

from cdc_rdc_triage.analyze import _ModuleAnalyzer, analyze_manifest
from cdc_rdc_triage.glossary import Glossary
from cdc_rdc_triage.manifest_models import (
    Assignment,
    ClockCandidate,
    Instance,
    Manifest,
    Module,
    PortConnection,
    Procedure,
    ProcedureKind,
    Register,
    SensitivityEntry,
    SourceLocation,
)
from cdc_rdc_triage.report_models import SyncEvidence

LOC = SourceLocation(file="g.sv", line=1, col=1, end_line=1, end_col=2)


def _ff(index: int, clk: str, lhs: str, rhs: str) -> Procedure:
    return Procedure(
        index=index,
        kind=ProcedureKind.always_ff,
        location=LOC,
        sensitivity=[SensitivityEntry(signal=clk, edge="posedge")],
        condition_signals=[],
        assignment_targets=[lhs],
        assignments=[Assignment(lhs=lhs, rhs=rhs, nonblocking=True, location=LOC)],
    )


def _module_with_glossary_cell() -> Module:
    # src_reg in clk_a; synced_net driven by a sync_2ff instance; dst_reg in
    # clk_b samples synced_net.
    return Module(
        name="top",
        location=LOC,
        clock_candidates=[
            ClockCandidate(signal="clk_a", confidence=1.0),
            ClockCandidate(signal="clk_b", confidence=1.0),
        ],
        procedures=[
            _ff(0, "clk_a", "src_reg", "d_a"),
            _ff(1, "clk_b", "dst_reg", "synced_net"),
        ],
        registers=[
            Register(name="src_reg", driven_in_procedure_index=0, location=LOC),
            Register(name="dst_reg", driven_in_procedure_index=1, location=LOC),
        ],
        instances=[
            Instance(
                module="sync_2ff",
                name="u_sync",
                location=LOC,
                connections=[
                    PortConnection(actual="src_reg", formal="d", location=LOC),
                    PortConnection(actual="synced_net", formal="q", location=LOC),
                    PortConnection(actual="clk_b", formal="clk", location=LOC),
                ],
            )
        ],
    )


def test_glossary_evidence_map() -> None:
    glossary = Glossary.model_validate(
        {
            "cells": [
                {"module": "sync_2ff", "depth": 2, "data_out_port": "q"}
            ]
        }
    )
    analyzer = _ModuleAnalyzer(_module_with_glossary_cell(), glossary)
    mapping = analyzer._glossary_evidence()
    assert mapping.get("synced_net") == 2


def test_glossary_cell_downgrades_crossing() -> None:
    # dst_reg samples synced_net (driven by the glossary cell) rather than the
    # cross-domain register directly -- so as modeled, dst_reg's only reg-source
    # is none; here we make dst_reg read src_reg directly but ALSO be the sync
    # cell output net, to exercise the glossary branch on a real crossing.
    module = _module_with_glossary_cell()
    # make dst_reg's net name match the glossary output so the branch triggers
    module.registers[1].name = "synced_net"
    module.procedures[1].assignments[0].lhs = "synced_net"
    module.procedures[1].assignments[0].rhs = "src_reg"
    module.procedures[1].assignment_targets = ["synced_net"]

    glossary = Glossary.model_validate(
        {"cells": [{"module": "sync_2ff", "depth": 2, "data_out_port": "q"}]}
    )
    manifest = Manifest(top="top", modules=[module])
    report = analyze_manifest(manifest, glossary=glossary, tool_version="test")
    crossings = report.all_crossings()
    assert len(crossings) == 1
    assert crossings[0].sync_evidence == SyncEvidence.glossary_cell
    assert crossings[0].sync_depth == 2
