// Public toy benchmark: an 8-bit saturating up-counter with load and enable.
// Constrained synthesizable Verilog subset (see README for supported constructs).
// No proprietary content.
module counter (
    input  wire       clk,
    input  wire       rst_n,     // active-low asynchronous reset
    input  wire       en,        // count enable
    input  wire       load,      // synchronous load
    input  wire [7:0] load_val,  // value to load
    output reg  [7:0] count,     // current count
    output wire       at_max     // high when saturated
);

    localparam [7:0] MAX_COUNT = 8'hFF;

    assign at_max = (count == MAX_COUNT);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 8'h00;
        end else begin
            if (load) begin
                count <= load_val;
            end else if (en) begin
                if (count < MAX_COUNT) begin
                    count <= count + 1;
                end
            end
        end
    end

endmodule
