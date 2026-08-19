module clk_divider #(
    parameter DIV_FACTOR = 2,
    parameter DIV_MODE   = 0
)(
    input  wire          clk_in,
    input  wire          rst_n,
    input  wire          clk_en,
    output reg           clk_out
);

    integer cnt;
    reg clk_half;

    if (DIV_MODE == 0) begin : even_div
        always @(posedge clk_in or negedge rst_n) begin
            if (!rst_n) begin
                cnt <= 0;
                clk_out <= 0;
            end else if (clk_en) begin
                if (cnt >= (DIV_FACTOR/2 - 1)) begin
                    cnt <= 0;
                    clk_out <= ~clk_out;
                end else begin
                    cnt <= cnt + 1;
                end
            end
        end
    end else if (DIV_MODE == 1) begin : odd_div
        always @(posedge clk_in or negedge rst_n) begin
            if (!rst_n) begin
                cnt <= 0;
                clk_out <= 0;
            end else if (clk_en) begin
                if (cnt == DIV_FACTOR-1)
                    cnt <= 0;
                else
                    cnt <= cnt + 1;
                if (cnt < DIV_FACTOR/2)
                    clk_out <= 1;
                else
                    clk_out <= 0;
            end
        end
        always @(negedge clk_in or negedge rst_n) begin
            if (!rst_n)
                clk_half <= 0;
            else if (clk_en)
                clk_half <= clk_out;
        end
        always @(*) clk_out = clk_out | clk_half;
    end

endmodule