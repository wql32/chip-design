module rr_sch
#(
parameter       REQ_NUM     = 64
)
(
input  wire                i_clk      ,
input  wire                i_rst_n    ,
input  wire                i_sch_en   ,//When sch_en is disabled, scheduler is paused
input  wire [REQ_NUM-1:0]  i_req      ,//Requests to be scheduled
output wire [REQ_NUM-1:0]  o_gnt_vld  ,//output wire granted
output wire [REQ_NUM-1:0]  o_gnt      //Granted request in one-hot style
);

wire [REQ_NUM-1:0]          req_oh     ;//masked request
wire [REQ_NUM-1:0]          req        ;//one-hot type of original request
wire [REQ_NUM-1:0]          masked_req ;//masked request
wire [REQ_NUM-1:0]          masked_req_oh ;//one-hot request of masked request
wire [REQ_NUM-1:0]          mask_0     ;//Cascaded mask of original request
wire [REQ_NUM-1:0]          mask_1     ;//Cascaded mask of masked request
wire [REQ_NUM-1:0]          unmask_0   ;//Inverted mask
wire [REQ_NUM-1:0]          unmask_1   ;//Inverted mask
reg  [REQ_NUM-1:0]          mask_last  ;//mask from last grant

assign req = i_req ;
assign masked_req = req & mask_last;

//Mask used to keep MSB than first 1.
assign mask_0[0] = 1'b0;
assign mask_1[0] = 1'b0;

for(genvar i = 1; i < REQ_NUM; i = i + 1) begin : GEN_MASK
assign mask_0[i] = |req[i] | mask_0[i - 1];
assign mask_1[i] = |masked_req[i-1:0];
end
endgenerate

assign unmask_0 = ~mask_0;
assign unmask_1 = ~mask_1;

assign req_oh = req & unmask_0; //Find first one and mask all other bits, we get a onehot type req.
assign masked_req_oh = masked_req & unmask_1; //Find first one and mask all other bits, we get a onehot type req.

always @(posedge i_clk) begin
  if(!i_rst_n) begin
    mask_last <= {REQ_NUM{1'b0}};
  end
  else if((masked_req == 1'b1) && (i_sch_en == 1'b1)) begin
    mask_last <= mask_1;
  end
  else if((|req == 1'b1) && (i_sch_en == 1'b1)) begin
    mask_last <= mask_0;
  end
  else ;
end

//Output
assign o_gnt_vld = |req && i_sch_en;
assign o_gnt = (|masked_req == 1'b1) ? masked_req_oh : req_oh;

endmodule
