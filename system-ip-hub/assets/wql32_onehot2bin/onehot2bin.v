module onehot2bin #(
    parameter BITMAP_WIDTH = 253,   // Supported width is not less than 16 and not greater than 512
    parameter BIN_WIDTH    = $clog2(BITMAP_WIDTH)
)(
    input  wire [BITMAP_WIDTH-1:0] i_bitmap,  // bitmap of onehot type
    output wire [BIN_WIDTH-1:0]   o_binary   // convert onehot sequence to binars
);

localparam BITMAP_CEIL_WIDTH = 2**BIN_WIDTH;

wire [BITMAP_CEIL_WIDTH-1:0] bitmap_ceil;
wire [BITMAP_CEIL_WIDTH/2-1:0] bitmap_seg [BIN_WIDTH-1:0];
genvar binary_idx;

assign bitmap_ceil = ({{(BITMAP_CEIL_WIDTH-BITMAP_WIDTH){1'b0}}, i_bitmap});
//BITMAP_WIDTH must be 8b at least
assign bitmap_seg[0] = bitmap_half_1(bitmap_ceil);
assign bitmap_seg[1] = bitmap_half_2(bitmap_ceil);

generate
    if(BITMAP_CEIL_WIDTH > 4) begin : GEN_BITMAP_WIDTH_8
        assign bitmap_seg[2] = bitmap_half_4(bitmap_ceil);

        function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_4;
            input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
            integer idx;
            begin
                for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/4; idx = idx + 1) begin : EXTRACT_HALF
                    bitmap_half_4[idx*4 +: 4] = i_bitmap[(8*(idx+1)-1) -: 4];
                end
            end
            endfunction
        end
    endgenerate

    generate
        if(BITMAP_CEIL_WIDTH > 8) begin : GEN_BITMAP_WIDTH_16
            assign bitmap_seg[3] = bitmap_half_8(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_8;
                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
                integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/8; idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_8[idx*8 +: 8] = i_bitmap[(16*(idx+1)) -: 8];
                    end
                end
                endfunction
            end
        endgenerate

        generate
        if(BITMAP_CEIL_WIDTH > 16) begin : GEN_BITMAP_WIDTH_32
            assign bitmap_seg[4] = bitmap_half_16(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_16;
                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
                integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/16; idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_16[idx*16 +: 16] = i_bitmap[(32*(idx+1)) -: 16];
                    end
                end
                endfunction
            end
        endgenerate

        generate
        if(BITMAP_CEIL_WIDTH > 32) begin : GEN_BITMAP_WIDTH_64
            assign bitmap_seg[5] = bitmap_half_32(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_32;
                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
                integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/32; idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_32[idx*32 +: 32] = i_bitmap[(64*(idx+1)) -: 32];
                    end
                end
                endfunction
            end
        endgenerate

        generate
        if(BITMAP_CEIL_WIDTH > 64) begin : GEN_BITMAP_WIDTH_128
            assign bitmap_seg[6] = bitmap_half_64(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_64;
                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
                integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/64; idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_64[idx*64 +: 64] = i_bitmap[(128*(idx+1)) -: 64];
                    end
                end
                endfunction
            end
        endgenerate

        generate
        if(BITMAP_CEIL_WIDTH > 128) begin : GEN_BITMAP_WIDTH_256
            assign bitmap_seg[7] = bitmap_half_128(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_128;
                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
                integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/128; idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_128[idx*128 +: 128] = i_bitmap[(256*(idx+1)) -: 128];
                    end
                end
                endfunction
            end
        endgenerate

        generate
        if(BITMAP_CEIL_WIDTH > 256) begin : GEN_BITMAP_WIDTH_512
            assign bitmap_seg[8] = bitmap_half_256(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_256;
                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
                integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/256; idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_256[idx*256 +: 256] = i_bitmap[(512*(idx+1)) -: 256];
                    end
                end
                endfunction
            end
        endgenerate

        generate
            for(binary_idx = 0; binary_idx < BIN_WIDTH; binary_idx = binary_idx + 1) begin : GEN_0_BINARY
                assign o_binary[binary_idx] = |bitmap_seg[binary_idx];
            end
        endgenerate

        // Example
        // i_bitmap    : 8'b0000 0001  8'b0001 0000  8'b0100 0000  8'b1000 0000
        // o_binary    : 3'b001   3'b100   3'b010   3'b111
        function [BITMAP_CEIL_WIDTH/2-1:0] bitmap_half_1;
          input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
          integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2); idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_1[idx] = i_bitmap[(2*(idx+1)) -: 1];
                    end
                end
        endfunction
		   function [BITMAP_CEIL_WIDTH/2-1:0] bitmap_half_2;
          input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;
          integer idx;
                begin
                    for(idx = 0; idx < (BITMAP_CEIL_WIDTH/2)/2; idx = idx + 1) begin : EXTRACT_HALF
                        bitmap_half_2[idx*2 +: 2] = i_bitmap[(4*(idx+1)) -: 2];
                    end
                end
        endfunction        
endmodule
