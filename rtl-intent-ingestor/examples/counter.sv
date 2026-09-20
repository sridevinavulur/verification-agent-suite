// Public example RTL: a parameterized up-counter with synchronous load.
// Constrained synthesizable Verilog subset - safe for public use.
module counter #(
    parameter WIDTH = 8
) (
    input  wire              clk,
    input  wire              rst_n,      // active-low async reset
    input  wire              en,
    input  wire              load,
    input  wire [WIDTH-1:0]  load_value,
    output reg  [WIDTH-1:0]  count,
    output wire              overflow
);

    wire [WIDTH-1:0] next_count;

    assign next_count = count + 1'b1;
    assign overflow   = en & (count == {WIDTH{1'b1}});

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= {WIDTH{1'b0}};
        end else if (load) begin
            count <= load_value;
        end else if (en) begin
            count <= next_count;
        end
    end

endmodule
