// Reference ALU (toy, public). 8-bit result, active-low async reset.
// INTENTIONAL inequivalence vs rev_alu.v: revised truncates result to 4 bits
// and uses active-high reset. See README for the seeded bugs.
module ref_alu (
    input             clk,
    input             rst_n,      // active-low async reset
    input      [7:0]  a,
    input      [7:0]  b,
    input      [1:0]  op,
    output reg [7:0]  result      // 8-bit result
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            result <= 8'h00;
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
