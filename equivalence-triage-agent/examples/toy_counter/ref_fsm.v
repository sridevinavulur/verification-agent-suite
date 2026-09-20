// Reference FSM (toy, public): binary-encoded 3-state machine with a gated
// enable. INTENTIONAL inequivalence vs rev_fsm.v: revised is one-hot encoded
// and drops the enable gating.
module ref_fsm (
    input        clk,
    input        rst_n,
    input        en,          // enable gates state advance
    output [1:0] state        // binary encoding
);
    reg [1:0] state_r;
    assign state = state_r;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state_r <= 2'b00;
        else if (en)          // gated
            state_r <= (state_r == 2'b10) ? 2'b00 : state_r + 1'b1;
    end
endmodule
