// Bad FIFO assertions.
// Manifest: examples/manifests/fifo.manifest.json  (rst active-high)

module fifo_bad_sva;

  // BAD: no clock at all (MISSING_CLOCK).
  property no_clock;
    disable iff (rst) full |-> !push;
  endproperty
  assert property (no_clock);

  // BAD: trivially passing -- constant true body (TRIVIALLY_PASSING).
  property always_true;
    @(posedge clk) disable iff (rst) 1'b1;
  endproperty
  assert property (always_true);

  // BAD: antecedent constant false -> vacuous by construction (TRIVIALLY_PASSING).
  property never_fires;
    @(posedge clk) disable iff (rst) 1'b0 |-> !full;
  endproperty
  assert property (never_fires);

  // BAD: overlapping |-> followed by ##1 (IMPLICATION_STYLE_RISK).
  property style_risk;
    @(posedge clk) disable iff (rst) push |-> ##1 !empty;
  endproperty
  assert property (style_risk);

  // BAD: assumption on internal state 'count' (ASSUME_CONSTRAINS_OUTPUT),
  //      width mismatch (count is 4-bit, literal is 8-bit).
  property assume_count;
    @(posedge clk) disable iff (rst) count == 8'h00;
  endproperty
  assume property (assume_count);

endmodule
