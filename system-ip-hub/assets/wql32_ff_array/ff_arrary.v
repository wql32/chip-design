/**
 * File     ff_array.v
 * @brief   This is a generic design of a FF based sram.
 *
 * @date    2020.12
 * @license Copyright (c) 2020 by Me, Inc. All rights reserved.
 */

module ff_array #(
    parameter DATA_WIDTH = 24,
    parameter ARRAY_DEPTH = 9,
    parameter ADDR_WIDTH = $clog2(ARRAY_DEPTH),
    parameter FLOP_IN    = 0,
    parameter FLOP_OUT   = 1,
    parameter END_OF_LIST = 1
)(
    input               i_clk,
    input               i_rst_n,
    input               i_wen,
    input  [ADDR_WIDTH-1:0] i_waddr,
    input  [DATA_WIDTH-1:0] i_wdata,
    input               i_ren,
    input  [ADDR_WIDTH-1:0] i_raddr,
    output reg [DATA_WIDTH-1:0] o_rdata
);

    reg  [DATA_WIDTH-1:0] ff_array  [ARRAY_DEPTH-1:0];
    reg                   wen;
    reg  [ADDR_WIDTH-1:0] waddr;
    reg  [DATA_WIDTH-1:0] wdata;
    reg                   ren;
    reg  [ADDR_WIDTH-1:0] raddr;
    reg  [DATA_WIDTH-1:0] rdata;

    wire  [ARRAY_DEPTH-1:0] wen_bitmap;
    wire  [ARRAY_DEPTH-1:0] ren_bitmap;
    integer read_idx;
    genvar array_idx;

    generate
        if(FLOP_IN == 1) begin : GEN_FLOP_IN
            always @(posedge i_clk) begin
                if(!i_rst_n) begin
                    wen <= 1'b0;
                    ren <= 1'b0;
                end
                else begin
                    wen <= i_wen;
                    ren <= i_ren;
                end
            end
        end
        else begin : GEN_NON_FLOP_IN
            always @(*) begin
                wen  = i_wen;
                waddr = i_waddr;
                wdata = i_wdata;
            end

            always @(*) begin
                ren  = i_ren;
                raddr = i_raddr;
            end
        end

        always @(posedge i_clk) begin
            if(i_ren) begin
                raddr <= i_raddr;
            end
            else ;
        end

        always @(*) begin
            ren  = i_ren;
            raddr = i_raddr;
        end
    endgenerate

    assign wen_bitmap = {{(ARRAY_DEPTH-1){1'b0}}, wen} << waddr;
    assign ren_bitmap = {{(ARRAY_DEPTH-1){1'b0}}, ren} << raddr;

    generate
        for(array_idx = 0; array_idx < ARRAY_DEPTH; array_idx = array_idx + 1) begin : GEN_FF_ARRAY
            always @(posedge i_clk) begin
                if(wen_bitmap[array_idx]) begin
                    ff_array[array_idx] <= wdata;
                end
                else ;
            end
        end
    endgenerate

    always @(*) begin
        rdata = {DATA_WIDTH{1'b0}};
        for(read_idx = 0; read_idx < ARRAY_DEPTH; read_idx = read_idx + 1) begin : ROTATE
            rdata = rdata | {DATA_WIDTH{ren_bitmap[read_idx]}} & ff_array[read_idx];
        end
    end

    generate
        if(FLOP_OUT == 1) begin : GEN_FLOP_OUT
            always @(posedge i_clk) begin
                if(ren) begin
                    o_rdata <= rdata;
                end
                else ;
            end
        end
        else begin : GEN_NON_FLOP_OUT
            always @(*) begin
                o_rdata = rdata;
            end
        end
    endgenerate

endmodule
