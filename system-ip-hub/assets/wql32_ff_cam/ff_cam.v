module ff_cam #(
    parameter DATA_WIDTH  = 24,
    parameter ARRAY_DEPTH = 9,
    parameter ADDR_WIDTH  = $clog2(ARRAY_DEPTH),
    parameter FLOP_IN     = 0,
    parameter FLOP_OUT    = 0,
    parameter END_OF_LIST = 0
)(
    input  i_clk,
    input  i_rst_n,

    input                    i_wen,
    input  [ADDR_WIDTH-1:0]  i_waddr,
    input  [DATA_WIDTH-1:0]  i_wdata,

    input                    i_ren,
    input  [ADDR_WIDTH-1:0]  i_raddr,
    output reg [DATA_WIDTH-1:0] o_rdata,

    input                    i_cen,
    input  [ADDR_WIDTH-1:0]  i_caddr,

    input                    i_sen,
    input  [DATA_WIDTH-1:0]  i_skey,
    output reg [ADDR_WIDTH-1:0] o_saddr
);

// 寄存器数组，每个元素包含 {valid, data}
reg [DATA_WIDTH:0] ff_array [0:ARRAY_DEPTH-1];

// 内部信号
reg wen, ren, cen, sen;
reg [ADDR_WIDTH-1:0] waddr, raddr, caddr;
reg [DATA_WIDTH-1:0] wdata, rdata, skey;

wire [ARRAY_DEPTH-1:0] wen_bitmap;
wire [ARRAY_DEPTH-1:0] ren_bitmap;
wire [ARRAY_DEPTH-1:0] cen_bitmap;
wire [ARRAY_DEPTH-1:0] cmp_bitmap;
wire [ADDR_WIDTH-1:0]  saddr;

// 输入寄存器控制
generate
if (FLOP_IN == 1) begin : GEN_FLOP_IN
    always @(posedge i_clk) begin
        if (!i_rst_n) begin
            wen <= 1'b0;
            ren <= 1'b0;
            cen <= 1'b0;
            sen <= 1'b0;
        end else begin
            wen <= i_wen;
            ren <= i_ren;
            cen <= i_cen;
            sen <= i_sen;
        end
    end

    always @(posedge i_clk) begin
        if (i_wen) begin
            waddr <= i_waddr;
            wdata <= i_wdata;
        end
    end

    always @(posedge i_clk) begin
        if (i_ren) begin
            raddr <= i_raddr;
        end
    end

    always @(posedge i_clk) begin
        if (i_cen) begin
            caddr <= i_caddr;
        end
    end

    always @(posedge i_clk) begin
        if (i_sen) begin
            skey <= i_skey;
        end
    end
end else begin : GEN_NON_FLOP_IN
    always @(*) begin
        wen   = i_wen;
        waddr = i_waddr;
        wdata = i_wdata;
        ren   = i_ren;
        raddr = i_raddr;
        cen   = i_cen;
        caddr = i_caddr;
        sen   = i_sen;
        skey  = i_skey;
    end
end
endgenerate

// 位图控制信号
assign wen_bitmap = ren ? ({{(ARRAY_DEPTH-1){1'b0}}, wen} << waddr) : 0;
assign ren_bitmap = ren ? ({{(ARRAY_DEPTH-1){1'b0}}, 1'b1} << raddr) : 0;
assign cen_bitmap = cen ? ({{(ARRAY_DEPTH-1){1'b0}}, 1'b1} << caddr) : 0;

// 寄存器数组写入/清除逻辑
generate
for (genvar i = 0; i < ARRAY_DEPTH; i = i + 1) begin : GEN_FF_ARRAY
    always @(posedge i_clk) begin
        if (!i_rst_n) begin
            ff_array[i] <= {1'b0, {DATA_WIDTH{1'b0}}};
        end else if (wen_bitmap[i]) begin
            ff_array[i] <= {1'b1, wdata};
        end else if (cen_bitmap[i]) begin
            ff_array[i] <= {1'b0, {DATA_WIDTH{1'b0}}};
        end
    end
end
endgenerate

// 读数据逻辑
always @(*) begin
    integer i;
    rdata = {DATA_WIDTH{1'b0}};
    for (i = 0; i < ARRAY_DEPTH; i = i + 1) begin
        if (ren_bitmap[i])
            rdata = ff_array[i][0 +: DATA_WIDTH];
    end
end

// 输出寄存器控制
generate
if (FLOP_OUT == 1) begin : GEN_FLOP_OUT
    always @(posedge i_clk) begin
        if (ren)
            o_rdata <= rdata;
    end

    always @(posedge i_clk) begin
        if (sen)
            o_saddr <= saddr;
    end
end else begin : GEN_NON_FLOP_OUT
    always @(*) begin
        o_rdata = rdata;
        if (sen)
            o_saddr = saddr;
    end
end
endgenerate

// 比较逻辑（CAM 功能）
generate
for (genvar i = 0; i < ARRAY_DEPTH; i = i + 1) begin : GEN_CONTENT_CMP
    assign cmp_bitmap[i] = ff_array[i][DATA_WIDTH] && (ff_array[i][0 +: DATA_WIDTH] == skey);
end
endgenerate

// 将匹配结果转换为地址
idh_onehot2bin #(
    .BITMAP_WIDTH(ARRAY_DEPTH)
) u_onehot2bin (
    .i_bitmap(cmp_bitmap),
    .o_bin   (saddr)
);

endmodule
