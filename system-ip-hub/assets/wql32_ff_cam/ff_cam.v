module ff_cam #(
    parameter DATA_WIDTH = 24,
    parameter ARRAY_DEPTH = 9,
    parameter ADDR_WIDTH = (ARRAY_DEPTH > 1) ? $clog2(ARRAY_DEPTH) : 1,
    parameter FLOP_IN = 0,
    parameter FLOP_OUT = 0,
    parameter END_OF_LIST = 0
)(
    input i_clk,
    input i_rst_n,
    input i_wen,
    input [ADDR_WIDTH-1:0] i_waddr,
    input [DATA_WIDTH-1:0] i_wdata,
    input i_ren,
    input [ADDR_WIDTH-1:0] i_raddr,
    output reg [DATA_WIDTH-1:0] o_rdata,
    input i_cen,
    input [ADDR_WIDTH-1:0] i_caddr,
    input i_sen,
    input [DATA_WIDTH-1:0] i_skey,
    output reg [ADDR_WIDTH-1:0] o_saddr
);
reg [DATA_WIDTH:0] ff_array [0:ARRAY_DEPTH-1];
reg wen, ren, cen, sen;
reg [ADDR_WIDTH-1:0] waddr, raddr, caddr;
reg [DATA_WIDTH-1:0] wdata, skey, rdata;
reg [ADDR_WIDTH-1:0] saddr;
wire [ARRAY_DEPTH-1:0] cmp_bitmap;
integer read_idx, search_idx;
genvar array_idx;

generate
    if (FLOP_IN == 1) begin : GEN_FLOP_IN
        always @(posedge i_clk) begin
            if (!i_rst_n) begin
                wen <= 0; ren <= 0; cen <= 0; sen <= 0;
                waddr <= 0; raddr <= 0; caddr <= 0;
                wdata <= 0; skey <= 0;
            end else begin
                wen <= i_wen; ren <= i_ren; cen <= i_cen; sen <= i_sen;
                waddr <= i_waddr; raddr <= i_raddr; caddr <= i_caddr;
                wdata <= i_wdata; skey <= i_skey;
            end
        end
    end else begin : GEN_NON_FLOP_IN
        always @(*) begin
            wen = i_wen; ren = i_ren; cen = i_cen; sen = i_sen;
            waddr = i_waddr; raddr = i_raddr; caddr = i_caddr;
            wdata = i_wdata; skey = i_skey;
        end
    end
    for (array_idx = 0; array_idx < ARRAY_DEPTH; array_idx = array_idx+1) begin : GEN_FF_ARRAY
        always @(posedge i_clk) begin
            if (!i_rst_n) ff_array[array_idx] <= 0;
            // Preserve the original write-over-clear priority at the same entry.
            else if (wen && waddr == array_idx) ff_array[array_idx] <= {1'b1, wdata};
            else if (cen && caddr == array_idx) ff_array[array_idx] <= 0;
        end
        assign cmp_bitmap[array_idx] = i_rst_n && sen && ff_array[array_idx][DATA_WIDTH]
            && (ff_array[array_idx][DATA_WIDTH-1:0] == skey);
    end
endgenerate

always @(*) begin
    rdata = 0;
    for (read_idx = 0; read_idx < ARRAY_DEPTH; read_idx = read_idx+1)
        if (i_rst_n && ren && raddr == read_idx && ff_array[read_idx][DATA_WIDTH])
            rdata = ff_array[read_idx][DATA_WIDTH-1:0];
end

// Explicit LSB-first priority also defines duplicate-key behavior.
always @(*) begin
    saddr = 0;
    for (search_idx = ARRAY_DEPTH-1; search_idx >= 0; search_idx = search_idx-1)
        if (cmp_bitmap[search_idx]) saddr = search_idx;
end

generate
    if (FLOP_OUT == 1) begin : GEN_FLOP_OUT
        always @(posedge i_clk) begin
            if (!i_rst_n) begin o_rdata <= 0; o_saddr <= 0; end
            else begin
                if (ren) o_rdata <= rdata;
                if (sen) o_saddr <= saddr;
            end
        end
    end else begin : GEN_NON_FLOP_OUT
        always @(*) begin o_rdata = rdata; o_saddr = saddr; end
    end
endgenerate
// Legacy interface has no match-valid output: no hit and address 0 both encode 0.
endmodule
