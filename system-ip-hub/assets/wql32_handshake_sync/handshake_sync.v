module handshake_sync #(
    parameter DATA_WIDTH = 16
)(
    input  wire                  src_clk,
    input  wire                  src_rst_n,
    input  wire                  src_vld,
    input  wire [DATA_WIDTH-1:0] src_data,
    output wire                  src_ready,

    input  wire                  dst_clk,
    input  wire                  dst_rst_n,
    output wire                  dst_vld,
    output wire [DATA_WIDTH-1:0] dst_data
);

    reg                         req;
    reg  [DATA_WIDTH-1:0]       data_reg;
    wire                        ack_sync;

    always @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            req      <= 1'b0;
            data_reg <= 0;
        end else if (src_vld && !req) begin
            data_reg <= src_data;
            req      <= 1'b1;
        end else if (ack_sync) begin
            req      <= 1'b0;
        end
    end

    assign src_ready = !req;

    reg  req_sync_0, req_sync_1;
    always @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            req_sync_0 <= 1'b0;
            req_sync_1 <= 1'b0;
        end else begin
            req_sync_0 <= req;
            req_sync_1 <= req_sync_0;
        end
    end
    wire req_pulse = req_sync_1 && !req_sync_0;

    reg                         ack;
    reg  [DATA_WIDTH-1:0]       dst_data_reg;

    always @(posedge dst_clk or negedge dst_rst_n) begin
        if (!dst_rst_n) begin
            ack          <= 1'b0;
            dst_data_reg <= 0;
        end else if (req_pulse) begin
            dst_data_reg <= data_reg;
            ack          <= 1'b1;
        end else if (!req_sync_1) begin
            ack          <= 1'b0;
        end
    end

    assign dst_vld  = req_pulse;
    assign dst_data = dst_data_reg;

    reg  ack_sync_0, ack_sync_1;
    always @(posedge src_clk or negedge src_rst_n) begin
        if (!src_rst_n) begin
            ack_sync_0 <= 1'b0;
            ack_sync_1 <= 1'b0;
        end else begin
            ack_sync_0 <= ack;
            ack_sync_1 <= ack_sync_0;
        end
    end
    assign ack_sync = ack_sync_1;

endmodule