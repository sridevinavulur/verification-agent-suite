# UART CSR block

The register map below is parsed from the first Markdown pipe table.

| register | field | address | bits | access | reset | description |
|---|---|---|---|---|---|---|
| TXDATA |        | 0x00 |      | WO  | 0x0 | transmit data register |
| TXDATA | DATA   | 0x00 | 7:0  | WO  | 0x0 | byte to transmit |
| RXDATA |        | 0x04 |      | RO  | 0x0 | receive data register |
| RXDATA | DATA   | 0x04 | 7:0  | RO  | 0x0 | received byte |
| STATUS |        | 0x08 |      | RW  | 0x2 | line status |
| STATUS | RXRDY  | 0x08 | 0    | RO  | 0x0 | receive ready |
| STATUS | TXEMPTY| 0x08 | 1    | RO  | 0x1 | transmit empty |
| STATUS | OVERRUN| 0x08 | 2    | RC  | 0x0 | overrun error (read to clear) |
