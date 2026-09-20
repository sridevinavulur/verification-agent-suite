"""Deterministic CSR checks.

Each ``check_*`` function returns a list of :class:`Discrepancy`. None of them
ever emits a PASS — a clean run simply returns an empty list. The checks are the
authority: they operate only on validated :class:`RegisterMap` data and never
call an LLM.

Check families (mirrors the spec):
* address uniqueness & alignment          -> ADDR_OVERLAP, ADDR_DUP, ADDR_MISALIGN
* reset-value consistency                 -> RESET_FIELD_SUM, RESET_RTL_MISMATCH
* access-type semantics                    -> ACCESS_RESERVED_RESET, ACCESS_CONFLICT
* field width / bit-range consistency      -> FIELD_OVERLAP, FIELD_OOB, FIELD_GAP(info)
* illegal-write behavior                   -> (covered by access semantics + SVA)
* readback behavior                        -> (covered by access semantics + SVA)
* side effects                             -> SIDE_EFFECT_UNREVIEWED (info)
* interrupt/status interaction             -> IRQ_STATUS_ACCESS
* security/privilege access                -> PRIV_ESCALATION (info/warn)
* RTL grounding consistency                -> RTL_WIDTH_MISMATCH, RTL_RESET_MISMATCH,
                                             RTL_ACCESS_MISMATCH, RTL_UNMAPPED
"""

from __future__ import annotations

from .models import (
    AccessType,
    Discrepancy,
    GroundingReport,
    Privilege,
    Register,
    RegisterMap,
    RtlSymbolTable,
    Severity,
)


def _err(code: str, msg: str, *, reg: str = "", field: str = "", detail: str = "") -> Discrepancy:
    return Discrepancy(
        code=code, severity=Severity.ERROR, register=reg, field=field, message=msg, detail=detail
    )


def _warn(code: str, msg: str, *, reg: str = "", field: str = "", detail: str = "") -> Discrepancy:
    return Discrepancy(
        code=code, severity=Severity.WARNING, register=reg, field=field, message=msg, detail=detail
    )


def _info(code: str, msg: str, *, reg: str = "", field: str = "", detail: str = "") -> Discrepancy:
    return Discrepancy(
        code=code, severity=Severity.INFO, register=reg, field=field, message=msg, detail=detail
    )


def check_address_uniqueness_and_alignment(rmap: RegisterMap) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    unit = rmap.address_unit_bytes
    # sort by address; detect duplicates and byte-range overlaps
    regs = sorted(rmap.registers, key=lambda r: r.address)
    for reg in regs:
        addr_bytes = reg.address * unit
        # alignment: a register should sit on a boundary of its own byte size
        size = reg.byte_size
        if size > 0 and addr_bytes % size != 0:
            out.append(
                _warn(
                    "ADDR_MISALIGN",
                    f"register {reg.name!r} @0x{addr_bytes:x} is not aligned to its "
                    f"{size}-byte size",
                    reg=reg.name,
                )
            )
    # duplicate exact addresses
    by_addr: dict[int, list[str]] = {}
    for reg in rmap.registers:
        by_addr.setdefault(reg.address, []).append(reg.name)
    for addr, names in by_addr.items():
        if len(names) > 1:
            out.append(
                _err(
                    "ADDR_DUP",
                    f"address 0x{addr * unit:x} assigned to multiple registers: "
                    f"{', '.join(names)}",
                    detail=f"unit={unit} byte(s)/addr",
                )
            )
    # byte-range overlaps between distinct addresses
    for i in range(len(regs) - 1):
        a = regs[i]
        b = regs[i + 1]
        a_start = a.address * unit
        a_end = a_start + a.byte_size - 1
        b_start = b.address * unit
        if a.address != b.address and b_start <= a_end:
            out.append(
                _err(
                    "ADDR_OVERLAP",
                    f"register {a.name!r} [0x{a_start:x}-0x{a_end:x}] overlaps "
                    f"{b.name!r} starting @0x{b_start:x}",
                )
            )
    return out


