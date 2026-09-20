// Good FIFO assertions.
// Manifest: examples/manifests/fifo.manifest.json
// rst is active-high, so reset is guarded with "disable iff (rst)".

module fifo_sva;

  // @requirement: REQ-FIFO-001
  // No push when full (overflow protection).
  property no_overflow;
    @(posedge clk) disable iff (rst)
      full |-> !push;
  endproperty
  assert property (no_overflow);

  // @requirement: REQ-FIFO-002
  // No pop when empty (underflow protection).
  property no_underflow;
    @(posedge clk) disable iff (rst)
      empty |-> !pop;
  endproperty
  assert property (no_underflow);

  // @requirement: REQ-FIFO-003
  // full and empty are mutually exclusive.
  property full_empty_mutex;
    @(posedge clk) disable iff (rst)
      !(full && empty);
  endproperty
  assert property (full_empty_mutex);

endmodule
