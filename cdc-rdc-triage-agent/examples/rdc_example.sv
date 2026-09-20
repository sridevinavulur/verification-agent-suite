// Public toy example for STRUCTURAL RDC (reset-domain crossing) triage.
//
// One clock (clk), TWO asynchronous reset domains:
//   * rst_x  resets the src_reg flops
//   * rst_y  resets the dst_reg flops
// dst_reg samples src_reg on the same clock but across reset domains -- a
// candidate reset-domain crossing the triage tool should flag.
//
// All content is public and non-proprietary.

module rdc_example (
    input  wire clk,
    input  wire rst_x,
    input  wire rst_y,
    input  wire d,
    output reg  q
);

    reg src_reg;
    reg dst_reg;

    // reset domain X
    always @(posedge clk or posedge rst_x) begin
        if (rst_x)
            src_reg <= 1'b0;
        else
            src_reg <= d;
    end

    // reset domain Y -- reads src_reg (RDC candidate)
    always @(posedge clk or posedge rst_y) begin
        if (rst_y)
            dst_reg <= 1'b0;
        else
            dst_reg <= src_reg;
    end

    always @(posedge clk or posedge rst_y) begin
        if (rst_y)
            q <= 1'b0;
        else
            q <= dst_reg;
    end

endmodule
