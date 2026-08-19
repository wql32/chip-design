module axi_slice #(
    parameter PAYLOAD_WIDTH = 32,
    parameter AR            = 0        // 1: 异步复位, 0: 同步复位
)(
    input  wire                    front_valid,
    input  wire [PAYLOAD_WIDTH-1:0] front_payload,
    output wire                    front_ready,
    input  wire                    end_ready,
    output wire                    end_valid,
    output wire [PAYLOAD_WIDTH-1:0] end_payload,
    input  wire                    iclk,
    input  wire                    iReset_n
);

    // ---- 双缓冲寄存器 ----
    reg [PAYLOAD_WIDTH-1:0] reg_a;
    reg [PAYLOAD_WIDTH-1:0] reg_b;
    reg                     valid_a;
    reg                     valid_b;

    // ---- 乒乓指针 ----
    reg front_step;   // 0→写 reg_a, 1→写 reg_b
    reg end_step;     // 0→读 reg_a, 1→读 reg_b

    wire front_hs;
    wire end_hs;
    wire enable_rega;
    wire enable_regb;

    assign front_hs = front_valid & front_ready;
    assign end_hs   = end_valid   & end_ready;

    // [BUGFIX] ready/valid 基于当前 target 判断，避免误写有效寄存器
    assign front_ready = front_step ? ~valid_b : ~valid_a;
    assign end_valid   = end_step   ?  valid_b :  valid_a;

    assign enable_rega = front_hs & ~front_step;
    assign enable_regb = front_hs &  front_step;

    generate
        if (AR == 1) begin : async_rst
            always @(posedge iclk or negedge iReset_n) begin
                if (!iReset_n) begin
                    front_step <= 1'b0;
                    end_step   <= 1'b0;
                    reg_a      <= {PAYLOAD_WIDTH{1'b0}};
                    reg_b      <= {PAYLOAD_WIDTH{1'b0}};
                    valid_a    <= 1'b0;
                    valid_b    <= 1'b0;
                end else begin
                    // 写指针轮转
                    if (front_hs) front_step <= ~front_step;
                    // 读指针轮转
                    if (end_hs)   end_step   <= ~end_step;
                    // 数据写入
                    if (enable_rega) reg_a <= front_payload;
                    if (enable_regb) reg_b <= front_payload;
                    // valid 管理
                    if (enable_rega)      valid_a <= 1'b1;
                    else if (end_hs & ~end_step) valid_a <= 1'b0;
                    if (enable_regb)      valid_b <= 1'b1;
                    else if (end_hs &  end_step) valid_b <= 1'b0;
                end
            end
        end else begin : sync_rst
            always @(posedge iclk) begin
                if (!iReset_n) begin
                    front_step <= 1'b0;
                    end_step   <= 1'b0;
                    reg_a      <= {PAYLOAD_WIDTH{1'b0}};
                    reg_b      <= {PAYLOAD_WIDTH{1'b0}};
                    valid_a    <= 1'b0;
                    valid_b    <= 1'b0;
                end else begin
                    if (front_hs) front_step <= ~front_step;
                    if (end_hs)   end_step   <= ~end_step;
                    if (enable_rega) reg_a <= front_payload;
                    if (enable_regb) reg_b <= front_payload;
                    if (enable_rega)      valid_a <= 1'b1;
                    else if (end_hs & ~end_step) valid_a <= 1'b0;
                    if (enable_regb)      valid_b <= 1'b1;
                    else if (end_hs &  end_step) valid_b <= 1'b0;
                end
            end
        end
    endgenerate

    // ---- 输出数据选择 ----
    assign end_payload = end_step ? reg_b : reg_a;

endmodule