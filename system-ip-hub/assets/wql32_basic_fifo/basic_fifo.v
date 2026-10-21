module basic_fifo #(
    parameter FIFO_WIDTH = 16,
    parameter FIFO_DEPTH = 8,
    parameter AFULL_DEPTH = 6,
    parameter FIFO_NAME = ""
)(
    input i_we,
    input [FIFO_WIDTH-1:0] i_wdata,
    input i_re,
    output wire [FIFO_WIDTH-1:0] o_rdata,
    output wire o_full,
    output wire o_afull,
    output wire o_empty,
    output wire o_overflow,
    output wire o_underflow,
    input i_clk,
    input i_rst_n
);
localparam ADDR_WIDTH = (FIFO_DEPTH > 1) ? $clog2(FIFO_DEPTH) : 1;
localparam COUNT_WIDTH = (FIFO_DEPTH > 1) ? $clog2(FIFO_DEPTH+1) : 1;
reg [ADDR_WIDTH-1:0] fifo_rptr, fifo_wptr;
reg [COUNT_WIDTH-1:0] fifo_cnt;
reg [FIFO_WIDTH-1:0] reg_mem [0:FIFO_DEPTH-1];
wire read_fire = i_rst_n && i_re && !o_empty;
// A real read frees one slot this cycle. There is no empty read bypass.
wire write_fire = i_rst_n && i_we && (!o_full || read_fire);

function [ADDR_WIDTH-1:0] next_ptr;
    input [ADDR_WIDTH-1:0] ptr;
    begin
        next_ptr = (ptr == FIFO_DEPTH-1) ? {ADDR_WIDTH{1'b0}} : ptr + 1'b1;
    end
endfunction

always @(posedge i_clk) begin
    if (!i_rst_n) begin
        fifo_rptr <= 0;
        fifo_wptr <= 0;
        fifo_cnt <= 0;
    end else begin
        if (read_fire) fifo_rptr <= next_ptr(fifo_rptr);
        if (write_fire) begin
            reg_mem[fifo_wptr] <= i_wdata;
            fifo_wptr <= next_ptr(fifo_wptr);
        end
        case ({write_fire, read_fire})
            2'b10: fifo_cnt <= fifo_cnt + 1'b1;
            2'b01: fifo_cnt <= fifo_cnt - 1'b1;
            default: ;
        endcase
    end
end

assign o_empty = (fifo_cnt == 0);
assign o_full = (fifo_cnt == FIFO_DEPTH);
assign o_afull = (fifo_cnt >= AFULL_DEPTH);
assign o_rdata = (i_rst_n && !o_empty) ? reg_mem[fifo_rptr] : {FIFO_WIDTH{1'b0}};
assign o_overflow = i_rst_n && i_we && !write_fire;
assign o_underflow = i_rst_n && i_re && !read_fire;
endmodule
