module find_1st_one
  #(
    parameter BITMAP_WIDTH      = 253 ,
    parameter BIN_WIDTH         = $clog2(BITMAP_WIDTH)
  )
  (
    input  wire  [BITMAP_WIDTH-1:0]  i_bitmap  ,
    output wire  [BITMAP_WIDTH-1:0]  o_onehot  ,
    output wire  [BIN_WIDTH-1:0]     o_binary
  );
  reg [BIN_WIDTH-1:0] one_loc;
  integer bitmap_idx;
  genvar onehot_idx;
  always@(*)begin
    one_loc = {BIN_WIDTH{1'b0}};
    for (bitmap_idx = BITMAP_WIDTH -1;bitmap_idx>=0;bitmap_idx=bitmap_idx-1)begin:LOC_ONE
      if(i_bitmap[bitmap_idx])begin
        one_loc = bitmap_idx;
      end
    end
  end
  assign o_binary = one_loc;
  assign o_onehot[0] = i_bitmap[0];
  generate
    for(onehot_idx = 1;onehot_idx<BITMAP_WIDTH;onehot_idx=onehot_idx+1)begin:GEN_ONEHOT
      assign o_onehot[onehot_idx] = i_bitmap[onehot_idx] & (~(|i_bitmap[onehot_idx-1:0]));
    end
  endgenerate
endmodule
