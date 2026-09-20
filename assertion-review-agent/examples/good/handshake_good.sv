// Good handshake assertions.
// Manifest: examples/manifests/handshake.manifest.json
// rst_n is active-low, so reset is guarded with "disable iff (!rst_n)".

module handshake_sva;

  // @requirement: REQ-HS-001
  // When req is asserted, grant must arrive on the next cycle.
  property req_gets_grant;
    @(posedge clk) disable iff (!rst_n)
      req |=> grant;
  endproperty
  assert property (req_gets_grant);

  // @requirement: REQ-HS-002
  // A grant is only issued in response to an outstanding req (same cycle).
  property grant_needs_req;
    @(posedge clk) disable iff (!rst_n)
      grant |-> req;
  endproperty
  assert property (grant_needs_req);

  // @requirement: REQ-HS-003
  // ack follows req within 1 to 3 cycles.
  property ack_within_window;
    @(posedge clk) disable iff (!rst_n)
      req |-> ##[1:3] ack;
  endproperty
  assert property (ack_within_window);

endmodule
