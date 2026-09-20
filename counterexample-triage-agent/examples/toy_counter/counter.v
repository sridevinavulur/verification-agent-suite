// Toy 4-bit up-counter with an INTENTIONAL, documented bug for triage demos.
//
// Intended behavior:
//   - Synchronous, active-high reset clears count to 0.
//   - When `en` is asserted, count increments each posedge clk.
//   - The property `p_inc`: whenever en is high, the NEXT cycle count must be
//     the previous count + 1 (mod 16).
//
// THE BUG (line 21): the increment is gated by `en & ~stall`, but the property
// and the surrounding logic assume `en` alone drives the increment. When
// `stall` is high while `en` is high, count does NOT advance, so `p_inc`
// fails. This is left in deliberately as the design-under-triage; the triage
// agent must NOT edit this file.
//
// Public toy example. No proprietary content.

module counter (
    input  wire       clk,
    input  wire       rst,      // active-high synchronous reset
    input  wire       en,       // enable increment
    input  wire       stall,    // (bug) unexpectedly gates the increment
    output reg  [3:0] count
);

    always @(posedge clk) begin
        if (rst)
            count <= 4'd0;
        else if (en & ~stall)          // BUG: should be `else if (en)`
            count <= count + 4'd1;
        // else: hold
    end

endmodule
