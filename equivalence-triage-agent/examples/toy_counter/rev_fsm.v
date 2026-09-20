// Revised FSM (toy, public) with TWO seeded inequivalences vs ref_fsm.v:
//   BUG 1 (state_encoding): one-hot encoding instead of binary.
//   BUG 2 (gating):         the enable 'en' is ignored, so it advances always.
module rev_fsm (
    input        clk,
    input        rst_n,
    input        en,          // BUG: unused (gating dropped)
    output [2:0] state        // one-hot encoding
);
    reg [2:0] state_r;
    assign state = state_r;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state_r <= 3'b001;
        else                  // BUG: advances unconditionally (no 'en' gate)
            state_r <= (state_r == 3'b100) ? 3'b001 : (state_r << 1);
    end
endmodule
