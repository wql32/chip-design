module mux_oh #(
    parameter DATA_WIDTH = 8,
    parameter PORT_NUM   = 4
)(
    input  wire [DATA_WIDTH*PORT_NUM-1:0] i_data, // data of n ports
    input  wire [PORT_NUM-1:0]            i_sel,  // select
    output wire [DATA_WIDTH-1:0]          o_data  // data of selected port
);

    wire [DATA_WIDTH-1:0] data_2d          [PORT_NUM-1:0];
    wire [PORT_NUM-1:0]   data_2d_trans    [DATA_WIDTH-1:0];

    generate
        // 1. 将输入数据按端口拆分为二维数组，并根据选择信号屏蔽
        for (genvar i = 0; i < PORT_NUM; i = i + 1) begin : GEN_DATA_2D
            assign data_2d[i] = i_data[i*DATA_WIDTH +: DATA_WIDTH] & {DATA_WIDTH{i_sel[i]}};
        end

        // 2. 转置二维数组
        for (genvar i = 0; i < DATA_WIDTH; i = i + 1) begin : GEN_TRANS_X
            for (genvar j = 0; j < PORT_NUM; j = j + 1) begin : Y
                assign data_2d_trans[i][j] = data_2d[j][i];
            end
        end

        // 3. 对转置后的每一位进行 OR 运算，得到输出
        for (genvar i = 0; i < DATA_WIDTH; i = i + 1) begin : GEN_OUT
            assign o_data[i] = |data_2d_trans[i];
        end
    endgenerate

endmodule
