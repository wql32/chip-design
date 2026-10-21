module fifo_2w1r #(
    parameter FIFO_WIDTH = 16,
    parameter FIFO_DEPTH = 8,
    parameter AFULL_DEPTH = 6,
    parameter FIFO_NAME = ""
)(
    input i_we_0,
    input [FIFO_WIDTH-1:0] i_wdata_0,
    input i_we_1,
    input [FIFO_WIDTH-1:0] i_wdata_1,
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
wire [1:0] requested_writes = {1'b0, i_we_0} + {1'b0, i_we_1};
wire read_fire = i_rst_n && i_re && !o_empty;
wire [COUNT_WIDTH:0] available_slots = FIFO_DEPTH - fifo_cnt + read_fire;
// No per-port accept signals exist: accept the complete write group or none.
wire write_fire = i_rst_n && (requested_writes != 0) && (requested_writes <= available_slots);
wire [1:0] accepted_writes = write_fire ? requested_writes : 2'b00;

function [ADDR_WIDTH-1:0] next_ptr;
    input [ADDR_WIDTH-1:0] ptr;
    begin
        next_ptr = (ptr == FIFO_DEPTH-1) ? {ADDR_WIDTH{1'b0}} : ptr + 1'b1;
    end
endfunction
wire [ADDR_WIDTH-1:0] fifo_wptr_plus1 = next_ptr(fifo_wptr);

always @(posedge i_clk) begin
    if (!i_rst_n) begin
        fifo_rptr <= 0;
        fifo_wptr <= 0;
        fifo_cnt <= 0;
    end else begin
        if (read_fire) fifo_rptr <= next_ptr(fifo_rptr);
        if (write_fire) begin
            reg_mem[fifo_wptr] <= i_we_0 ? i_wdata_0 : i_wdata_1;
            if (requested_writes == 2) reg_mem[fifo_wptr_plus1] <= i_wdata_1;
            fifo_wptr <= (requested_writes == 2) ? next_ptr(fifo_wptr_plus1) : fifo_wptr_plus1;
        end
        fifo_cnt <= fifo_cnt - read_fire + accepted_writes;
    end
end

assign o_empty = (fifo_cnt == 0);
assign o_full = (fifo_cnt == FIFO_DEPTH);
assign o_afull = (fifo_cnt >= AFULL_DEPTH);
assign o_rdata = (i_rst_n && !o_empty) ? reg_mem[fifo_rptr] : {FIFO_WIDTH{1'b0}};
assign o_overflow = i_rst_n && (requested_writes != 0) && !write_fire;
assign o_underflow = i_rst_n && i_re && !read_fire;
endmodule
