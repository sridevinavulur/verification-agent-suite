# Supported property forms and phrase shapes

## Property forms (renderer)

| Form | Rendered shape | Notes |
| --- | --- | --- |
| `invariant` | `@(posedge clk)[ disable iff ...] cond` | condition always holds |
| `implication` | `(ante) \|-> (cons)` | overlapping |
| `bounded_response` | `(ante) \|-> ##[N:M] (cons)` | requires explicit N,M |
| `next_cycle` | `(ante) \|=> (cons)` | non-overlapping |
| `no_overflow` | `(guard) \|=> (cons)` | e.g. `full \|=> !overflow` |
| `no_underflow` | `(guard) \|=> (cons)` | e.g. `empty \|=> !underflow` |
| `one_hot` | `$onehot(vec)` | mutual exclusion |
| `stable_while_stalled` | `(stall) \|=> $stable(data)` | |
| `reset_state` | `(reset_active) \|-> (cons)` | polarity must be known |
| `eventually_within_bound` | `[(ante) \|->] ##[lo:hi] (cons)` | cover directive |

`|->` (overlapping) vs `|=>` (non-overlapping) is chosen from timing structure:
next-cycle and no-overflow/underflow use `|=>`; plain implication and bounded
response use `|->`.

## Phrase shapes the deterministic normalizer accepts

The natural-language front end is deliberately narrow (grounded signals only):

- `<sig> is asserted` / `<sig> is high` / `<sig> must be high` -> `sig`
- `<sig> is deasserted` / `<sig> is low` / `<sig> must be low` -> `!sig`
- `<sig1> and <sig2> are high` -> `sig1 && sig2`
- `<sig> value is zero` -> `sig == 0`

Trailing temporal qualifiers (`on the next cycle`, `within N cycles`,
`after N cycles`) are carried structurally as the intent's `min_delay`/`max_delay`
and stripped from the boolean expression.

Anything outside these shapes is recorded as an ambiguity and the property is
**not** emitted.

## Reset semantics must be reviewed

Reset polarity is inferred only from lexical/type evidence in the manifest
(`_n`/`rst_n`/`resetn` suffix, or `signal_type` of `active_low`/`active_high`).
When unknown, a reset-state property is rejected and `disable iff` is omitted
rather than guessed. A human must confirm reset semantics before signoff.
