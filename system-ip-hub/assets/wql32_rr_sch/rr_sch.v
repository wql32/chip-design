module rr_sch
#(
parameter       REQ_NUM     = 64
)
(
input  wire                i_clk      ,
input  wire                i_rst_n    ,
input  wire                i_sch_en   ,//Accept one selected request this cycle; 0 pauses service
input  wire [REQ_NUM-1:0]  i_req      ,//Requests to be scheduled
output wire [REQ_NUM-1:0]  o_gnt_vld  ,//Legacy vector: bit 0 is valid, remaining bits are 0
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
wire                        grant_valid;
genvar                       mask_idx;

assign req = i_req ;
assign masked_req = req & mask_last;

//Mask used to keep MSB than first 1.
assign mask_0[0] = 1'b0;
assign mask_1[0] = 1'b0;

generate
for(mask_idx = 1; mask_idx < REQ_NUM; mask_idx = mask_idx + 1) begin : GEN_MASK
assign mask_0[mask_idx] = |req[mask_idx-1:0];
assign mask_1[mask_idx] = |masked_req[mask_idx-1:0];
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
  else if((|masked_req) && grant_valid) begin
    mask_last <= mask_1;
  end
  else if(grant_valid) begin
    mask_last <= mask_0;
  end
  else ;
end

//Output
assign grant_valid = i_rst_n && i_sch_en && (|req);
assign o_gnt_vld = {{(REQ_NUM-1){1'b0}}, grant_valid};
assign o_gnt = grant_valid ? ((|masked_req) ? masked_req_oh : req_oh) : {REQ_NUM{1'b0}};

endmodule
