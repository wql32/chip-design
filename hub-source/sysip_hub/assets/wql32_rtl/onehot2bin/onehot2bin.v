module onehot2bin #(
    parameter BITMAP_WIDTH = 253,
    parameter BIN_WIDTH    = (BITMAP_WIDTH > 1) ? $clog2(BITMAP_WIDTH) : 1
)(
    input  wire [BITMAP_WIDTH-1:0] i_bitmap,
    output wire [BIN_WIDTH-1:0]    o_binary
);

// Input contract: one-hot or zero. For each index bit, OR together exactly
// those bitmap positions whose constant index contains that bit. No padding
// or variable part-select is required, including for non-power-of-two widths.
genvar binary_idx;
genvar bitmap_idx;
generate
    for (binary_idx = 0; binary_idx < BIN_WIDTH; binary_idx = binary_idx + 1) begin : GEN_BINARY
        wire [BITMAP_WIDTH-1:0] selected_bitmap;
        for (bitmap_idx = 0; bitmap_idx < BITMAP_WIDTH; bitmap_idx = bitmap_idx + 1) begin : GEN_BITMAP
            assign selected_bitmap[bitmap_idx] = ((bitmap_idx >> binary_idx) & 1)
                ? i_bitmap[bitmap_idx] : 1'b0;
        end
        assign o_binary[binary_idx] = |selected_bitmap;
    end
endgenerate

endmodule
