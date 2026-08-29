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
    genvar port_idx;
    genvar bit_idx;
    genvar transpose_port_idx;
    genvar out_idx;

    generate
        // 1. 将输入数据按端口拆分为二维数组，并根据选择信号屏蔽
        for (port_idx = 0; port_idx < PORT_NUM; port_idx = port_idx + 1) begin : GEN_DATA_2D
            assign data_2d[port_idx] = i_data[port_idx*DATA_WIDTH +: DATA_WIDTH] & {DATA_WIDTH{i_sel[port_idx]}};
        end

        // 2. 转置二维数组
        for (bit_idx = 0; bit_idx < DATA_WIDTH; bit_idx = bit_idx + 1) begin : GEN_TRANS_X
            for (transpose_port_idx = 0; transpose_port_idx < PORT_NUM; transpose_port_idx = transpose_port_idx + 1) begin : Y
                assign data_2d_trans[bit_idx][transpose_port_idx] = data_2d[transpose_port_idx][bit_idx];
            end
        end

        // 3. 对转置后的每一位进行 OR 运算，得到输出
        for (out_idx = 0; out_idx < DATA_WIDTH; out_idx = out_idx + 1) begin : GEN_OUT
            assign o_data[out_idx] = |data_2d_trans[out_idx];
        end
    endgenerate

endmodule
