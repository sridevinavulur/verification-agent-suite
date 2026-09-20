// Public toy RTL: a saturating up-counter with synchronous reset.
module counter (
    input  wire       clk,
    input  wire       rst,
    input  wire       en,
    output wire       at_max,
    output wire [7:0] value
);
    reg [7:0] cnt;

    assign at_max = (cnt == 8'hFF);
    assign value  = cnt;

    always @(posedge clk) begin
        if (rst)
            cnt <= 8'h00;
        else if (en && !at_max)
            cnt <= cnt + 8'h01;
    end
endmodule
