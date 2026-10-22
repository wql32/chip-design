`timescale 1ns/1ps
module tb_storage;
    parameter DEPTH = 3;
    parameter PIN = 0;
    parameter POUT = 0;
    localparam AW = (DEPTH > 1) ? $clog2(DEPTH) : 1;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1, we = 0, re = 0, ce = 0, se = 0;
    reg [AW-1:0] wa = 0, ra = 0, ca = 0;
    reg [15:0] wd = 0, key = 0;
    wire [15:0] arr_out, cam_out;
    wire [AW-1:0] search_out;
    ff_array #(.DATA_WIDTH(16), .ARRAY_DEPTH(DEPTH), .FLOP_IN(PIN), .FLOP_OUT(POUT)) arr_dut
        (.i_clk(clk), .i_rst_n(rst), .i_wen(we), .i_waddr(wa), .i_wdata(wd), .i_ren(re), .i_raddr(ra), .o_rdata(arr_out));
    ff_cam #(.DATA_WIDTH(16), .ARRAY_DEPTH(DEPTH), .FLOP_IN(PIN), .FLOP_OUT(POUT)) cam_dut
        (.i_clk(clk), .i_rst_n(rst), .i_wen(we), .i_waddr(wa), .i_wdata(wd), .i_ren(re), .i_raddr(ra), .o_rdata(cam_out), .i_cen(ce), .i_caddr(ca), .i_sen(se), .i_skey(key), .o_saddr(search_out));
    reg [15:0] array_model [0:DEPTH-1], cam_model [0:DEPTH-1];
    reg cam_valid [0:DEPTH-1];
    reg pw = 0, pr = 0, pc = 0, ps = 0;
    integer pwa = 0, pra = 0, pca = 0;
    reg [15:0] pwd = 0, pk = 0;
    reg ew, er, ec, es;
    integer ewa, era, eca, found, idx, trial, seed;
    reg [15:0] ewd, ek, ar_value, cr_value, ar_registered = 0, cr_registered = 0;
    reg [AW-1:0] search_value, search_registered = 0;

    task evaluate_reads;
        begin
            ar_value = 0; cr_value = 0; search_value = 0; found = -1;
            if (rst && er && era < DEPTH) begin
                ar_value = array_model[era];
                if (cam_valid[era]) cr_value = cam_model[era];
            end
            for (idx = 0; idx < DEPTH; idx = idx+1)
                if (rst && es && cam_valid[idx] && cam_model[idx] == ek && found < 0) found = idx;
            if (found >= 0) search_value = found;
        end
    endtask

    task step(input rw, input integer rwa, input [15:0] rwd, input rr, input integer rra,
              input rc, input integer rca, input rs, input [15:0] rk, input reset_n);
        begin
            @(negedge clk);
            we = rw; wa = rwa; wd = rwd; re = rr; ra = rra;
            ce = rc; ca = rca; se = rs; key = rk; rst = reset_n;
            ew = PIN ? pw : we; er = PIN ? pr : re; ec = PIN ? pc : ce; es = PIN ? ps : se;
            ewa = PIN ? pwa : wa; era = PIN ? pra : ra; eca = PIN ? pca : ca;
            ewd = PIN ? pwd : wd; ek = PIN ? pk : key;
            evaluate_reads();
            @(posedge clk);
            if (!rst) begin
                ar_registered = 0; cr_registered = 0; search_registered = 0;
                pw = 0; pr = 0; pc = 0; ps = 0; pwa = 0; pra = 0; pca = 0; pwd = 0; pk = 0;
                for (idx = 0; idx < DEPTH; idx = idx+1) begin cam_valid[idx] = 0; cam_model[idx] = 0; end
            end else begin
                if (er) begin ar_registered = ar_value; cr_registered = cr_value; end
                if (es) search_registered = search_value;
                if (ew && ewa < DEPTH) array_model[ewa] = ewd;
                for (idx = 0; idx < DEPTH; idx = idx+1) begin
                    if (ew && ewa == idx) begin cam_model[idx] = ewd; cam_valid[idx] = 1; end
                    else if (ec && eca == idx) begin cam_model[idx] = 0; cam_valid[idx] = 0; end
                end
                pw = we; pr = re; pc = ce; ps = se; pwa = wa; pra = ra; pca = ca; pwd = wd; pk = key;
            end
            ew = PIN ? pw : we; er = PIN ? pr : re; ec = PIN ? pc : ce; es = PIN ? ps : se;
            era = PIN ? pra : ra; ek = PIN ? pk : key;
            evaluate_reads();
            #1;
            if (arr_out !== (POUT ? ar_registered : ar_value)) $fatal(1, "FF array mismatch DEPTH=%0d PIN=%0d POUT=%0d actual=%h expected=%h", DEPTH, PIN, POUT, arr_out, (POUT ? ar_registered : ar_value));
            if (cam_out !== (POUT ? cr_registered : cr_value)) $fatal(1, "CAM read mismatch");
            if (search_out !== (POUT ? search_registered : search_value)) $fatal(1, "CAM search mismatch");
        end
    endtask

    initial begin
        seed = 32'h20261021;
        #1; rst = 0; // Drive a real reset transition, not only a declaration initializer.
        step(0,0,0,0,0,0,0,0,0,0);
        // Initialize every array entry before any legal array read.
        for (trial = 0; trial < DEPTH; trial = trial+1) step(1,trial,trial+100,0,0,0,0,0,0,1);
        repeat (2) step(0,0,0,0,0,0,0,0,0,1);
        for (trial = 0; trial < DEPTH; trial = trial+1) step(0,0,0,1,trial,0,0,1,trial+100,1);
        step(1,0,7,1,0,1,0,1,7,1); // Write wins over clear, registered reads see old state.
        step(1,DEPTH-1,7,1,DEPTH-1,0,0,1,7,1); // Duplicate keys select lowest address.
        repeat (3) step(0,0,0,1,0,0,0,1,7,1);
        for (trial = 0; trial < 1500; trial = trial+1)
            step($random(seed)&1,$random(seed)&((1<<AW)-1),$random(seed)&15,
                 $random(seed)&1,$random(seed)&((1<<AW)-1),$random(seed)&1,$random(seed)&((1<<AW)-1),
                 $random(seed)&1,$random(seed)&15,(trial%157)!=0);
        repeat (3) step(0,0,0,0,0,0,0,0,0,1);
        $display("PASS tb_storage DEPTH=%0d PIN=%0d POUT=%0d", DEPTH, PIN, POUT);
        $finish;
    end
endmodule
