// Public example RTL: a valid/ready producer + consumer connected in a top.
// Demonstrates handshake signals and a two-level hierarchy.
// Constrained synthesizable Verilog subset - safe for public use.

module vr_producer #(
    parameter WIDTH = 8
) (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              start,
    output reg               out_valid,
    input  wire              out_ready,
    output reg  [WIDTH-1:0]  out_data
);

    reg [WIDTH-1:0] counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_data  <= {WIDTH{1'b0}};
            counter   <= {WIDTH{1'b0}};
        end else begin
            if (start & ~out_valid) begin
                out_valid <= 1'b1;
                out_data  <= counter;
            end else if (out_valid & out_ready) begin
                out_valid <= 1'b0;
                counter   <= counter + 1'b1;
            end
        end
    end

endmodule


module vr_consumer #(
    parameter WIDTH = 8
) (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              in_valid,
    output reg               in_ready,
    input  wire [WIDTH-1:0]  in_data,
    output reg  [WIDTH-1:0]  last_data
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            in_ready  <= 1'b1;
            last_data <= {WIDTH{1'b0}};
        end else begin
            if (in_valid & in_ready) begin
                last_data <= in_data;
            end
        end
    end

endmodule


module vr_top #(
    parameter WIDTH = 8
) (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              start,
    output wire [WIDTH-1:0]  observed
);

    wire              valid;
    wire              ready;
    wire [WIDTH-1:0]  data;

    vr_producer #(.WIDTH(WIDTH)) u_producer (
        .clk       (clk),
        .rst_n     (rst_n),
        .start     (start),
        .out_valid (valid),
        .out_ready (ready),
        .out_data  (data)
    );

    vr_consumer #(.WIDTH(WIDTH)) u_consumer (
        .clk       (clk),
        .rst_n     (rst_n),
        .in_valid  (valid),
        .in_ready  (ready),
        .in_data   (data),
        .last_data (observed)
    );

endmodule
