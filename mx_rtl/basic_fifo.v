
module basic_fifo
#(
parameter FIFO_WIDTH = 16        ,
parameter FIFO_DEPTH = 8         ,
parameter AFULL_DEPTH = 6        ,
parameter FIFO_NAME  = ""        // For error log print purpose
)
(
input              i_we        ,
input  [FIFO_WIDTH-1:0] i_wdata   ,
input              i_re          ,
output wire [FIFO_WIDTH-1:0] o_rdata      ,
output wire        o_full        ,
output wire        o_afull       ,//almost full
output wire        o_empty       ,
output wire        o_overflow    ,
output wire        o_underflow   ,
input              i_clk         ,
input              i_rst_n
);

//=====================================================================
// PARAMETERS
//=====================================================================

localparam ADDR_WIDTH = $clog2(FIFO_DEPTH);

//=====================================================================
// INTERNAL SIGNALS
//=====================================================================

reg  [ADDR_WIDTH-1:0] fifo_rptr;
reg  [ADDR_WIDTH-1:0] fifo_wptr;
reg  [ADDR_WIDTH-1:0] fifo_wptr_plus1;
reg  [FIFO_WIDTH-1:0] reg_mem [FIFO_DEPTH-1:0];
reg  [ADDR_WIDTH:0]   fifo_cnt;
wire                  fifo_cnt_upd;
wire [2:0]            fifo_cnt_delta;

always @(posedge i_clk) begin
  if(!i_rst_n) begin
    fifo_rptr <= {ADDR_WIDTH{1'b0}};
  end
  else if(i_re) begin
    fifo_rptr <= fifo_rptr + 1'b1;
  end
  else ;
end

always @(posedge i_clk) begin
  if(!i_rst_n) begin
    fifo_wptr <= {ADDR_WIDTH{1'b0}};
  end
  else if (i_we && fifo_wptr == FIFO_DEPTH-1)begin
	  fifo_wptr <= {ADDR_WIDTH{1'b0}};
  end
  else if (i_we)begin
	  fifp_wptr <= fifo_wptr + 1'b1;
  end
  else ;
end


always @(posedge i_clk) begin
  if (i_we)begin
	  reg_mem[fifo_wptr] <= i_wdata;
  end
  else ;
end

assign fifo_cnt_upd = i_we || i_re;
assign fifo_cnt_delta = (1'b0, i_we) - (1'b0, i_re);

always @(posedge i_clk) begin
  if(!i_rst_n) begin
    fifo_cnt <= {ADDR_WIDTH{1'b0}};
  end
  else if(fifo_cnt_upd) begin
    fifo_cnt <= fifo_cnt + {{(ADDR_WIDTH+1-1){fifo_cnt_delta[1]}}, {fifo_cnt_delta[0]}};
  end
  else ;
end

assign o_rdata = reg_mem[fifo_rptr];

assign o_empty = fifo_cnt == {(ADDR_WIDTH+1){1'b0}};
assign o_full = fifo_cnt >= FIFO_DEPTH;
assign o_afull = fifo_cnt >= AFULL_DEPTH;

assign o_overflow  = i_we && o_full;
assign o_underflow = i_re && o_empty;

endmodule 
