
module 2wlr_fifo
#(
parameter FIFO_WIDTH = 16        ,
parameter FIFO_DEPTH = 8         ,
parameter AFULL_DEPTH = 6        ,
parameter FIFO_NAME  = ""        // For error log print purpose
)
(
input              i_we_0        ,
input  [FIFO_WIDTH-1:0] i_wdata_0   ,
input              i_we_1        ,
input  [FIFO_WIDTH-1:0] i_wdata_1   ,
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
  else begin
    case({i_we_1, i_we_0})
    2'b01, 2'b10: begin
      fifo_wptr <= fifo_wptr + 2'h1;
    end
    2'b11: begin
      fifo_wptr <= fifo_wptr + 2'h2;
    end
    default: ;
    endcase
  end
end

always @(posedge i_clk) begin
  if(!i_rst_n) begin
    fifo_wptr_plus1 <= {{(ADDR_WIDTH-1){1'b0}}, 1'b1};
  end
  else begin
    case({i_we_1, i_we_0})
    2'b01, 2'b10: begin
      fifo_wptr_plus1 <= fifo_wptr_plus1 + 2'h1;
    end
    2'b11: begin
      fifo_wptr_plus1 <= fifo_wptr_plus1 + 2'h2;
    end
    default: ;
    endcase
  end
end

always @(posedge i_clk) begin
  case({i_we_1, i_we_0})
  2'b01: begin
    reg_mem[fifo_wptr] <= i_wdata_0;
  end
  2'b10: begin
    reg_mem[fifo_wptr] <= i_wdata_1;
  end
  2'b11: begin
    reg_mem[fifo_wptr] <= i_wdata_0;
    reg_mem[fifo_wptr_plus1] <= i_wdata_1;
  end
  default: ;
  endcase
end

assign fifo_cnt_upd = i_we_1 || i_we_0 || i_re;
assign fifo_cnt_delta = (2'b0, i_we_1) + (2'b0, i_we_0) - (2'b0, i_re);

always @(posedge i_clk) begin
  if(!i_rst_n) begin
    fifo_cnt <= {ADDR_WIDTH{1'b0}};
  end
  else if(fifo_cnt_upd) begin
    fifo_cnt <= fifo_cnt + {{(ADDR_WIDTH+1-2){fifo_cnt_delta[2]}}, {fifo_cnt_delta[1:0]}};
  end
  else ;
end

assign o_rdata = reg_mem[fifo_rptr];

assign o_empty = fifo_cnt == {(ADDR_WIDTH+1){1'b0}};
assign o_full = fifo_cnt >= FIFO_DEPTH;
assign o_afull = fifo_cnt >= AFULL_DEPTH;

assign o_overflow = (i_we_0 || i_we_1) && o_full;
assign o_underflow = i_re && o_empty;

endmodule 
