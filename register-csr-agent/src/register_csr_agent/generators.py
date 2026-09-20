"""Candidate SVA and directed-test generation, coverage matrix, review checklist.

All SVA is emitted in the ``sva-intent-engine`` style: a named
``assert property`` clocked/reset-guarded block, always tagged ``candidate``
(the ``status`` field of :class:`CandidateSVA` is never upgraded). Templates are
deterministic and driven only by the validated access semantics — no semantics
are invented.

The generated assertions model the standard CSR access contracts:
* RO      : value never changes on a write to its address
* RW      : readback equals last written value
* W1C     : writing 1 clears the bit; writing 0 leaves it
* W1S     : writing 1 sets the bit; writing 0 leaves it
* RC      : reading clears the field
* RESERVED: reads as 0
plus a reset-value assertion for every field.
"""

from __future__ import annotations

from .models import (
    AccessType,
    CandidateSVA,
    CoverageRow,
    DirectedTest,
    Field_,
    Register,
    RegisterMap,
    ReviewItem,
)

CLK = "clk"
RSTN = "rst_n"
# Abstract CSR bus handles used in templates (documented in README).
WR = "csr_write"  # write strobe
RD = "csr_read"  # read strobe
ADDR = "csr_addr"  # address bus
WDATA = "csr_wdata"  # write data
RDATA = "csr_rdata"  # read data


def _guard() -> str:
    return f"@(posedge {CLK}) disable iff (!{RSTN})"


def _sig(reg: Register, f: Field_ | None) -> str:
    """Abstract RTL signal handle for a field's stored value."""
    if f is None or f.name == reg.name:
        return f"csr.{reg.name}"
    return f"csr.{reg.name}.{f.name}"


def _field_slice(f: Field_) -> str:
    if f.bit_width == 1:
        return f"[{f.bit_offset}]"
    return f"[{f.msb}:{f.lsb}]"


def _reset_sva(reg: Register, f: Field_ | None) -> CandidateSVA:
    target = f if f is not None else reg
    name = f"p_{reg.name}_{getattr(f, 'name', 'reg')}_reset".lower()
    sig = _sig(reg, f)
    rv = target.reset_value
    return CandidateSVA(
        name=name,
        register=reg.name,
        field=getattr(f, "name", ""),
        check="reset_value",
        sva=(
            f"{name}: assert property (\n"
            f"  $rose({RSTN}) |-> ({sig} == 'h{rv:x})\n"
            f");"
        ),
        rationale="value at deassertion of reset must equal declared reset value",
    )


def _access_sva(reg: Register, f: Field_) -> list[CandidateSVA]:
    out: list[CandidateSVA] = []
    sig = _sig(reg, f)
    addr_hit = f"({ADDR} == 'h{reg.address:x})"
    wbit = f"{WDATA}{_field_slice(f)}"
    guard = _guard()
    base = f"p_{reg.name}_{f.name}".lower()
    acc = f.access

    if acc == AccessType.RO:
        out.append(
            CandidateSVA(
                name=f"{base}_ro_write_ignored",
                register=reg.name,
                field=f.name,
                check="illegal_write",
                sva=(
                    f"{base}_ro_write_ignored: assert property (\n"
                    f"  {guard} ({WR} && {addr_hit}) |=> ($stable({sig}))\n"
                    f");"
                ),
                rationale="RO field must not change on a bus write to its address",
            )
        )
    elif acc == AccessType.RW:
        out.append(
            CandidateSVA(
                name=f"{base}_rw_readback",
                register=reg.name,
                field=f.name,
                check="readback",
                sva=(
                    f"{base}_rw_readback: assert property (\n"
                    f"  {guard} ({WR} && {addr_hit}) |=> ({sig} == $past({wbit}))\n"
                    f");"
                ),
                rationale="RW field stores the written value and reads it back",
            )
        )
    elif acc == AccessType.W1C:
        out.append(
            CandidateSVA(
                name=f"{base}_w1c_clear",
                register=reg.name,
                field=f.name,
                check="side_effects",
                sva=(
                    f"{base}_w1c_clear: assert property (\n"
                    f"  {guard} ({WR} && {addr_hit} && {wbit}) |=> ({sig} == 'h0)\n"
                    f");"
                ),
                rationale="W1C: writing 1 clears the bit",
            )
        )
    elif acc == AccessType.W1S:
        out.append(
            CandidateSVA(
                name=f"{base}_w1s_set",
                register=reg.name,
                field=f.name,
                check="side_effects",
                sva=(
                    f"{base}_w1s_set: assert property (\n"
                    f"  {guard} ({WR} && {addr_hit} && {wbit}) |=> "
                    f"(&{sig} === 1'b1)\n"
                    f");"
                ),
                rationale="W1S: writing 1 sets the bit",
            )
        )
    elif acc == AccessType.RC:
        out.append(
            CandidateSVA(
                name=f"{base}_rc_readclear",
                register=reg.name,
                field=f.name,
                check="side_effects",
                sva=(
                    f"{base}_rc_readclear: assert property (\n"
                    f"  {guard} ({RD} && {addr_hit}) |=> ({sig} == 'h0)\n"
                    f");"
                ),
                rationale="RC: reading the field clears it",
            )
        )
    elif acc == AccessType.RESERVED:
        out.append(
            CandidateSVA(
                name=f"{base}_reserved_reads_zero",
                register=reg.name,
                field=f.name,
                check="readback",
                sva=(
                    f"{base}_reserved_reads_zero: assert property (\n"
                    f"  {guard} ({RD} && {addr_hit}) |-> ({RDATA}{_field_slice(f)} == 'h0)\n"
                    f");"
                ),
                rationale="reserved field reads as zero",
            )
        )
    return out