def check_field_bit_ranges(rmap: RegisterMap) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    for reg in rmap.registers:
        occupied = 0
        for f in reg.fields:
            if f.msb >= reg.width_bits:
                out.append(
                    _err(
                        "FIELD_OOB",
                        f"field {f.name!r} bits[{f.msb}:{f.lsb}] exceed register width "
                        f"{reg.width_bits}",
                        reg=reg.name,
                        field=f.name,
                    )
                )
            if occupied & f.mask:
                out.append(
                    _err(
                        "FIELD_OVERLAP",
                        f"field {f.name!r} bits[{f.msb}:{f.lsb}] overlap another field",
                        reg=reg.name,
                        field=f.name,
                    )
                )
            occupied |= f.mask
        # gaps: informational only (reserved bits are legal)
        if reg.fields:
            full = (1 << reg.width_bits) - 1
            gap = full & ~occupied
            if gap:
                out.append(
                    _info(
                        "FIELD_GAP",
                        f"register {reg.name!r} has undeclared (reserved) bits: "
                        f"mask 0x{gap:x}",
                        reg=reg.name,
                    )
                )
    return out


def check_reset_value_consistency(rmap: RegisterMap) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    for reg in rmap.registers:
        if reg.reset_value >> reg.width_bits:
            out.append(
                _err(
                    "RESET_OOB",
                    f"register {reg.name!r} reset 0x{reg.reset_value:x} does not fit in "
                    f"{reg.width_bits} bits",
                    reg=reg.name,
                )
            )
        if not reg.fields:
            continue
        # composed reset from fields must equal register reset (over declared bits)
        composed = 0
        declared_mask = 0
        for f in reg.fields:
            composed |= (f.reset_value << f.bit_offset) & f.mask
            declared_mask |= f.mask
        reg_over_declared = reg.reset_value & declared_mask
        if composed != reg_over_declared:
            out.append(
                _err(
                    "RESET_FIELD_SUM",
                    f"register {reg.name!r} reset 0x{reg.reset_value:x} inconsistent with "
                    f"field-composed reset 0x{composed:x} (over declared bits "
                    f"0x{declared_mask:x})",
                    reg=reg.name,
                    detail=f"reg_over_declared=0x{reg_over_declared:x}",
                )
            )
    return out


def check_access_semantics(rmap: RegisterMap) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    for reg in rmap.registers:
        targets = reg.fields if reg.fields else [reg]
        for t in targets:
            name = getattr(t, "name", reg.name)
            fld = name if reg.fields else ""
            acc = t.access
            # RESERVED must reset to 0
            if acc == AccessType.RESERVED and t.reset_value != 0:
                out.append(
                    _err(
                        "ACCESS_RESERVED_RESET",
                        f"reserved field {name!r} has non-zero reset 0x{t.reset_value:x}",
                        reg=reg.name,
                        field=fld,
                    )
                )
            # RO with non-zero reset is legal (reflects HW state) -> info if reset==0? no.
            # W1C/W1S/RC status bits: nothing to add here beyond SVA/tests.
    # register access vs field access coherence
    for reg in rmap.registers:
        if not reg.fields:
            continue
        field_acc = {f.access for f in reg.fields}
        # if every field is RO but register declared RW (or vice versa) -> conflict warn
        if reg.access == AccessType.RO and any(
            f.access in {AccessType.RW, AccessType.WO, AccessType.W1C, AccessType.W1S}
            for f in reg.fields
        ):
            out.append(
                _warn(
                    "ACCESS_CONFLICT",
                    f"register {reg.name!r} declared RO but contains writable fields "
                    f"{sorted(a.value for a in field_acc)}",
                    reg=reg.name,
                )
            )
    return out


