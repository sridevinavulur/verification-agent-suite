// Public toy testbench for the counter (minimal, illustrative only).
module counter_tb;
    logic clk = 0, rst = 1, en = 0;
    logic [7:0] count;

    counter #(.WIDTH(8)) dut (.clk(clk), .rst(rst), .en(en), .count(count));

    always #5 clk = ~clk;

    initial begin
        repeat (2) @(posedge clk);
        rst = 0; en = 1;
        repeat (10) @(posedge clk);
        if (count == 8'd10)
            $display("PASS: count=%0d", count);
        else
            $display("FAIL: count=%0d", count);
        $finish;
    end
endmodule
