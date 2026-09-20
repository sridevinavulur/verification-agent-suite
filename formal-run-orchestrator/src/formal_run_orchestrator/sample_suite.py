"""Public toy benchmark suite.

Twenty-four (design, property) pairs across eight correlated design families (groups):
counter, fifo, arbiter, handshake, alu, shifter, crc, stack. All data is
synthetic/public toy data -- no proprietary RTL, no real SHAs (placeholders only).
Difficulty features and the ``is_holds`` ground truth are hand-authored to exercise
every classifier branch and to differentiate policies. Multiple items share a
``group`` so the group-level holdout split is meaningfully leakage-free.
"""

from __future__ import annotations

import hashlib

from .models import (
    BenchmarkItem,
    BenchmarkSuite,
    PropertyKind,
    PropertySpec,
)


def _sha(text: str) -> str:
    """Deterministic placeholder SHA (clearly a placeholder, not a real git object)."""
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()[:12]


def _item(
    bid: str,
    design: str,
    group: str,
    prop_id: str,
    kind: PropertyKind,
    lines: int,
    regs: int,
    coi: int,
    depth: int,
    diff: float,
    holds: bool,
    desc: str = "",
) -> BenchmarkItem:
    return BenchmarkItem(
        benchmark_id=bid,
        design_name=design,
        design_sha=_sha(design),
        property=PropertySpec(property_id=prop_id, kind=kind, description=desc),
        property_sha=_sha(f"{design}:{prop_id}"),
        group=group,
        rtl_lines=lines,
        register_count=regs,
        coi_size=coi,
        max_depth_hint=depth,
        intrinsic_difficulty=diff,
        is_holds=holds,
    )


def build_sample_suite() -> BenchmarkSuite:
    items = [
        # --- counter family (small, holding + a bug) ---
        _item("cnt_no_overflow", "counter", "counter", "p_no_overflow",
              PropertyKind.ASSERT, 60, 8, 20, 8, 0.05, True,
              "count never exceeds max"),
        _item("cnt_wrap_bug", "counter_buggy", "counter", "p_wrap_correct",
              PropertyKind.ASSERT, 62, 8, 22, 6, 0.06, False,
              "wrap-around is off-by-one (counterexample expected)"),
        _item("cnt_reset_state", "counter", "counter", "p_reset_zero",
              PropertyKind.ASSERT, 60, 8, 15, 3, 0.03, True,
              "count == 0 after reset"),
        # --- fifo family (medium, holding depth property + underflow bug) ---
        _item("fifo_no_overflow", "sync_fifo", "fifo", "p_no_overflow",
              PropertyKind.ASSERT, 180, 40, 160, 40, 0.35, True,
              "wr_ptr never passes rd_ptr by depth"),
        _item("fifo_no_underflow_bug", "sync_fifo_buggy", "fifo", "p_no_underflow",
              PropertyKind.ASSERT, 182, 40, 165, 20, 0.30, False,
              "empty read not gated (counterexample expected)"),
        _item("fifo_cover_full", "sync_fifo", "fifo", "c_reaches_full",
              PropertyKind.COVER, 180, 40, 150, 32, 0.28, True,
              "cover: fifo becomes full"),
        # --- arbiter family (larger COI, deep holding property) ---
        _item("arb_mutex", "rr_arbiter", "arbiter", "p_one_hot_grant",
              PropertyKind.ASSERT, 240, 90, 320, 70, 0.55, True,
              "at most one grant asserted"),
        _item("arb_no_starve", "rr_arbiter", "arbiter", "p_eventually_grant",
              PropertyKind.ASSERT, 245, 95, 340, 110, 0.75, True,
              "round-robin: each requester eventually granted"),
        # --- handshake family (valid/ready) ---
        _item("hs_stable", "valid_ready", "handshake", "p_data_stable",
              PropertyKind.ASSERT, 90, 16, 45, 5, 0.12, True,
              "data stable while valid && !ready"),
        _item("hs_no_drop_bug", "valid_ready_buggy", "handshake", "p_no_drop",
              PropertyKind.ASSERT, 92, 16, 48, 4, 0.10, False,
              "valid dropped before ready (counterexample expected)"),
        # --- alu family (hard, forces deep/unbounded engines) ---
        _item("alu_add_comm", "alu", "alu", "p_add_commutes",
              PropertyKind.ASSERT, 300, 64, 480, 150, 0.90, True,
              "a+b == b+a for all inputs (hard, likely deep/unbounded)"),
        _item("alu_shift_bug", "alu_buggy", "alu", "p_shift_correct",
              PropertyKind.ASSERT, 305, 64, 470, 18, 0.60, False,
              "barrel shifter mask bug (shallow counterexample)"),
        # --- shifter family ---
        _item("shift_rot_inv", "barrel_shifter", "shifter", "p_rotate_inverse",
              PropertyKind.ASSERT, 120, 24, 90, 12, 0.20, True,
              "rotate-left then rotate-right is identity"),
        _item("shift_sat_bug", "barrel_shifter_buggy", "shifter", "p_no_sign_leak",
              PropertyKind.ASSERT, 122, 24, 95, 7, 0.18, False,
              "arithmetic shift sign leak (counterexample expected)"),
        _item("shift_cover_max", "barrel_shifter", "shifter", "c_max_shift",
              PropertyKind.COVER, 120, 24, 88, 16, 0.22, True,
              "cover: maximum shift amount reached"),
        # --- crc family (deep, holding) ---
        _item("crc_reset", "crc32", "crc", "p_reset_seed",
              PropertyKind.ASSERT, 160, 32, 130, 4, 0.15, True,
              "crc register loads seed on reset"),
        _item("crc_stable", "crc32", "crc", "p_no_update_when_idle",
              PropertyKind.ASSERT, 162, 32, 135, 25, 0.45, True,
              "crc holds value while enable deasserted"),
        _item("crc_poly_bug", "crc32_buggy", "crc", "p_poly_correct",
              PropertyKind.ASSERT, 165, 32, 140, 22, 0.50, False,
              "wrong polynomial tap (counterexample expected)"),
        # --- stack family ---
        _item("stack_no_overflow", "lifo_stack", "stack", "p_no_overflow",
              PropertyKind.ASSERT, 140, 36, 120, 34, 0.30, True,
              "stack pointer never exceeds depth"),
        _item("stack_no_underflow_bug", "lifo_stack_buggy", "stack", "p_no_underflow",
              PropertyKind.ASSERT, 142, 36, 122, 16, 0.28, False,
              "pop when empty not gated (counterexample expected)"),
        _item("stack_lifo_order", "lifo_stack", "stack", "p_lifo_order",
              PropertyKind.ASSERT, 145, 40, 150, 60, 0.55, True,
              "last pushed value is first popped"),
        _item("stack_cover_full", "lifo_stack", "stack", "c_reaches_full",
              PropertyKind.COVER, 140, 36, 118, 30, 0.26, True,
              "cover: stack becomes full"),
    ]
    return BenchmarkSuite(
        suite_id="public-toy-v1",
        description=(
            "Public synthetic toy benchmark suite for the Formal Run Orchestrator. "
            "No proprietary RTL; SHAs are placeholders."
        ),
        items=items,
    )
