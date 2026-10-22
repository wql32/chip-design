module sync_fifo #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH      = 16,
    parameter AFULL_TH   = DEPTH - 2,
    parameter AEMPTY_TH  = 2
)(
    input  wire                  i_clk,
    input  wire                  i_rst_n,
    input  wire                  i_wr_en,
    input  wire [DATA_WIDTH-1:0] i_wr_data,
    output wire                  o_full,
    output wire                  o_almost_full,
    input  wire                  i_rd_en,
    output wire [DATA_WIDTH-1:0] o_rd_data,
    output wire                  o_empty,
    output wire                  o_almost_empty
);

    localparam ADDR_WIDTH = $clog2(DEPTH);

    reg  [DATA_WIDTH-1:0]         mem [0:DEPTH-1];
    reg  [ADDR_WIDTH:0]           wr_ptr, rd_ptr;
    wire [ADDR_WIDTH:0]           wr_ptr_next, rd_ptr_next;
    wire                          fifo_full, fifo_empty;
    wire [ADDR_WIDTH:0]           fifo_cnt;

    assign wr_ptr_next = wr_ptr + 1'b1;
    assign rd_ptr_next = rd_ptr + 1'b1;

    // 写操作
    always @(posedge i_clk) begin
        if (i_wr_en && !fifo_full)
            mem[wr_ptr[ADDR_WIDTH-1:0]] <= i_wr_data;
    end

    // 写指针
    always @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) wr_ptr <= 0;
        else if (i_wr_en && !fifo_full) wr_ptr <= wr_ptr_next;
    end

    // 读指针
    always @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) rd_ptr <= 0;
        else if (i_rd_en && !fifo_empty) rd_ptr <= rd_ptr_next;
    end

    assign fifo_cnt   = wr_ptr - rd_ptr;
    assign fifo_full  = (wr_ptr[ADDR_WIDTH] != rd_ptr[ADDR_WIDTH]) &&
                        (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]);
    assign fifo_empty = (wr_ptr == rd_ptr);

    assign o_full        = fifo_full;
    assign o_almost_full = (fifo_cnt >= AFULL_TH);
    assign o_empty       = fifo_empty;
    assign o_almost_empty= (fifo_cnt <= AEMPTY_TH);
    assign o_rd_data     = mem[rd_ptr[ADDR_WIDTH-1:0]];

endmodule