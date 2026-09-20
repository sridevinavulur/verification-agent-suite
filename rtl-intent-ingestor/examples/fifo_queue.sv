// Public example RTL: a small synchronous FIFO-like queue.
// Constrained synthesizable Verilog subset - safe for public use.
module fifo_queue #(
    parameter WIDTH = 8,
    parameter DEPTH = 4,
    parameter ADDR  = 2
) (
    input  wire              clk,
    input  wire              rst,        // active-high sync reset
    input  wire              wr_en,
    input  wire [WIDTH-1:0]  wr_data,
    input  wire              rd_en,
    output reg  [WIDTH-1:0]  rd_data,
    output wire              full,
    output wire              empty
);

    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [ADDR:0]    wr_ptr;
    reg [ADDR:0]    rd_ptr;

    wire do_write;
    wire do_read;

    assign do_write = wr_en & ~full;
    assign do_read  = rd_en & ~empty;
    assign full     = (wr_ptr[ADDR] != rd_ptr[ADDR]) &&
                      (wr_ptr[ADDR-1:0] == rd_ptr[ADDR-1:0]);
    assign empty    = (wr_ptr == rd_ptr);

    always @(posedge clk) begin
        if (rst) begin
            wr_ptr <= {(ADDR+1){1'b0}};
        end else if (do_write) begin
            wr_ptr <= wr_ptr + 1'b1;
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            rd_ptr <= {(ADDR+1){1'b0}};
        end else if (do_read) begin
            rd_ptr <= rd_ptr + 1'b1;
        end
    end

    always @(posedge clk) begin
        if (do_read) begin
            rd_data <= mem[rd_ptr[ADDR-1:0]];
        end
    end

endmodule
