module axis_fifo #(
    parameter DATA_WIDTH = 64,
    parameter DEPTH      = 32,
    parameter AFULL_TH   = DEPTH - 2
)(
    input  wire                     i_clk,
    input  wire                     i_rst_n,

    // ========== AXI4-Stream 写侧（Slave 接口） ==========
    input  wire                     s_axis_tvalid,  // 上游数据有效
    output wire                     s_axis_tready,  // FIFO 可接收（反压信号）
    input  wire [DATA_WIDTH-1:0]    s_axis_tdata,    // 数据总线
    input  wire [DATA_WIDTH/8-1:0]  s_axis_tkeep,    // 字节使能掩码
    input  wire                     s_axis_tlast,    // 包结束标志

    // ========== AXI4-Stream 读侧（Master 接口） ==========
    output wire                     m_axis_tvalid,   // 下游数据有效
    input  wire                     m_axis_tready,   // 下游就绪（背压输入）
    output wire [DATA_WIDTH-1:0]    m_axis_tdata,    // 数据总线
    output wire [DATA_WIDTH/8-1:0]  m_axis_tkeep,    // 字节使能掩码
    output wire                     m_axis_tlast,    // 包结束标志

    // ========== 状态信号 ==========
    output wire                     o_full,
    output wire                     o_almost_full,
    output wire                     o_empty,
    output wire                     o_almost_empty
);

    localparam ADDR_WIDTH = $clog2(DEPTH);
    localparam KEEP_WIDTH = DATA_WIDTH / 8;

    reg [DATA_WIDTH + KEEP_WIDTH + 1 - 1 : 0] mem [0:DEPTH-1];
    wire [DATA_WIDTH + KEEP_WIDTH + 1 - 1 : 0] mem_din;
    wire [DATA_WIDTH + KEEP_WIDTH + 1 - 1 : 0] mem_dout;

    reg [ADDR_WIDTH:0] wr_ptr, rd_ptr;
    wire [ADDR_WIDTH:0] wr_ptr_next, rd_ptr_next;
    wire [ADDR_WIDTH-1:0] wr_addr, rd_addr;
    wire mem_wr_en, mem_rd_en;
    wire [ADDR_WIDTH:0] fifo_cnt;

    assign wr_ptr_next = wr_ptr + {{ADDR_WIDTH{1'b0}}, 1'b1};
    assign rd_ptr_next = rd_ptr + {{ADDR_WIDTH{1'b0}}, 1'b1};
    assign wr_addr = wr_ptr[ADDR_WIDTH-1:0];
    assign rd_addr = rd_ptr[ADDR_WIDTH-1:0];

    assign mem_wr_en = s_axis_tvalid && s_axis_tready;
    assign mem_rd_en = (fifo_cnt != 0) && m_axis_tready;

    assign mem_din = {s_axis_tlast, s_axis_tkeep, s_axis_tdata};

    always @(posedge i_clk) begin
        if (mem_wr_en) mem[wr_addr] <= mem_din;
    end

    always @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) rd_ptr <= 0;
        else if (mem_rd_en) rd_ptr <= rd_ptr_next;
    end

    always @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) wr_ptr <= 0;
        else if (mem_wr_en) wr_ptr <= wr_ptr_next;
    end

    assign fifo_cnt = wr_ptr - rd_ptr;

    assign o_full        = (fifo_cnt == DEPTH);
    assign o_almost_full = (fifo_cnt >= AFULL_TH);
    assign o_empty       = (fifo_cnt == 0);
    assign o_almost_empty= (fifo_cnt <= 2);

    assign s_axis_tready = !o_full;
    assign m_axis_tvalid = !o_empty;

    assign mem_dout = mem[rd_addr];
    assign m_axis_tdata = mem_dout[0 +: DATA_WIDTH];
    assign m_axis_tkeep = mem_dout[DATA_WIDTH +: KEEP_WIDTH];
    assign m_axis_tlast = mem_dout[DATA_WIDTH + KEEP_WIDTH];

endmodule