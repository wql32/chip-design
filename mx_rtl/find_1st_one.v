module find_1st_one
  #(
    parameter BITMAP_WDITH      = 253 ,
    parameter BIN_WIDTH         = $clog2(BITMAP_WIDHT)
  )
  (
    input  wire  [BITMAP_WIDTH-1:0]  i_bitmap  ,
    output wire  [BITMAP_WIDTH-1:0]  o_onehot  ,
    output wire  [BIN_WIDTH-1:0]     o_binary
  );
  reg [BIN_WIDTH-1:0] one_loc;
  always@(*)begin
    one_loc = {BIN_WIDHT{1'b0}};
    for (integer i = BITMAP_WIDTH -1;i>=0;i=i-1)begin:LOC_ONE
      if(i_bitmap[i])begin
        one_loc =i ;
      end
    end
  end
  assign o_binary = one_loc;
  assign o_onehot[0] = i_bitmap[0];
  generate
    for(genvar i =i;i<BITMAP_WIDTH;i=i+1)begin:GEN_ONEHOT
      assign o_onehot[i] = i_bitmap[i] & (~(|i_bitmap[i-1:0]));
    end
  endgenerate
endmodule
