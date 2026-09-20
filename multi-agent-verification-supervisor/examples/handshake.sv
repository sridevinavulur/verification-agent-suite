// Public toy RTL: simple req/grant handshake.
// Used only as a symbol source for the mocked RTL Intent Ingestor.
module handshake (
    input  wire clk,
    input  wire rst_n,   // active-low reset
    input  wire req,
    output reg  grant
);
    // Internal: a request is "accepted" the cycle after it is seen.
    reg req_accepted;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            req_accepted <= 1'b0;
            grant        <= 1'b0;
        end else begin
            req_accepted <= req;
            grant        <= req_accepted;  // grant one cycle after acceptance
        end
    end
endmodule
