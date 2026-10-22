`timescale 1ns/1ps
// Self-checking bench distributed with the design asset.
module tb_encoder;
    parameter WIDTH = 253;
    localparam BITS = (WIDTH > 1) ? $clog2(WIDTH) : 1;
    reg [WIDTH-1:0] bitmap;
    wire [BITS-1:0] binary;
    wire [WIDTH-1:0] first_one;
    wire [BITS-1:0] first_index;
    integer idx, vector_idx, scan_idx, expected_index, seed;
    reg [WIDTH-1:0] expected_one;

    onehot2bin #(.BITMAP_WIDTH(WIDTH)) dut (.i_bitmap(bitmap), .o_binary(binary));
    generate
        if (WIDTH > 1) begin : GEN_FIRST
            find_1st_one #(.BITMAP_WIDTH(WIDTH)) first_dut (
                .i_bitmap(bitmap), .o_onehot(first_one), .o_binary(first_index)
            );
        end
    endgenerate

    task check_first;
        begin
            expected_one = 0;
            expected_index = 0;
            for (scan_idx = WIDTH-1; scan_idx >= 0; scan_idx = scan_idx-1) begin
                if (bitmap[scan_idx]) begin
                    expected_one = 0;
                    expected_one[scan_idx] = 1;
                    expected_index = scan_idx;
                end
            end
            if (WIDTH > 1 && (first_one !== expected_one || first_index !== expected_index[BITS-1:0]))
                $fatal(1, "find_1st_one mismatch WIDTH=%0d bitmap=%h", WIDTH, bitmap);
        end
    endtask

    initial begin
        seed = 32'h20261021;
        bitmap = 0;
        #1;
        if (binary !== {BITS{1'b0}}) $fatal(1, "Zero input mismatch");
        check_first();
        for (idx = 0; idx < WIDTH; idx = idx+1) begin
            bitmap = 0;
            bitmap[idx] = 1;
            #1;
            if (binary !== idx[BITS-1:0]) $fatal(1, "onehot2bin WIDTH=%0d bit=%0d got=%h", WIDTH, idx, binary);
            check_first();
        end
        // Multi-hot is only checked against the priority encoder. It is outside
        // onehot2bin's input contract and must not be treated as priority encode.
        for (vector_idx = 0; vector_idx < ((WIDTH <= 9) ? (1 << WIDTH) : 500); vector_idx = vector_idx+1) begin
            if (WIDTH <= 9) bitmap = vector_idx;
            else for (idx = 0; idx < WIDTH; idx = idx+1) bitmap[idx] = $random(seed);
            #1;
            check_first();
        end
        $display("PASS tb_encoder WIDTH=%0d", WIDTH);
        $finish;
    end
endmodule
