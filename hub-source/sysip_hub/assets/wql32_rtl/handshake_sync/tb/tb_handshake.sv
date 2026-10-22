`timescale 1ns/1ps
// Self-checking bench distributed with the design asset.
module tb_handshake;
    parameter SRC_HALF = 3;
    parameter DST_HALF = 11;
    parameter DST_PHASE = 0;
    reg src_clk = 0, dst_clk = 0;
    always #(SRC_HALF) src_clk = ~src_clk;
    initial begin
        #(DST_PHASE);
        forever #(DST_HALF) dst_clk = ~dst_clk;
    end
    reg src_reset_n = 0, dst_reset_n = 0, src_valid = 0;
    reg [15:0] src_data = 0;
    wire src_ready, dst_valid;
    wire [15:0] dst_data;
    reg [15:0] expected [0:1023];
    integer sent = 0, received = 0, idx;
    handshake_sync dut (.src_clk(src_clk), .src_rst_n(src_reset_n), .src_vld(src_valid), .src_data(src_data), .src_ready(src_ready),
                        .dst_clk(dst_clk), .dst_rst_n(dst_reset_n), .dst_vld(dst_valid), .dst_data(dst_data));

    always @(posedge src_clk or negedge src_reset_n) begin
        if (!src_reset_n) sent = 0;
        else if (src_valid && src_ready) begin
            expected[sent] = src_data;
            sent = sent+1;
        end
    end
    always @(posedge dst_clk or negedge dst_reset_n) begin
        if (!dst_reset_n) received = 0;
        else if (dst_valid) begin
            if (received >= sent) $fatal(1, "Unexpected/duplicate destination transfer");
            if (dst_data !== expected[received]) $fatal(1, "CDC payload mismatch index=%0d got=%h expected=%h", received, dst_data, expected[received]);
            received = received+1;
        end
    end

    task stream(input integer count, input integer base);
        integer item;
        begin
            @(negedge src_clk);
            src_valid = 1;
            for (item = 0; item < count; item = item+1) begin
                src_data = base + item;
                do @(posedge src_clk); while (!src_ready);
                @(negedge src_clk);
            end
            src_valid = 0;
        end
    endtask

    initial begin
        #37;
        // Reset release is aligned to each domain's falling edge in this bench.
        fork
            begin @(negedge src_clk); src_reset_n = 1; end
            begin @(negedge dst_clk); dst_reset_n = 1; end
        join
        stream(100, 16'h1000);
        wait (sent == received && src_ready);
        // An in-flight transfer may be aborted by coordinated reset.
        stream(1, 16'hdead);
        src_reset_n = 0;
        dst_reset_n = 0;
        #(4*(SRC_HALF+DST_HALF));
        fork
            begin @(negedge src_clk); src_reset_n = 1; end
            begin @(negedge dst_clk); dst_reset_n = 1; end
        join
        stream(100, 16'h2000);
        wait (sent == received && src_ready);
        repeat (10) @(posedge dst_clk);
        if (sent != 100 || received != 100) $fatal(1, "Post-reset transfer count mismatch");
        $display("PASS tb_handshake SRC_HALF=%0d DST_HALF=%0d PHASE=%0d", SRC_HALF, DST_HALF, DST_PHASE);
        $finish;
    end
    initial begin #2000000; $fatal(1, "Handshake timeout/deadlock"); end
endmodule
