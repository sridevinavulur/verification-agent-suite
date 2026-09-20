# Discrepancy Report

ERRORS: 7  WARNINGS: 2  TOTAL: 11

## ERROR (7)
- [ACCESS_RESERVED_RESET] REG_C.RSVD: reserved field 'RSVD' has non-zero reset 0x3
    explanation: A reserved field must power up as 0 but declares a nonzero reset.
- [ADDR_OVERLAP] : register 'REG_A' [0x0-0x3] overlaps 'REG_B' starting @0x2
    explanation: Two registers claim overlapping byte ranges; decoding is ambiguous.
- [FIELD_OOB] REG_C.WIDE: field 'WIDE' bits[9:0] exceed register width 8
    explanation: A field's MSB exceeds the register width, so bits fall off the register.
- [FIELD_OVERLAP] REG_A.FA1: field 'FA1' bits[2:1] overlap another field
    explanation: Two fields claim the same bit(s); the stored value is ill-defined.
- [FIELD_OVERLAP] REG_C.RSVD: field 'RSVD' bits[7:6] overlap another field
    explanation: Two fields claim the same bit(s); the stored value is ill-defined.
- [RESET_FIELD_SUM] REG_A: register 'REG_A' reset 0x1 inconsistent with field-composed reset 0x0 (over declared bits 0xf)
    explanation: Per-field reset values do not compose to the register reset value.
- [RESET_FIELD_SUM] REG_C: register 'REG_C' reset 0x0 inconsistent with field-composed reset 0xc0 (over declared bits 0x3ff)
    explanation: Per-field reset values do not compose to the register reset value.

## WARNING (2)
- [ADDR_MISALIGN] REG_B: register 'REG_B' @0x2 is not aligned to its 4-byte size
    explanation: The base address is not a multiple of the register size.
- [IRQ_STATUS_ACCESS] IRQ_STATUS.DONE: interrupt/status field 'DONE' uses RW; expected one of W1C/RC/RO/W1S for status semantics
    explanation: A status/interrupt bit uses plain RW; software could spuriously set it.

## INFO (2)
- [FIELD_GAP] IRQ_STATUS: register 'IRQ_STATUS' has undeclared (reserved) bits: mask 0xfffffffe
    explanation: Some bits are undeclared and should be treated as reserved (read 0).
- [FIELD_GAP] REG_A: register 'REG_A' has undeclared (reserved) bits: mask 0xfffffff0
    explanation: Some bits are undeclared and should be treated as reserved (read 0).
