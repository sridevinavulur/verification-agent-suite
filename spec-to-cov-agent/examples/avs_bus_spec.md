# AVSBus 2.0 Controller — Design Specification

## Overview

`apb2avsbus` is a generic APB-to-AVSBus 2.0 bridge controller (public example design).
The DUT accepts APB register write/read commands and translates them to 48-bit AVSBus 2.0 serial frames.

## Protocol

- **Protocol**: AVSBus 2.0
- **Frame width**: 48 bits, MSB-first
- **Bus topology**: Open-drain, shared controller/target bus (`avs_data`)
- **Controller subframe**: cmd_data_type[3:0], data[9:0], addr[5:0], target_id[4:0], retry[3:0], CRC-3[2:0]
- **Target subframe**: pending_ack[2:0], CRC-3[2:0] (returned in same frame after turnaround)

## Interfaces

### APB Slave Interface
- Role: slave
- Signals: PCLK (input), PRESETn (input, active_low), PADDR[11:0] (input), PWDATA[31:0] (input), PRDATA[31:0] (output), PSEL (input), PENABLE (input), PWRITE (input), PREADY (output, hardwired=1)

### AVSBus Interface
- Role: master
- Signals: avs_data (inout, open-drain), avs_clk (output)
- Clock select: clksel (input) — 0=bitclk=sysclk, 1=divided

## Registers (APB address map)

| Register | Offset | Access | Reset | Description |
|----------|--------|--------|-------|-------------|
| CTRL | 0x00 | RW | 0 | Control: [0]=start, [1]=abort, [4]=clksel |
| STATUS | 0x04 | RO | 0 | Status: [0]=busy, [1]=done, [2]=error |
| CMD_DATA | 0x08 | RW | 0 | [3:0]=cmd_type, [13:4]=data, [19:14]=addr, [24:20]=target_id |
| RBF_DATA | 0x0C | RO | 0 | Readback FIFO: [2:0]=ack, [13:3]=data, depth=8 |
| TIMEOUT | 0x10 | RW | 1023 | Timeout threshold (TIMEOUT_MAX) |

## ACK Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | ACTION_TAKEN | Command executed successfully |
| 1 | RESOURCE_UNAVAILABLE | Target busy |
| 2 | BAD_FRAME_OR_CRC | CRC error detected |
| 3 | BAD_DATA_OR_SELECTOR | Invalid command type or data |

## Command Data Types

| Type | Name | Access |
|------|------|--------|
| 0x0 | RAIL_VOLTAGE | RW |
| 0x1 | RAIL_VOLTAGE_READBACK | RO |
| 0x2 | RAIL_POWER_READBACK | RO |
| 0x3 | RAIL_TEMP_READBACK | RO |
| 0x4 | RAIL_POWER_MODE | RW |
| 0x5 | RAIL_STATUS | RO |
| 0xE | FIRMWARE_VERSION | RO |
| 0xF | DEVICE_ID | RO |
| 0x6–0xD | RESERVED | — |

## FSMs

### TX FSM
- States: TX_IDLE → TX_ARB → TX_FRAME → TX_DONE
- TX_ARB: Wait for bus idle (avs_data=1)
- TX_FRAME: Shift 48 bits, MSB-first
- TX_DONE: Assert STATUS.done

### RX FSM
- States: RX_IDLE → RX_SAMPLE → RX_DONE
- RX_SAMPLE: Sample target subframe after turnaround
- Validates target CRC-3

## Error Conditions

- CRC mismatch → ACK_BAD_FRAME_OR_CRC
- Reserved cmd_type (0x6–0xD) → ACK_BAD_DATA_OR_SELECTOR
- Write to read-only type → ACK_NO_ACTION
- CMD FIFO overflow → STATUS.error

## Corner Cases

- Retry count reaching 0xF (max)
- ACK codes ≥ 4 (undefined in spec)
- clksel=1 divided clock mode
- tx_frame upper 48 bits (dead code if AVS frame is 48b)
- PADDR[11:6] silently ignored
- Timeout counter never reaching TIMEOUT_MAX=1023
