module import_sample #(
  parameter DATA_WIDTH = 32,
  parameter DEPTH = 16
) (
  input logic i_clk,
  input logic i_rst_n,
  input logic [DATA_WIDTH-1:0] i_data,
  output logic o_valid
);
endmodule
