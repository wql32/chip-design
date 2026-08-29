// Two-entry ready/valid skid buffer.
// s_ready depends only on registered occupancy and therefore has no
// combinational path from m_ready.
module wql32_axi_skid_buffer #(
    parameter integer DATA_WIDTH = 64,
    parameter integer AR         = 0  // 1: asynchronous active-low reset
)(
    input  wire                  clk,
    input  wire                  reset_n,
    input  wire                  s_valid,
    output wire                  s_ready,
    input  wire [DATA_WIDTH-1:0] s_data,
    output wire                  m_valid,
    input  wire                  m_ready,
    output wire [DATA_WIDTH-1:0] m_data
);

    reg [DATA_WIDTH-1:0] data_mem [0:1];
    reg                  write_ptr_reg;
    reg                  read_ptr_reg;
    reg [1:0]            count_reg;

    wire push = s_valid && s_ready;
    wire pop  = m_valid && m_ready;

    assign s_ready = (count_reg != 2);
    assign m_valid = (count_reg != 0);
    assign m_data  = data_mem[read_ptr_reg];

    generate
        if (AR == 1) begin : g_async_reset
            always @(posedge clk or negedge reset_n) begin
                if (!reset_n) begin
                    data_mem[0]  <= {DATA_WIDTH{1'b0}};
                    data_mem[1]  <= {DATA_WIDTH{1'b0}};
                    write_ptr_reg <= 1'b0;
                    read_ptr_reg  <= 1'b0;
                    count_reg     <= 2'd0;
                end else begin
                    if (push) begin
                        data_mem[write_ptr_reg] <= s_data;
                        write_ptr_reg <= ~write_ptr_reg;
                    end
                    if (pop)
                        read_ptr_reg <= ~read_ptr_reg;
                    case ({push, pop})
                        2'b10: count_reg <= count_reg + 1'b1;
                        2'b01: count_reg <= count_reg - 1'b1;
                        default: count_reg <= count_reg;
                    endcase
                end
            end
        end else begin : g_sync_reset
            always @(posedge clk) begin
                if (!reset_n) begin
                    data_mem[0]  <= {DATA_WIDTH{1'b0}};
                    data_mem[1]  <= {DATA_WIDTH{1'b0}};
                    write_ptr_reg <= 1'b0;
                    read_ptr_reg  <= 1'b0;
                    count_reg     <= 2'd0;
                end else begin
                    if (push) begin
                        data_mem[write_ptr_reg] <= s_data;
                        write_ptr_reg <= ~write_ptr_reg;
                    end
                    if (pop)
                        read_ptr_reg <= ~read_ptr_reg;
                    case ({push, pop})
                        2'b10: count_reg <= count_reg + 1'b1;
                        2'b01: count_reg <= count_reg - 1'b1;
                        default: count_reg <= count_reg;
                    endcase
                end
            end
        end
    endgenerate

endmodule
