// Bad handshake assertions -- each line deliberately trips one or more checks.
// Manifest: examples/manifests/handshake.manifest.json  (rst_n active-low)

module handshake_bad_sva;

  // BAD: rst_n is active-low but disable iff uses it un-negated (RESET_POLARITY_RISK).
  property p1;
    @(posedge clk) disable iff (rst_n)
      req |=> grant;
  endproperty
  assert property (p1);

  // BAD: no disable iff (MISSING_DISABLE_IFF), generic name (NAME_SEMANTICS),
  //      not traced (REQ_TRACEABILITY).
  property p2;
    @(posedge clk) req |-> grant;
  endproperty
  assert property (p2);

  // BAD: assumption constrains a design OUTPUT 'ack' (ASSUME_CONSTRAINS_OUTPUT).
  property assume_ack;
    @(posedge clk) disable iff (!rst_n) ack == 1'b0;
  endproperty
  assume property (assume_ack);

  // BAD: antecedent == consequent, a tautology (ANTECEDENT_IN_CONSEQUENT / weak).
  property req_implies_req;
    @(posedge clk) disable iff (!rst_n) req |-> req;
  endproperty
  assert property (req_implies_req);

  // BAD: undeclared signal 'foo' (UNDECLARED_SIGNAL); width mismatch on data.
  property bad_signals;
    @(posedge clk) disable iff (!rst_n) foo |-> data == 4'hA;
  endproperty
  assert property (bad_signals);

  // BAD: constant-true consequent (WEAK_CONSEQUENT), unbounded delay (UNBOUNDED_TEMPORAL).
  property weak_and_unbounded;
    @(posedge clk) disable iff (!rst_n) req |-> ##[0:$] 1'b1;
  endproperty
  assert property (weak_and_unbounded);

endmodule
