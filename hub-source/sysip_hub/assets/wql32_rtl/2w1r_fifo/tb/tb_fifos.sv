`timescale 1ns/1ps
module tb_fifos;
    parameter DEPTH = 3;
    localparam AFULL = (DEPTH > 1) ? DEPTH-1 : 1;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 0, w0 = 0, w1 = 0, re = 0;
    reg [15:0] d0 = 0, d1 = 0;
    wire [15:0] single_data, dual_data;
    wire sf, sa, se, so, su, df, da, de, dover, du;
    basic_fifo #(.FIFO_WIDTH(16), .FIFO_DEPTH(DEPTH), .AFULL_DEPTH(AFULL)) single_dut
        (.i_clk(clk), .i_rst_n(rst), .i_we(w0), .i_wdata(d0), .i_re(re), .o_rdata(single_data), .o_full(sf), .o_afull(sa), .o_empty(se), .o_overflow(so), .o_underflow(su));
    fifo_2w1r #(.FIFO_WIDTH(16), .FIFO_DEPTH(DEPTH), .AFULL_DEPTH(AFULL)) dual_dut
        (.i_clk(clk), .i_rst_n(rst), .i_we_0(w0), .i_wdata_0(d0), .i_we_1(w1), .i_wdata_1(d1), .i_re(re), .o_rdata(dual_data), .o_full(df), .o_afull(da), .o_empty(de), .o_overflow(dover), .o_underflow(du));
    reg [15:0] sq [0:DEPTH-1], dq [0:DEPTH-1];
    integer sn = 0, dn = 0, sh = 0, st = 0, dh = 0, dt = 0;
    integer sr, sw, dr, dw, requested, serial = 0, trial, seed;

    task check_state;
        begin
            if (sf !== (sn == DEPTH) || se !== (sn == 0) || sa !== (sn >= AFULL)) $fatal(1, "Single FIFO flags");
            if (df !== (dn == DEPTH) || de !== (dn == 0) || da !== (dn >= AFULL)) $fatal(1, "Dual FIFO flags");
            if (single_data !== ((sn != 0 && rst) ? sq[sh] : 16'b0)) $fatal(1, "Single FIFO data");
            if (dual_data !== ((dn != 0 && rst) ? dq[dh] : 16'b0)) $fatal(1, "Dual FIFO data");
        end
    endtask

    task step(input we0, input we1, input rd, input reset_n);
        begin
            @(negedge clk);
            w0 = we0; w1 = we1; re = rd; rst = reset_n;
            d0 = serial; d1 = serial+1; serial = serial+2;
            sr = reset_n && rd && sn != 0;
            sw = reset_n && we0 && (sn < DEPTH || sr);
            dr = reset_n && rd && dn != 0;
            requested = we0 + int'(we1);
            dw = reset_n && (requested != 0) && (requested <= DEPTH-dn+dr);
            #1;
            if (reset_n) check_state();
            if (so !== (reset_n && we0 && !sw) || su !== (reset_n && rd && !sr)) $fatal(1, "Single FIFO errors");
            if (dover !== (reset_n && requested != 0 && !dw) || du !== (reset_n && rd && !dr)) $fatal(1, "Dual FIFO errors");
            @(posedge clk);
            if (!reset_n) begin sn = 0; dn = 0; sh = 0; st = 0; dh = 0; dt = 0; end
            else begin
                if (sr) begin sh = (sh+1)%DEPTH; sn = sn-1; end
                if (sw) begin sq[st] = d0; st = (st+1)%DEPTH; sn = sn+1; end
                if (dr) begin dh = (dh+1)%DEPTH; dn = dn-1; end
                if (dw && we0) begin dq[dt] = d0; dt = (dt+1)%DEPTH; dn = dn+1; end
                if (dw && we1) begin dq[dt] = d1; dt = (dt+1)%DEPTH; dn = dn+1; end
            end
            #1;
            check_state();
        end
    endtask

    initial begin
        seed = 32'h20261021;
        step(1, 1, 1, 0);
        step(1, 0, 1, 1); // Empty read does not consume the simultaneous write.
        step(0, 0, 1, 1);
        for (trial = 0; trial < DEPTH-1; trial = trial+1) step(1, 0, 0, 1);
        step(1, 1, 0, 1); // Exactly one free entry: reject complete pair.
        step(1, 0, 0, 1);
        step(1, 0, 1, 1); // Full read/write replacement.
        step(1, 1, 1, 1);
        for (trial = 0; trial < 3000; trial = trial+1)
            step($random(seed)&1, $random(seed)&1, $random(seed)&1, (trial%173)!=0);
        for (trial = 0; trial < DEPTH+2; trial = trial+1) step(0, 0, 1, 1);
        $display("PASS tb_fifos DEPTH=%0d", DEPTH);
        $finish;
    end
endmodule