def check_interrupt_status(rmap: RegisterMap) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    for reg in rmap.registers:
        for f in reg.fields:
            if not f.interrupt_related:
                continue
            # interrupt/status fields should use clear-on-write / read-clear semantics,
            # not plain RW (plain RW lets SW spuriously set status).
            if f.access not in {
                AccessType.W1C,
                AccessType.RC,
                AccessType.RO,
                AccessType.W1S,
            }:
                out.append(
                    _warn(
                        "IRQ_STATUS_ACCESS",
                        f"interrupt/status field {f.name!r} uses {f.access.value}; "
                        f"expected one of W1C/RC/RO/W1S for status semantics",
                        reg=reg.name,
                        field=f.name,
                    )
                )
    return out


def check_side_effects(rmap: RegisterMap) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    for reg in rmap.registers:
        for f in reg.fields:
            if f.side_effect:
                out.append(
                    _info(
                        "SIDE_EFFECT_UNREVIEWED",
                        f"field {f.name!r} declares side effect {f.side_effect!r}; "
                        f"requires directed test + human review",
                        reg=reg.name,
                        field=f.name,
                    )
                )
    return out


def check_privilege(rmap: RegisterMap) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    for reg in rmap.registers:
        for f in reg.fields:
            if f.privilege in {Privilege.SECURE, Privilege.MACHINE, Privilege.SUPERVISOR}:
                out.append(
                    _info(
                        "PRIV_ACCESS_DECLARED",
                        f"field {f.name!r} restricted to {f.privilege.value}; verify "
                        f"lower-privilege access is denied",
                        reg=reg.name,
                        field=f.name,
                    )
                )
    return out


def check_rtl_grounding(
    rmap: RegisterMap, rtl: RtlSymbolTable, grounding: GroundingReport
) -> list[Discrepancy]:
    """Cross-check manifest registers against matched RTL symbols."""
    out: list[Discrepancy] = []
    if rtl is None or not rtl.symbols:
        return out
    by_name = rtl.by_name()
    matched = {g.manifest_name: g for g in grounding.results if g.matched}
    reg_by_name: dict[str, Register] = {r.name: r for r in rmap.registers}
    for name, g in matched.items():
        reg = reg_by_name.get(name)
        sym = by_name.get(g.rtl_symbol or "")
        if reg is None or sym is None:
            continue
        if sym.width_bits is not None and sym.width_bits != reg.width_bits:
            out.append(
                _err(
                    "RTL_WIDTH_MISMATCH",
                    f"register {name!r} width {reg.width_bits} != RTL symbol "
                    f"{sym.name!r} width {sym.width_bits}",
                    reg=name,
                )
            )
        if sym.reset_value is not None and sym.reset_value != reg.reset_value:
            out.append(
                _err(
                    "RTL_RESET_MISMATCH",
                    f"register {name!r} reset 0x{reg.reset_value:x} != RTL symbol reset "
                    f"0x{sym.reset_value:x}",
                    reg=name,
                )
            )
        if sym.access is not None and sym.access != reg.access:
            out.append(
                _warn(
                    "RTL_ACCESS_MISMATCH",
                    f"register {name!r} access {reg.access.value} != RTL symbol access "
                    f"{sym.access.value}",
                    reg=name,
                )
            )
    for name in grounding.unmatched_manifest:
        out.append(
            _warn(
                "RTL_UNMAPPED",
                f"register/field {name!r} could not be mapped to any RTL symbol",
                reg=name,
            )
        )
    return out


_MAP_CHECKS = (
    check_address_uniqueness_and_alignment,
    check_field_bit_ranges,
    check_reset_value_consistency,
    check_access_semantics,
    check_interrupt_status,
    check_side_effects,
    check_privilege,
)


def run_all_checks(
    rmap: RegisterMap,
    rtl: RtlSymbolTable | None = None,
    grounding: GroundingReport | None = None,
) -> list[Discrepancy]:
    out: list[Discrepancy] = []
    for fn in _MAP_CHECKS:
        out.extend(fn(rmap))
    if rtl is not None and grounding is not None:
        out.extend(check_rtl_grounding(rmap, rtl, grounding))
    # stable ordering: ERROR first, then by code/register/field
    sev_rank = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    out.sort(key=lambda d: (sev_rank[d.severity], d.code, d.register, d.field, d.message))
    return out
