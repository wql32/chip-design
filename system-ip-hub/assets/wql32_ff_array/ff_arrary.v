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
    parameter ADDR_WIDTH = (ARRAY_DEPTH > 1) ? $clog2(ARRAY_DEPTH) : 1,
    parameter FLOP_IN = 0,
    parameter FLOP_OUT = 1,
    parameter END_OF_LIST = 1
)(
    input i_clk,
    input i_rst_n,
    input i_wen,
    input [ADDR_WIDTH-1:0] i_waddr,
    input [DATA_WIDTH-1:0] i_wdata,
    input i_ren,
    input [ADDR_WIDTH-1:0] i_raddr,
    output reg [DATA_WIDTH-1:0] o_rdata
);
reg [DATA_WIDTH-1:0] ff_array [0:ARRAY_DEPTH-1];
reg wen, ren;
reg [ADDR_WIDTH-1:0] waddr, raddr;
reg [DATA_WIDTH-1:0] wdata, rdata;
integer read_idx;
genvar array_idx;

generate
    if (FLOP_IN == 1) begin : GEN_FLOP_IN
        always @(posedge i_clk) begin
            if (!i_rst_n) begin
                wen <= 0;
                ren <= 0;
                waddr <= 0;
                raddr <= 0;
                wdata <= 0;
            end else begin
                wen <= i_wen;
                ren <= i_ren;
                waddr <= i_waddr;
                raddr <= i_raddr;
                wdata <= i_wdata;
            end
        end
    end else begin : GEN_NON_FLOP_IN
        always @(*) begin
            wen = i_wen;
            ren = i_ren;
            waddr = i_waddr;
            raddr = i_raddr;
            wdata = i_wdata;
        end
    end
    for (array_idx = 0; array_idx < ARRAY_DEPTH; array_idx = array_idx+1) begin : GEN_FF_ARRAY
        always @(posedge i_clk) begin
            if (i_rst_n && wen && waddr == array_idx) ff_array[array_idx] <= wdata;
        end
    end
endgenerate

// Unwritten entries are unspecified; disabled/invalid-address reads return zero.
always @(*) begin
    rdata = {DATA_WIDTH{1'b0}};
    for (read_idx = 0; read_idx < ARRAY_DEPTH; read_idx = read_idx+1)
        if (i_rst_n && ren && raddr == read_idx) rdata = ff_array[read_idx];
end

generate
    if (FLOP_OUT == 1) begin : GEN_FLOP_OUT
        always @(posedge i_clk) begin
            if (!i_rst_n) o_rdata <= 0;
            else if (ren) o_rdata <= rdata;
        end
    end else begin : GEN_NON_FLOP_OUT
        always @(*) o_rdata = rdata;
    end
endgenerate
endmodule
