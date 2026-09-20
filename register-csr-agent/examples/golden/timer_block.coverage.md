# Coverage Matrix

| register | field | access | checks | #sva | #tests |
|---|---|---|---|---|---|
| CTRL | ENABLE | RW | readback,reset_value | 2 | 0 |
| CTRL | MODE | RW | readback,reset_value | 2 | 0 |
| CTRL | RSVD | RESERVED | readback,reset_value | 2 | 0 |
| LOAD | - | RW | reset_value | 1 | 1 |
| COUNT | - | RO | reset_value | 1 | 1 |
| STATUS | EXPIRED | W1C | reset_value,side_effects | 2 | 0 |
| STATUS | OVERRUN | W1C | reset_value,side_effects | 2 | 0 |
| STATUS | RSVD | RESERVED | readback,reset_value | 2 | 0 |