// Public toy RTL for security-property-agent examples.
// NOT a real design. Illustrative only. No proprietary content.
//
// Covers: access control, privilege gating, debug lockout, fault response,
// error containment, and a lockstep pair.

module secure_soc (
    input  wire        clk,
    input  wire        rst_n,          // active-low reset

    // access control
    input  wire        mem_wr_en,      // requested write
    input  wire        wr_grant,       // access granted by permission unit
    output reg         wr_commit,      // committed write

    // privilege gating
    input  wire        secure_op,      // an operation requiring privilege
    input  wire        priv_mode,      // 1 = privileged

    // debug lockout
    input  wire        dbg_req,        // debug wants to enable
    input  wire        dbg_locked,     // lifecycle lock asserted
    output reg         dbg_enable,     // debug actually enabled

    // fault response
    input  wire        fault_detected,
    output reg         safe_halt,

    // error containment
    input  wire        ecc_error,
    output reg         data_valid_out,

    // lockstep pair
    output reg  [7:0]  core_a_result,
    output reg  [7:0]  core_b_result,
    output reg         lockstep_mismatch
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_commit         <= 1'b0;
            dbg_enable        <= 1'b0;
            safe_halt         <= 1'b0;
            data_valid_out    <= 1'b0;
            core_a_result     <= 8'h00;
            core_b_result     <= 8'h00;
            lockstep_mismatch <= 1'b0;
        end else begin
            wr_commit         <= mem_wr_en & wr_grant;
            dbg_enable        <= dbg_req & ~dbg_locked;
            safe_halt         <= fault_detected;
            data_valid_out    <= ~ecc_error;
            lockstep_mismatch <= (core_a_result != core_b_result);
        end
    end

endmodule
