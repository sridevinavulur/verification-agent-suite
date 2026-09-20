// Toy example: contradictory reset polarity evidence.
// The signal is named 'rst_n' (name suggests active-low) but is used bare in a
// positive guard `if (rst_n)` (suggests active-high). The tool MUST NOT pick a
// polarity silently -- it reports `unknown` and records an ambiguity.
module ambiguous_polarity (
    input  wire       clk,
    input  wire       rst_n,
    output reg  [3:0] q
);

    always @(posedge clk) begin
        if (rst_n)          // contradicts the _n naming convention
            q <= 4'h0;
        else
            q <= q + 1'b1;
    end

endmodule
