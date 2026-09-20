// Public toy example for STRUCTURAL CDC triage.
//
// Two clock domains: clk_a and clk_b.
//   * flag_a is a 1-bit signal generated in the clk_a domain, then passed
//     through a classic 2-FF synchronizer (sync_ff1 -> sync_ff2) in clk_b.
//   * bus_a is an 8-bit bus captured directly into clk_b with NO synchronizer
//     (an intentional multi-bit CDC hazard the triage tool should flag HIGH).
//
// This file is fed to rtl-intent-ingestor to produce the manifest that the
// CDC/RDC triage agent consumes.  All content is public and non-proprietary.

module cdc_sync (
    input  wire       clk_a,
    input  wire       rst_a,
    input  wire       clk_b,
    input  wire       rst_b,
    input  wire       d_a,
    input  wire [7:0] data_a,
    output reg        flag_b,
    output reg [7:0]  bus_b
);

    reg       flag_a;
    reg [7:0] bus_a;
    reg       sync_ff1;
    reg       sync_ff2;

    // ---- clk_a domain -------------------------------------------------
    always @(posedge clk_a or posedge rst_a) begin
        if (rst_a) begin
            flag_a <= 1'b0;
            bus_a  <= 8'h00;
        end else begin
            flag_a <= d_a;
            bus_a  <= data_a;
        end
    end

    // ---- clk_b domain: 2-FF synchronizer on flag_a --------------------
    always @(posedge clk_b or posedge rst_b) begin
        if (rst_b) begin
            sync_ff1 <= 1'b0;
            sync_ff2 <= 1'b0;
        end else begin
            sync_ff1 <= flag_a;
            sync_ff2 <= sync_ff1;
        end
    end

    always @(posedge clk_b or posedge rst_b) begin
        if (rst_b) begin
            flag_b <= 1'b0;
        end else begin
            flag_b <= sync_ff2;
        end
    end

    // ---- clk_b domain: UNSYNCHRONIZED multi-bit capture (hazard) -------
    always @(posedge clk_b or posedge rst_b) begin
        if (rst_b) begin
            bus_b <= 8'h00;
        end else begin
            bus_b <= bus_a;
        end
    end

endmodule
