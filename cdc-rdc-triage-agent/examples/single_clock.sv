// Public toy example: a single-clock, single-reset design.
//
// There are NO clock- or reset-domain crossings here.  The triage tool should
// report zero candidate crossings -- which is NOT the same as "CDC clean".
//
// All content is public and non-proprietary.

module single_clock (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] d,
    output reg  [7:0] q
);

    reg [7:0] stage1;

    always @(posedge clk) begin
        if (!rst_n)
            stage1 <= 8'h00;
        else
            stage1 <= d;
    end

    always @(posedge clk) begin
        if (!rst_n)
            q <= 8'h00;
        else
            q <= stage1;
    end

endmodule
