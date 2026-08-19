module async_fifo #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH      = 16
)(
    input  wire                  wr_clk,
    input  wire                  wr_rst_n,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    output wire                  full,
    input  wire                  rd_clk,
    input  wire                  rd_rst_n,
    input  wire                  rd_en,
    output wire [DATA_WIDTH-1:0] rd_data,
    output wire                  empty
);

    localparam ADDR_WIDTH = $clog2(DEPTH);

    // 双端口存储器
    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    reg  [ADDR_WIDTH:0] wr_ptr, rd_ptr;
    wire [ADDR_WIDTH:0] wr_gray, rd_gray;
    reg  [ADDR_WIDTH:0] wr_gray_sync_0, wr_gray_sync_1;
    reg  [ADDR_WIDTH:0] rd_gray_sync_0, rd_gray_sync_1;
    wire [ADDR_WIDTH:0] wr_gray_sync, rd_gray_sync;

    wire                 fifo_full, fifo_empty;
    wire                 wr_enable, rd_enable;

    // 二进制→格雷码
    assign wr_gray = (wr_ptr >> 1) ^ wr_ptr;
    assign rd_gray = (rd_ptr >> 1) ^ rd_ptr;

    // 写时钟域同步读指针格雷码
    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            rd_gray_sync_0 <= 0;
            rd_gray_sync_1 <= 0;
        end else begin
            rd_gray_sync_0 <= rd_gray;
            rd_gray_sync_1 <= rd_gray_sync_0;
        end
    end
    assign rd_gray_sync = rd_gray_sync_1;

    // 读时钟域同步写指针格雷码
    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            wr_gray_sync_0 <= 0;
            wr_gray_sync_1 <= 0;
        end else begin
            wr_gray_sync_0 <= wr_gray;
            wr_gray_sync_1 <= wr_gray_sync_0;
        end
    end
    assign wr_gray_sync = wr_gray_sync_1;

    // 满标志（写时钟域）
    assign fifo_full = (wr_gray[ADDR_WIDTH:ADDR_WIDTH-1] != rd_gray_sync[ADDR_WIDTH:ADDR_WIDTH-1]) &&
                       (wr_gray[ADDR_WIDTH-2:0] == rd_gray_sync[ADDR_WIDTH-2:0]);

    // 空标志（读时钟域）
    assign fifo_empty = (rd_gray == wr_gray_sync);

    assign wr_enable = wr_en && !fifo_full;
    assign rd_enable = rd_en && !fifo_empty;

    // 写操作
    always @(posedge wr_clk) begin
        if (wr_enable)
            mem[wr_ptr[ADDR_WIDTH-1:0]] <= wr_data;
    end

    // 写指针
    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) wr_ptr <= 0;
        else if (wr_enable) wr_ptr <= wr_ptr + 1'b1;
    end

    // 读指针
    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) rd_ptr <= 0;
        else if (rd_enable) rd_ptr <= rd_ptr + 1'b1;
    end

    assign full    = fifo_full;
    assign empty   = fifo_empty;
    assign rd_data = mem[rd_ptr[ADDR_WIDTH-1:0]];

endmodule