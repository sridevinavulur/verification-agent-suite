// Toy example: two reset domains + a structural reset-domain crossing.
// Domain A: rst_a_n (async, active-low) -> reg_a
// Domain B: rst_b   (sync,  active-high) -> reg_b, which reads reg_a.
// The reg_a -> reg_b path is a possible reset-domain crossing (HEURISTIC).
module dual_reset_domains (
    input  wire       clk,
    input  wire       rst_a_n,   // async active-low reset for domain A
    input  wire       rst_b,     // sync  active-high reset for domain B
    input  wire [7:0] din,
    output reg  [7:0] reg_a,
    output reg  [7:0] reg_b
);

    always @(posedge clk or negedge rst_a_n) begin
        if (!rst_a_n)
            reg_a <= 8'h00;
        else
            reg_a <= din;
    end

    always @(posedge clk) begin
        if (rst_b)
            reg_b <= 8'h00;
        else
            reg_b <= reg_a;   // crosses from domain A into domain B
    end

endmodule
