module onehot2bin #(
    parameter BITMAP_WIDTH = 253,   // Supported width is not less than 16 and not greater than 512
    parameter BIN_WIDTH    = $clog2(BITMAP_WIDTH)
)(
    input  wire [BITMAP_WIDTH-1:0] i_bitmap,  // bitmap of onehot type
    output wire [BIN_WIDTH-1:0]   o_binary   // convert onehot sequence to binars
);

localparam BITMAP_CEIL_WIDTH = 2**BIN_WIDTH;

wire [BITMAP_CELL_WIDTH-1:0] bitmap_ceil;
wire [BITMAP_CELL_WIDTH/2-1:0] bitmap_seg [BIN_WIDTH-1:0];

assign bitmap_ceil = ({{(BITMAP_CEIL_WIDTH-BITMAP_WIDTH){1'b0}}, i_bitmap});
//BITMAP_WIDTH must be 8b at least
assign bitmap_seg[0] = bitmap_half_1(bitmap_ceil);
assign bitmap_seg[1] = bitmap_half_2(bitmap_ceil);

generate
    if(BITMAP_CEIL_WIDTH > 4) begin : GEN_BITMAP_WIDTH_8
        assign bitmap_seg[2] = bitmap_half_4(bitmap_ceil);

        function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_4;
            parameter EXTRACT_WIDTH = 4;
            parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;

            input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;

            begin
                for(integer i = 0; i < (BITMAP_CEIL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                    bitmap_half_4[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)-1) : EXTRACT_WIDTH];
                end
            endfunction
        end
    endgenerate

    generate
        if(BITMAP_CELL_WIDTH > 8) begin : GEN_BITMAP_WIDTH_16
            assign bitmap_seg[3] = bitmap_half_8(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_8;
                parameter EXTRACT_WIDTH = 8;
                parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;

                input [BITMAP_CELL_WIDTH-1 : 0] i_bitmap;

                begin
                    for(integer i = 0; i < (BITMAP_CEIL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_8[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                endfunction
            end
        endgenerate

        if(BITMAP_CELL_WIDTH > 16) begin : GEN_BITMAP_WIDTH_32
            assign bitmap_seg[4] = bitmap_half_16(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_16;
                parameter EXTRACT_WIDTH = 16;
                parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;

                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;

                begin
                    for(integer i = 0; i < (BITMAP_CEIL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_16[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                endfunction
            end
        endgenerate

        if(BITMAP_CEIL_WIDTH > 32) begin : GEN_BITMAP_WIDTH_64
            assign bitmap_seg[5] = bitmap_half_32(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_32;
                parameter EXTRACT_WIDTH = 32;
                parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;

                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;

                begin
                    for(integer i = 0; i < (BITMAP_CEIL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_32[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                endfunction
            end
        endgenerate

        if(BITMAP_CEIL_WIDTH > 64) begin : GEN_BITMAP_WIDTH_128
            assign bitmap_seg[6] = bitmap_half_64(bitmap_ceil);

            function [BITMAP_CEIL_WIDTH/2-1 : 0] bitmap_half_64;
                parameter EXTRACT_WIDTH = 64;
                parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;

                input [BITMAP_CEIL_WIDTH-1 : 0] i_bitmap;

                begin
                    for(integer i = 0; i < (BITMAP_CEIL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_64[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                endfunction
            end
        endgenerate

        if(BITMAP_CELL_WIDTH > 128) begin : GEN_BITMAP_WIDTH_256
            assign bitmap_seg[7] = bitmap_half_128(bitmap_cell);

            function [BITMAP_CELL_WIDTH/2-1 : 0] bitmap_half_128;
                parameter EXTRACT_WIDTH = 128;
                parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;

                input [BITMAP_CELL_WIDTH-1 : 0] i_bitmap;

                begin
                    for(integer i = 0; i < (BITMAP_CELL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_128[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                endfunction
            end
        endgenerate

        if(BITMAP_CELL_WIDTH > 256) begin : GEN_BITMAP_WIDTH_512
            assign bitmap_seg[8] = bitmap_half_256(bitmap_cell);

            function [BITMAP_CELL_WIDTH/2-1 : 0] bitmap_half_256;
                parameter EXTRACT_WIDTH = 256;
                parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;

                input [BITMAP_CELL_WIDTH-1 : 0] i_bitmap;

                begin
                    for(integer i = 0; i < (BITMAP_CELL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_256[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                end
                endfunction
            end
        endgenerate

        generate
            for(genvar i = 0; i < BIN_WIDTH; i = i + 1) begin : GEN_0_BINARY
                assign o_binary[i] = |bitmap_seg[i];
            end
        endgenerate

        // Example
        // i_bitmap    : 8'b0000 0001  8'b0001 0000  8'b0100 0000  8'b1000 0000
        // o_binary    : 3'b001   3'b100   3'b010   3'b111
        function [BITMAP_CEIL_WIDTH/2-1:0] bimap_half_1;
		      parameter EXTRACT_WIDTH = 1;
          parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;
          input [BITMAP_CELL_WIDTH-1 : 0] i_bitmap;
                begin
                    for(integer i = 0; i < (BITMAP_CELL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_256[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                end
        endfunction
		   function [BITMAP_CEIL_WIDTH/2-1:0] bimap_half_2;
		      parameter EXTRACT_WIDTH = 2;
          parameter STAP_WIDTH    = 2*EXTRACT_WIDTH;
          input [BITMAP_CELL_WIDTH-1 : 0] i_bitmap;
                begin
                    for(integer i = 0; i < (BITMAP_CELL_WIDTH/2)/EXTRACT_WIDTH; i = i + 1) begin : EXTRACT_HALF
                        bitmap_half_256[i*EXTRACT_WIDTH +: EXTRACT_WIDTH] = i_bitmap[(STAP_WIDTH*(i+1)) -: EXTRACT_WIDTH];
                    end
                end
        endfunction        
endmodule
