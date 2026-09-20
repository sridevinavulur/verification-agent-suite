// Revised ALU (toy, public) with TWO seeded inequivalences vs ref_alu.v:
//   BUG 1 (width):    result is only 4 bits, so high nibble is dropped.
//   BUG 2 (polarity): reset is active-HIGH synchronous instead of active-low.
module rev_alu (
    input             clk,
    input             rst,        // active-high sync reset (was rst_n, async)
    input      [7:0]  a,
    input      [7:0]  b,
    input      [1:0]  op,
    output reg [3:0]  result      // BUG: 4-bit result (was 8-bit)
);
    always @(posedge clk) begin
        if (rst)                  // BUG: active-high (was !rst_n)
            result <= 4'h0;
        else begin
            case (op)
                2'b00: result <= a + b;
                2'b01: result <= a - b;
                2'b10: result <= a & b;
                2'b11: result <= a | b;
            endcase
        end
    end
endmodule
