# Protocol property catalog

For each protocol, the templates below are instantiated deterministically from the
resolved roles. All properties are **candidates for human review**. `A|=>B` is
non-overlapping implication; `disable iff` is emitted only when reset polarity is
known.

Notation: `pol` = resolved reset polarity, `[lo:hi]` = supplied delay window.

## valid_ready  (roles: valid, ready, [data])
- **valid_stable** (assert if valid is a DUT output, else assume):
  `(valid && !ready) |=> (valid)` — source holds valid until accepted.
- **data_stable** (only if `data` bound): `(valid && !ready) |=> $stable(data)`.
- **handshake_cover** (cover): `valid && ready`.
- **accept_without_valid_cover** (cover / negative): `ready && !valid` — the
  illegal combination is *covered for review*, not asserted away.

Checklist: reset polarity; role directions; no combinational deadlock (not
checked structurally).

## req_grant  (roles: req, grant; optional min/max delay)
- **no_spurious_grant** (assert): `grant |-> req`.
- **grant_latency** (assert, only if `max_delay` given):
  `req |-> ##[lo:hi] grant`; depends on `no_spurious_grant`.
- **req_stable_assume** (assume, only if req is an env input):
  `(req && !grant) |=> req`. Because the guard references `grant` (a DUT output),
  this is flagged `ownership_ok=false` for review.
- **grant_cover** (cover): `req && grant`.

Checklist: single-requestor scope (grant mutual exclusion is a *separate*
property, not modeled as one); ownership of req/grant.

## fifo  (roles: push, pop; optional full, empty, count; depth)
- **no_overflow** (assert / negative, needs `full`): `!(full && push)`.
- **no_underflow** (assert / negative, needs `empty`): `!(empty && pop)`.
- **count_bound** (assert, needs `count` + `depth`): `count <= depth` — models
  MULTIPLE outstanding entries.
- **full_iff_count** / **empty_iff_count** (assert): `full == (count == depth)`,
  `empty == (count == 0)`.
- **reset_empty** (assert, needs known polarity): while reset asserted, `empty`.
- Covers: `fill_cover` (full), `drain_cover` (empty), `concurrent_cover`
  (`push && pop`).

Checklist: occupancy modeled with a real count/pointer (not a single
transaction); declared depth matches RTL; push/pop ownership.

## interrupt  (roles: irq; optional source, clear; optional latency)
Assumes **level-sensitive sticky** semantics.
- **irq_sticky** (assert, needs `clear`): `(irq && !clear) |=> irq`.
- **irq_clears** (assert, needs `clear`+`source`): `(clear && !source) |=> !irq`;
  depends on `irq_sticky`.
- **irq_raise** (assert, needs `source`+`max_delay`): `source |-> ##[lo:hi] irq`.
- **irq_reset_low** (assert, known polarity): while reset asserted, `!irq`.
- **irq_cover** (cover): `irq`.

Checklist: reset polarity; edge-vs-level sensitivity.

## credit  (roles: send, credit_return; optional credit_count; max_credits)
- **no_send_without_credit** (assert / negative, needs `credit_count`):
  `!(send && (credit_count == 0))`.
- **credit_bound** (assert, needs `credit_count`+`max_credits`):
  `credit_count <= max_credits` — MULTIPLE outstanding credits.
- Covers: `send_cover` (send), `credit_exhausted_cover` (`credit_count == 0`).

Checklist: credit_return only asserted when the receiver frees a slot
(conservation of credits); credit reset/initial value (NOT assumed).
