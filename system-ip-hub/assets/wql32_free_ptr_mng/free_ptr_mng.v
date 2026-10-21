module free_ptr_mng #(
    parameter PTR_NUM = 384,
    parameter PTR_WIDTH = (PTR_NUM > 1) ? $clog2(PTR_NUM) : 1,
    parameter END_OF_LIST = 1
)(
    input wire i_clk,
    input wire i_rst_n,
    input wire i_alc_req,
    output wire [PTR_WIDTH-1:0] o_alc_ptr,
    output wire o_alc_vld,
    input wire i_rls_req,
    input wire [PTR_WIDTH-1:0] i_rls_ptr,
    output wire [PTR_WIDTH:0] o_ptr_num
);
reg [PTR_NUM-1:0] ptr_bitmap;
reg [PTR_NUM-1:0] allocated_bitmap;
reg [PTR_WIDTH:0] ptr_num;
reg [PTR_WIDTH-1:0] free_ptr [0:1];
reg [1:0] cache_num;
reg free_ptr_wr_pp, free_ptr_rd_pp;
reg pre_alc_found;
reg [PTR_WIDTH-1:0] pre_alc_ptr;
reg release_fire;
integer search_idx;

always @(*) begin
    pre_alc_found = 0;
    pre_alc_ptr = 0;
    for (search_idx = PTR_NUM-1; search_idx >= 0; search_idx = search_idx-1) begin
        if (ptr_bitmap[search_idx]) begin
            pre_alc_found = 1;
            pre_alc_ptr = search_idx;
        end
    end
end

assign o_alc_vld = i_rst_n && (cache_num != 0);
assign o_alc_ptr = o_alc_vld ? free_ptr[free_ptr_rd_pp] : {PTR_WIDTH{1'b0}};
wire alloc_fire = i_alc_req && o_alc_vld;
// Full cache may be refilled on a real pop, without overwriting an unconsumed item.
wire prefetch_fire = i_rst_n && pre_alc_found && ((cache_num < 2) || alloc_fire);

always @(*) begin
    release_fire = 0;
    if (i_rst_n && i_rls_req && i_rls_ptr < PTR_NUM)
        release_fire = allocated_bitmap[i_rls_ptr];
end

always @(posedge i_clk) begin
    if (!i_rst_n) begin
        ptr_bitmap <= {PTR_NUM{1'b1}};
        allocated_bitmap <= 0;
        ptr_num <= PTR_NUM;
        cache_num <= 0;
        free_ptr_wr_pp <= 0;
        free_ptr_rd_pp <= 0;
        free_ptr[0] <= 0;
        free_ptr[1] <= 0;
    end else begin
        if (prefetch_fire) begin
            ptr_bitmap[pre_alc_ptr] <= 0;
            free_ptr[free_ptr_wr_pp] <= pre_alc_ptr;
            free_ptr_wr_pp <= ~free_ptr_wr_pp;
        end
        if (release_fire) begin
            ptr_bitmap[i_rls_ptr] <= 1;
            allocated_bitmap[i_rls_ptr] <= 0;
        end
        if (alloc_fire) begin
            allocated_bitmap[free_ptr[free_ptr_rd_pp]] <= 1;
            free_ptr_rd_pp <= ~free_ptr_rd_pp;
        end
        case ({prefetch_fire, alloc_fire})
            2'b10: cache_num <= cache_num + 1'b1;
            2'b01: cache_num <= cache_num - 1'b1;
            default: ;
        endcase
        // Total free = bitmap plus cache; internal prefetch does not change it.
        case ({release_fire, alloc_fire})
            2'b10: ptr_num <= ptr_num + 1'b1;
            2'b01: ptr_num <= ptr_num - 1'b1;
            default: ;
        endcase
    end
end
assign o_ptr_num = ptr_num;
endmodule
