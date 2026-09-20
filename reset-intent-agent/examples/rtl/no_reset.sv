// Toy example: sequential logic with NO reset.
// The tool should flag a HIGH-severity "no_reset" risk and quiescence risks
// for the uninitialised registers.
module no_reset (
    input  wire       clk,
    input  wire [7:0] d,
    output reg  [7:0] q
);

    always @(posedge clk) begin
        q <= d;
    end

endmodule
