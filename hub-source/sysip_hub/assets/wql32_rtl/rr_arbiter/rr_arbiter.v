module rr_arbiter #(
    parameter REQ_NUM = 8
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [REQ_NUM-1:0]    i_req,
    input  wire                  i_grant_en,
    output wire [REQ_NUM-1:0]    o_grant,
    output wire [$clog2(REQ_NUM)-1:0] o_grant_id,
    output wire                  o_grant_vld
);

    reg  [$clog2(REQ_NUM)-1:0] last_grant;
    wire [REQ_NUM-1:0]          mask;
    wire [REQ_NUM-1:0]          masked_req;
    wire [REQ_NUM-1:0]          unmasked_req;
    wire [REQ_NUM-1:0]          selected_req;
    wire                        any_req;

    assign mask = ({{REQ_NUM{1'b1}}} << (last_grant + 1));
    assign masked_req   = i_req & mask;

    function [REQ_NUM-1:0] priority_enc;
        input [REQ_NUM-1:0] req;
        integer i;
        begin
            priority_enc = 0;
            for (i = REQ_NUM - 1; i >= 0; i = i - 1) begin
                if (req[i]) begin
                    priority_enc = ({{(REQ_NUM-1){1'b0}}, 1'b1} << i);
                end
            end
        end
    endfunction

    assign unmasked_req = i_req;

    wire [REQ_NUM-1:0] high_pri_grant = priority_enc(masked_req);
    wire [REQ_NUM-1:0] low_pri_grant  = priority_enc(unmasked_req);

    assign selected_req = (|masked_req) ? high_pri_grant : low_pri_grant;
    assign any_req      = |i_req;

    assign o_grant     = i_grant_en ? selected_req : {REQ_NUM{1'b0}};
    assign o_grant_vld = i_grant_en && any_req;

    generate
        if (REQ_NUM == 1) begin
            assign o_grant_id = 0;
        end else begin
            reg [$clog2(REQ_NUM)-1:0] grant_id_r;
            integer idx;
            always @(*) begin
                grant_id_r = 0;
                for (idx = 0; idx < REQ_NUM; idx = idx + 1) begin
                    if (selected_req[idx]) grant_id_r = idx;
                end
            end
            assign o_grant_id = grant_id_r;
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            last_grant <= 0;
        end else if (o_grant_vld) begin
            last_grant <= o_grant_id;
        end
    end

endmodule