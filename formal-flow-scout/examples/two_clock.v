// Public toy RTL: two independent clock domains feeding a combinational compare.
// Demonstrates a multi-clock COI soundness risk (NOT safe to partition per clock
// without CDC synchronization assumptions).
module two_clock (
    input  wire       clk_a,
    input  wire       clk_b,
    input  wire       rst,
    input  wire [7:0] din_a,
    input  wire [7:0] din_b,
    output wire       mismatch
);
    reg [7:0] reg_a;
    reg [7:0] reg_b;

    assign mismatch = (reg_a != reg_b);

    always @(posedge clk_a) begin
        if (rst) reg_a <= 8'h00;
        else     reg_a <= din_a;
    end

    always @(posedge clk_b) begin
        if (rst) reg_b <= 8'h00;
        else     reg_b <= din_b;
    end
endmodule
