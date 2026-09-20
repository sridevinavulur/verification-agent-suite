// Public toy benchmark: a valid/ready skid-free registered handshake stage.
// Constrained synthesizable Verilog subset. No proprietary content.
module valid_ready (
    input  wire       clk,
    input  wire       rst_n,       // active-low asynchronous reset
    input  wire       in_valid,
    input  wire [7:0] in_data,
    output reg        out_valid,
    output reg  [7:0] out_data,
    input  wire       out_ready
);

    wire accept;
    assign accept = in_valid && out_ready;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_data  <= 8'h00;
        end else begin
            if (accept) begin
                out_valid <= 1'b1;
                out_data  <= in_data;
            end else if (out_ready) begin
                out_valid <= 1'b0;
            end
        end
    end

endmodule
