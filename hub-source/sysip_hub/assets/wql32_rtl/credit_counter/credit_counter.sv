// Credit allocator/return counter.
// Allocation is conservative: same-cycle returned credits are available from
// the following cycle, not from the current allocation decision.
module wql32_credit_counter #(
    // CREDIT_WIDTH must be wide enough to represent MAX_CREDITS itself.
    parameter integer CREDIT_WIDTH = 9,
    parameter integer MAX_CREDITS   = 256,
    parameter integer INIT_CREDITS  = MAX_CREDITS,
    parameter integer AR            = 0
)(
    input  wire                    clk,
    input  wire                    reset_n,
    input  wire                    alloc_valid,
    output wire                    alloc_ready,
    input  wire [CREDIT_WIDTH-1:0] alloc_count,
    input  wire                    return_valid,
    input  wire [CREDIT_WIDTH-1:0] return_count,
    input  wire                    clear_errors,
    output wire [CREDIT_WIDTH-1:0] credit_available,
    output wire                    empty,
    output wire                    full,
    output wire                    alloc_blocked,
    output wire                    return_overflow,
    output reg                     overflow_error
);

    reg [CREDIT_WIDTH-1:0] credit_reg;
    wire alloc_fire = alloc_valid && alloc_ready;
    wire [CREDIT_WIDTH:0] return_ext = return_valid ? {1'b0, return_count} : 0;
    wire [CREDIT_WIDTH:0] alloc_ext = alloc_fire ? {1'b0, alloc_count} : 0;
    wire [CREDIT_WIDTH:0] net_credit_ext = {1'b0, credit_reg} + return_ext - alloc_ext;
    wire return_overflow_now = return_valid && (net_credit_ext > MAX_CREDITS);
    reg [CREDIT_WIDTH:0] next_credit_ext;

    assign alloc_ready       = (alloc_count <= credit_reg);
    assign alloc_blocked     = alloc_valid && !alloc_ready;
    assign return_overflow   = return_overflow_now;
    assign credit_available  = credit_reg;
    assign empty             = (credit_reg == 0);
    assign full              = (credit_reg == MAX_CREDITS);

    always @(*) begin
        next_credit_ext = net_credit_ext;
        if (net_credit_ext > MAX_CREDITS)
            next_credit_ext = MAX_CREDITS;
    end

    generate
        if (AR == 1) begin : g_async_reset
            always @(posedge clk or negedge reset_n) begin
                if (!reset_n) begin
                    credit_reg    <= (INIT_CREDITS > MAX_CREDITS) ? MAX_CREDITS : INIT_CREDITS;
                    overflow_error <= 1'b0;
                end else begin
                    credit_reg <= next_credit_ext[CREDIT_WIDTH-1:0];
                    if (return_overflow_now)
                        overflow_error <= 1'b1;
                    else if (clear_errors)
                        overflow_error <= 1'b0;
                end
            end
        end else begin : g_sync_reset
            always @(posedge clk) begin
                if (!reset_n) begin
                    credit_reg     <= (INIT_CREDITS > MAX_CREDITS) ? MAX_CREDITS : INIT_CREDITS;
                    overflow_error <= 1'b0;
                end else begin
                    credit_reg <= next_credit_ext[CREDIT_WIDTH-1:0];
                    if (return_overflow_now)
                        overflow_error <= 1'b1;
                    else if (clear_errors)
                        overflow_error <= 1'b0;
                end
            end
        end
    endgenerate

endmodule
