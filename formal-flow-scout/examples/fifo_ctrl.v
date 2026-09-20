// Public toy RTL: a small synchronous FIFO controller (pointer/occupancy logic).
// Synthesizable constrained-Verilog subset used by FormalFlow-Scout examples.
// No proprietary content.
module fifo_ctrl (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        push,
    input  wire        pop,
    output wire        full,
    output wire        empty,
    output wire [3:0]  count
);
    reg  [3:0] wr_ptr;
    reg  [3:0] rd_ptr;
    reg  [3:0] occ;

    wire do_push;
    wire do_pop;

    assign do_push = push & ~full;
    assign do_pop  = pop  & ~empty;
    assign full    = (occ == 4'd8);
    assign empty   = (occ == 4'd0);
    assign count   = occ;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 4'd0;
            rd_ptr <= 4'd0;
            occ    <= 4'd0;
        end else begin
            if (do_push) wr_ptr <= wr_ptr + 4'd1;
            if (do_pop)  rd_ptr <= rd_ptr + 4'd1;
            occ <= occ + do_push - do_pop;
        end
    end
endmodule
