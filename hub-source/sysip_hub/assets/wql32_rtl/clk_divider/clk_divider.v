module clk_divider #(
    parameter DIV_FACTOR = 2,
    parameter DIV_MODE = 0
)(
    input wire clk_in,
    input wire rst_n,
    input wire clk_en,
    output wire clk_out
);
generate
    if (DIV_MODE == 0 && DIV_FACTOR >= 2 && DIV_FACTOR % 2 == 0) begin : even_div
        localparam COUNT_WIDTH = (DIV_FACTOR > 2) ? $clog2(DIV_FACTOR/2) : 1;
        reg [COUNT_WIDTH-1:0] cnt;
        reg clk_even;
        always @(posedge clk_in or negedge rst_n) begin
            if (!rst_n) begin cnt <= 0; clk_even <= 0; end
            else if (clk_en) begin
                if (cnt == DIV_FACTOR/2-1) begin cnt <= 0; clk_even <= ~clk_even; end
                else cnt <= cnt + 1'b1;
            end
        end
        assign clk_out = clk_even;
    end else if (DIV_MODE == 1 && DIV_FACTOR >= 3 && DIV_FACTOR % 2 == 1) begin : odd_div
        localparam COUNT_WIDTH = $clog2(DIV_FACTOR);
        reg [COUNT_WIDTH-1:0] cnt;
        reg clk_pos, clk_neg, step_en;
        always @(posedge clk_in or negedge rst_n) begin
            if (!rst_n) begin cnt <= 0; clk_pos <= 0; step_en <= 0; end
            else begin
                step_en <= clk_en;
                if (clk_en) begin
                    cnt <= (cnt == DIV_FACTOR-1) ? 0 : cnt + 1'b1;
                    clk_pos <= (cnt < DIV_FACTOR/2);
                end
            end
        end
        // Finish the half-cycle selected at the preceding positive edge.
        always @(negedge clk_in or negedge rst_n) begin
            if (!rst_n) clk_neg <= 0;
            else if (step_en) clk_neg <= clk_pos;
        end
        assign clk_out = clk_pos | clk_neg;
    end else begin : invalid_config
        // Invalid mode/parity/factor has a deterministic inactive output.
        assign clk_out = 1'b0;
    end
endgenerate
endmodule
