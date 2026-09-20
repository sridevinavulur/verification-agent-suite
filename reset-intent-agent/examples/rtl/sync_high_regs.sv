// Toy example: synchronous, active-high reset driving several registers.
// Exercises sync reset detection, multi-register domain, and reset values.
module sync_high_regs (
    input  wire       clk,
    input  wire       rst,     // active-high synchronous reset
    input  wire [7:0] d,
    output reg  [7:0] q,
    output reg        valid,
    output reg  [3:0] state
);

    always @(posedge clk) begin
        if (rst) begin
            q     <= 8'h00;
            valid <= 1'b0;
            state <= 4'd0;
        end else begin
            q     <= d;
            valid <= 1'b1;
            state <= state + 1'b1;
        end
    end

endmodule
