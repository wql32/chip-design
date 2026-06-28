module free_ptr_mng #(
    parameter PTR_NUM = 384, // Total number of managed pointers
    parameter PTR_WIDTH = $clog2(PTR_NUM) // Data width of a pointer
    parameter END_OF_LIST =1
) (
    input wire i_clk,
    input wire i_rst_n,
    input wire                  i_alc_req, // Allocation request
    output wire [PTR_WIDTH-1:0] o_alc_ptr, // Allocated free pointer
    output wire o_alc_vld, // A flag to indicate there're free pointers
  
    input wire                 i_rls_req, // Allocation request
    input wire [PTR_WIDTH-1:0] i_rls_ptr, // Allocated free pointer
  
    output wire [PTR_WIDTH:0] o_ptr_num // Number of free pointers
);

    reg [PTR_NUM-1:0] ptr_bitmap; // Bitmap of pointer pool. 1: free. 0: occupied.
    reg [PTR_WIDTH:0] ptr_num; // Number of free pointers
    reg [1:0] cache_num; // Number of cached pointers
    wire [PTR_NUM-1:0] alc_req; // Allocation request in a bitmap style
    wire [PTR_NUM-1:0] rls_req; // Release request in a bitmap style
    wire [PTR_WIDTH-1:0] pre_alc_req;
    reg [PTR_WIDTH-1:0] pre_alc_ptr;
    reg [1:0] free_ptr_vld; // A flag to indicate there're free pointers
    reg [PTR_WIDTH-1:0] free_ptr[1:0]; // A pre-allocated pointer
    reg free_ptr_wr_pp;
    reg free_ptr_rd_pp;
    wire num_upd; // Released number subs allocated number, MSB bit is sign bit.
  	wire [1:0] rls_sub_alc_num ;

    assign alc_req = {{(PTR_NUM-1){1'b0}}, pre_alc_req} << pre_alc_ptr;
    assign rls_req = {{(PTR_NUM-1){1'b0}}, i_rls_req} << i_rls_ptr;

    generate
        for(genvar i = 0; i < PTR_NUM; i = i + 1) begin: BITMAP
            always @(posedge i_clk) begin
                if(!i_rst_n) begin
                    ptr_bitmap[i] <= 1'b1;
                end else if(alc_req[i]) begin
                    ptr_bitmap[i] <= 1'b0;
                end else if(rls_req[i]) begin
                    ptr_bitmap[i] <= 1'b1;
                end else;
            end
        end
    endgenerate

always @(*) begin
    for(i = PTR_NUM - 1; i > 0; i = i - 1) begin: PRE_ALC_PTR
        if(ptr_bitmap[i]) begin
            pre_alc_ptr = i;
        end
    end
end

assign pre_alc_req = (|ptr_num) && (~(&free_ptr_vld));

always @(posedge i_clk) begin
    if(!i_rst_n) begin
        free_ptr_vld[0] <= 1'b0;
        free_ptr_vld[1] <= 1'b0;
    end 
    else begin
        case({pre_alc_req, i_alc_req})
            2'b01: begin
               free_ptr_vld[free_ptr_rd_pp] <= 1'b0;
            end
            2'b10: begin
              	free_ptr_vld[free_ptr_wr_pp] <= 1'b1;
            end
            2'b11: begin
               free_ptr_vld[free_ptr_rd_pp] <= 1'b0;
               free_ptr_vld[free_ptr_wr_pp] <= 1'b1;
            end
            default;
        endcase
    end
end

always @(posedge i_clk) begin
    if(pre_alc_req) begin
        free_ptr[free_ptr_wr_pp] <= pre_alc_ptr;
    end
end

always @(posedge i_clk) begin
    if(!i_rst_n) begin
        free_ptr_wr_pp <= 1'b0;
    end else if(pre_alc_req) begin
        free_ptr_wr_pp <= ~free_ptr_wr_pp;
    end
end

always @(posedge i_clk) begin
    if(!i_rst_n) begin
        free_ptr_rd_pp <= 1'b0;
    end else if(i_alc_req) begin
        free_ptr_rd_pp <= ~free_ptr_rd_pp;
    end
end

assign num_upd = pre_alc_req || i_rls_req;
assign rls_sub_alc_num = {1'b0, i_rls_req} - {1'b0, pre_alc_req};

always @(posedge i_clk) begin
    if(!i_rst_n) begin
        ptr_num <= PTR_NUM;
    end else if(num_upd) begin
        ptr_num <= ptr_num + {{PTR_WIDTH{rls_sub_alc_num[1]}}, rls_sub_alc_num[0]};
    end
end

always @(*) begin
  cache_num = {1'b0, free_ptr_vld[1]} + {1'b0, free_ptr_vld[0]};
end

assign o_alc_vld = free_ptr_vld[free_ptr_rd_pp];
assign o_alc_ptr = free_ptr[free_ptr_rd_pp];
assign o_ptr_num = {{(PTR_WIDTH-1){1'b0}}, cache_num};

endmodule