def _implicit_field(reg: Register) -> Field_:
    """A fieldless register is treated as one full-width field for access SVA."""
    return Field_(
        name=reg.name,
        bit_offset=0,
        bit_width=reg.width_bits,
        access=reg.access,
        reset_value=reg.reset_value,
    )


def generate_sva(rmap: RegisterMap) -> list[CandidateSVA]:
    out: list[CandidateSVA] = []
    for reg in rmap.registers:
        if reg.fields:
            for f in reg.fields:
                out.append(_reset_sva(reg, f))
                out.extend(_access_sva(reg, f))
        else:
            out.append(_reset_sva(reg, None))
            out.extend(_access_sva(reg, _implicit_field(reg)))
    return out


def generate_directed_tests(rmap: RegisterMap) -> list[DirectedTest]:
    out: list[DirectedTest] = []
    for reg in rmap.registers:
        addr = f"0x{reg.address:x}"
        out.append(
            DirectedTest(
                name=f"t_{reg.name}_reset".lower(),
                register=reg.name,
                check="reset_value",
                steps=["assert reset", "release reset", f"read {addr}"],
                expected=f"read data == 0x{reg.reset_value:x}",
            )
        )
        targets = reg.fields if reg.fields else []
        for f in targets:
            if f.access == AccessType.RW:
                out.append(
                    DirectedTest(
                        name=f"t_{reg.name}_{f.name}_rw".lower(),
                        register=reg.name,
                        check="readback",
                        steps=[
                            f"write all-ones to {reg.name}.{f.name} @{addr}",
                            f"read {addr}",
                        ],
                        expected=f"{f.name} reads back written value",
                    )
                )
            elif f.access == AccessType.RO:
                out.append(
                    DirectedTest(
                        name=f"t_{reg.name}_{f.name}_ro".lower(),
                        register=reg.name,
                        check="illegal_write",
                        steps=[
                            f"read {addr} (capture {f.name})",
                            f"write inverted value to {addr}",
                            f"read {addr}",
                        ],
                        expected=f"{f.name} unchanged (write ignored)",
                    )
                )
            elif f.access == AccessType.W1C:
                out.append(
                    DirectedTest(
                        name=f"t_{reg.name}_{f.name}_w1c".lower(),
                        register=reg.name,
                        check="side_effects",
                        steps=[
                            f"cause {f.name} to become set",
                            f"write 1 to {f.name} @{addr}",
                            f"read {addr}",
                        ],
                        expected=f"{f.name} == 0",
                    )
                )
            elif f.access == AccessType.RC:
                out.append(
                    DirectedTest(
                        name=f"t_{reg.name}_{f.name}_rc".lower(),
                        register=reg.name,
                        check="side_effects",
                        steps=[
                            f"cause {f.name} to become set",
                            f"read {addr}",
                            f"read {addr} again",
                        ],
                        expected=f"second read of {f.name} == 0",
                    )
                )
    return out


def build_coverage(
    rmap: RegisterMap, sva: list[CandidateSVA], tests: list[DirectedTest]
) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    for reg in rmap.registers:
        targets = reg.fields if reg.fields else [None]
        for f in targets:
            fname = f.name if f is not None else ""
            acc = f.access.value if f is not None else reg.access.value
            sva_here = [
                s for s in sva if s.register == reg.name and s.field == fname
            ]
            tests_here = [
                t
                for t in tests
                if t.register == reg.name
                and (fname == "" or fname in t.name)
            ]
            checks = sorted({s.check for s in sva_here})
            rows.append(
                CoverageRow(
                    register=reg.name,
                    field=fname,
                    access=acc,
                    checks_covered=checks,
                    sva_count=len(sva_here),
                    test_count=len(tests_here),
                )
            )
    return rows


def build_review_checklist(rmap: RegisterMap) -> list[ReviewItem]:
    items: list[ReviewItem] = [
        ReviewItem(
            id="RC-001",
            prompt="Confirm every RTL grounding (matched signal) is semantically correct.",
            why="Grounding is lexical; a normalized-name match can be a false positive.",
        ),
        ReviewItem(
            id="RC-002",
            prompt="Confirm candidate SVA bus handles map to the real CSR interface signals.",
            why="SVA templates use abstract handles (csr_write/csr_addr/...).",
        ),
        ReviewItem(
            id="RC-003",
            prompt="Review all ERROR discrepancies; fix the map/RTL or waive with rationale.",
            why="Errors indicate real inconsistencies (overlap, bad reset, OOB fields).",
        ),
    ]
    n = 4
    for reg in rmap.registers:
        for f in reg.fields:
            if f.side_effect:
                items.append(
                    ReviewItem(
                        id=f"RC-{n:03d}",
                        prompt=f"Verify side effect of {reg.name}.{f.name}: {f.side_effect!r}.",
                        why="Side effects cannot be inferred; require a directed test.",
                    )
                )
                n += 1
            if f.interrupt_related:
                items.append(
                    ReviewItem(
                        id=f"RC-{n:03d}",
                        prompt=f"Verify interrupt/status handshake for {reg.name}.{f.name}.",
                        why="Interrupt semantics need clear/set behavior confirmed against RTL.",
                    )
                )
                n += 1
    return items
