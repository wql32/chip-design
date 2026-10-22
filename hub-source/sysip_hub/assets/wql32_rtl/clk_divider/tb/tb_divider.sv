`timescale 1ns/1ps
module tb_divider;
    parameter FACTOR = 5;
    parameter MODE = 1;
    localparam LEGAL_EVEN = MODE == 0 && FACTOR >= 2 && FACTOR%2 == 0;
    localparam LEGAL_ODD = MODE == 1 && FACTOR >= 3 && FACTOR%2 == 1;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1, enable = 0;
    wire out;
    clk_divider #(.DIV_FACTOR(FACTOR), .DIV_MODE(MODE)) dut (.clk_in(clk), .rst_n(rst), .clk_en(enable), .clk_out(out));
    integer enabled_edges = 0, previous, trial, seed;
    reg step_enabled = 0, expected = 0;
    function positive_wave(input integer edges);
        positive_wave = edges > 0 && ((edges-1)%FACTOR) < FACTOR/2;
    endfunction
    always @(posedge clk or negedge rst) begin
        if (!rst) begin enabled_edges = 0; step_enabled = 0; expected = 0; end
        else begin
            step_enabled = enable;
            previous = enabled_edges;
            if (enable) enabled_edges = enabled_edges+1;
            if (LEGAL_EVEN) expected = (enabled_edges/(FACTOR/2))%2;
            else if (LEGAL_ODD && enable) expected = positive_wave(enabled_edges) | positive_wave(previous);
            else if (!LEGAL_ODD) expected = 0;
        end
        #1;
        if (out !== expected) $fatal(1, "Divider positive edge mismatch FACTOR=%0d MODE=%0d", FACTOR, MODE);
    end
    always @(negedge clk) begin
        if (!rst) expected = 0;
        else if (LEGAL_ODD && step_enabled) expected = positive_wave(enabled_edges);
        #1;
        if (out !== expected) $fatal(1, "Divider negative edge mismatch");
    end
    initial begin
        seed = 32'h20261021;
        #1; rst = 0;
        repeat (3) @(negedge clk);
        #2; rst = 1; enable = 1;
        repeat (200) @(negedge clk);
        for (trial = 0; trial < 300; trial = trial+1) begin
            @(negedge clk); #2; enable = $random(seed)&1;
        end
        #2; rst = 0;
        #2; if (out !== 1'b0) $fatal(1, "Asynchronous reset did not clear output");
        repeat (3) @(negedge clk);
        #2; rst = 1; enable = 1;
        repeat (200) @(negedge clk);
        #2;
        $display("PASS tb_divider FACTOR=%0d MODE=%0d", FACTOR, MODE);
        $finish;
    end
endmodule
