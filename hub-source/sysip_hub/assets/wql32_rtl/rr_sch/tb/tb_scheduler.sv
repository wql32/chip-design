`timescale 1ns/1ps
// Self-checking bench distributed with the design asset.
module tb_scheduler;
    parameter N = 5;
    reg clk = 0;
    always #5 clk = ~clk;
    reg reset_n = 0, enable = 0;
    reg [N-1:0] req = 0;
    wire [N-1:0] grant, valid;
    integer last, offset, selected, candidate, trial, idx, initial_last, seed;
    reg [N-1:0] stimulus, expected;
    reg [N-1:0] expected_valid;
    rr_sch #(.REQ_NUM(N)) dut (.i_clk(clk), .i_rst_n(reset_n), .i_sch_en(enable), .i_req(req), .o_gnt_vld(valid), .o_gnt(grant));

    task step(input [N-1:0] request, input accept, input rst);
        begin
            @(negedge clk);
            req = request;
            enable = accept;
            reset_n = rst;
            expected = 0;
            selected = -1;
            if (!rst) last = N-1;
            else if (accept) begin
                for (offset = 1; offset <= N; offset = offset+1) begin
                    candidate = (last + offset) % N;
                    if (selected < 0 && request[candidate]) begin
                        selected = candidate;
                        expected[candidate] = 1;
                    end
                end
            end
            expected_valid = 0;
            expected_valid[0] = |expected;
            #1;
            if (grant !== expected || valid !== expected_valid)
                $fatal(1, "Scheduler mismatch N=%0d req=%h enable=%0b last=%0d grant=%h expected=%h valid=%h", N, request, accept, last, grant, expected, valid);
            @(posedge clk);
            if (selected >= 0) last = selected;
        end
    endtask

    initial begin
        last = N-1;
        seed = 32'h20261021;
        step(0, 0, 0);
        // Reproduce the original failure: only requester 1 active after reset.
        stimulus = 0;
        stimulus[(N > 1) ? 1 : 0] = 1;
        step(stimulus, 1, 1);
        if (N <= 8) begin
            for (initial_last = 0; initial_last < N; initial_last = initial_last+1) begin
                for (trial = 0; trial < (1 << N); trial = trial+1) begin
                    step(0, 0, 0);
                    stimulus = 0;
                    stimulus[initial_last] = 1;
                    step(stimulus, 1, 1);
                    step(trial, 0, 1);
                    step(trial, 1, 1);
                end
            end
        end
        for (trial = 0; trial < 2000; trial = trial+1) begin
            for (idx = 0; idx < N; idx = idx+1) stimulus[idx] = $random(seed);
            step(stimulus, (trial % 3) != 0, (trial % 47) != 0);
        end
        step(0, 0, 0);
        for (trial = 0; trial < N*3; trial = trial+1) step({N{1'b1}}, 1, 1);
        $display("PASS tb_scheduler N=%0d", N);
        $finish;
    end
    initial begin #2000000; $fatal(1, "Scheduler test timeout"); end
endmodule
