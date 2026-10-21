`timescale 1ns/1ps
module tb_pointer_pool;
    parameter N = 9;
    localparam PW = (N > 1) ? $clog2(N) : 1;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 0, allocate = 0, release_req = 0;
    reg [PW-1:0] release_ptr = 0;
    wire [PW-1:0] pointer;
    wire valid;
    wire [PW:0] free_count;
    free_ptr_mng #(.PTR_NUM(N)) dut (.i_clk(clk), .i_rst_n(rst), .i_alc_req(allocate), .o_alc_ptr(pointer), .o_alc_vld(valid), .i_rls_req(release_req), .i_rls_ptr(release_ptr), .o_ptr_num(free_count));
    reg allocated [0:N-1];
    integer count = N, accepted_alloc, accepted_release, selected, idx, trial, seed;

    task step(input alc, input rls, input integer ptr, input reset_n);
        begin
            @(negedge clk);
            allocate = alc; release_req = rls; release_ptr = ptr; rst = reset_n;
            #1;
            if (valid && (pointer >= N || allocated[pointer] || count == 0)) $fatal(1, "Invalid/repeated allocation");
            if (!valid && pointer !== {PW{1'b0}}) $fatal(1, "Invalid output pointer must be zero");
            accepted_alloc = reset_n && alc && valid;
            accepted_release = 0;
            if (reset_n && rls && release_ptr < N) accepted_release = allocated[release_ptr];
            selected = pointer;
            @(posedge clk);
            if (!reset_n) begin
                count = N;
                for (idx = 0; idx < N; idx = idx+1) allocated[idx] = 0;
            end else begin
                if (accepted_alloc) begin allocated[selected] = 1; count = count-1; end
                if (accepted_release) begin allocated[release_ptr] = 0; count = count+1; end
            end
            #1;
            if (free_count !== count) $fatal(1, "Total free count mismatch got=%0d expected=%0d", free_count, count);
        end
    endtask

    initial begin
        seed = 32'h20261021;
        step(1,1,0,0);
        for (trial = 0; trial < N*3+5; trial = trial+1) step(1,0,0,1);
        if (count != 0 || valid) $fatal(1, "Pool did not exhaust every pointer including 0");
        step(0,1,0,1);
        step(0,1,0,1); // Duplicate free must not increase total.
        repeat (5) step(1,1,0,1);
        for (trial = 0; trial < 3000; trial = trial+1)
            step($random(seed)&1,$random(seed)&1,$random(seed)&((1<<PW)-1),(trial%251)!=0);
        step(0,0,0,0);
        for (trial = 0; trial < N*3+5; trial = trial+1) step(1,0,0,1);
        if (count != 0) $fatal(1, "Pool failed to recover after reset");
        $display("PASS tb_pointer_pool N=%0d", N);
        $finish;
    end
endmodule
