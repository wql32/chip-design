// Single-outstanding transaction timeout monitor.
// timeout_limit=0 disables timeout expiry while a transaction is active.
module wql32_timeout_monitor #(
    parameter integer TIMEOUT_WIDTH = 16,
    parameter integer AR            = 0
)(
    input  wire                    clk,
    input  wire                    reset_n,
    input  wire                    start_valid,
    output wire                    start_ready,
    input  wire                    done,
    input  wire                    abort,
    input  wire [TIMEOUT_WIDTH-1:0] timeout_limit,
    input  wire                    clear_sticky,
    output wire                    active,
    output wire [TIMEOUT_WIDTH-1:0] elapsed,
    output reg                     timeout_pulse,
    output reg                     timeout_sticky
);

    reg                   active_reg;
    reg [TIMEOUT_WIDTH-1:0] elapsed_reg;
    reg [TIMEOUT_WIDTH-1:0] timeout_limit_reg;
    wire [TIMEOUT_WIDTH:0] elapsed_next = {1'b0, elapsed_reg} + 1'b1;
    wire timeout_now = active_reg && (timeout_limit_reg != 0) &&
                       (elapsed_next >= timeout_limit_reg);
    wire timeout_fire = timeout_now && !done && !abort;
    wire start_fire;

    assign start_ready = ~active_reg || done || abort;
    assign start_fire  = start_valid && start_ready;
    assign active      = active_reg;
    assign elapsed     = elapsed_reg;

    generate
        if (AR == 1) begin : g_async_reset
            always @(posedge clk or negedge reset_n) begin
                if (!reset_n) begin
                    active_reg    <= 1'b0;
                    elapsed_reg   <= {TIMEOUT_WIDTH{1'b0}};
                    timeout_limit_reg <= {TIMEOUT_WIDTH{1'b0}};
                    timeout_pulse <= 1'b0;
                    timeout_sticky <= 1'b0;
                end else begin
                    timeout_pulse <= 1'b0;
                    if (!active_reg) begin
                        if (start_fire) begin
                            active_reg  <= 1'b1;
                            elapsed_reg <= {TIMEOUT_WIDTH{1'b0}};
                            timeout_limit_reg <= timeout_limit;
                        end
                    end else if (done || abort) begin
                        if (start_fire) begin
                            active_reg  <= 1'b1;
                            elapsed_reg <= {TIMEOUT_WIDTH{1'b0}};
                            timeout_limit_reg <= timeout_limit;
                        end else begin
                            active_reg  <= 1'b0;
                            elapsed_reg <= {TIMEOUT_WIDTH{1'b0}};
                        end
                    end else if (timeout_fire) begin
                        active_reg     <= 1'b0;
                        elapsed_reg    <= timeout_limit_reg;
                        timeout_pulse  <= 1'b1;
                        timeout_sticky <= 1'b1;
                    end else begin
                        if (!(&elapsed_reg))
                            elapsed_reg <= elapsed_next[TIMEOUT_WIDTH-1:0];
                    end
                    if (clear_sticky && !timeout_fire)
                        timeout_sticky <= 1'b0;
                end
            end
        end else begin : g_sync_reset
            always @(posedge clk) begin
                if (!reset_n) begin
                    active_reg     <= 1'b0;
                    elapsed_reg    <= {TIMEOUT_WIDTH{1'b0}};
                    timeout_limit_reg <= {TIMEOUT_WIDTH{1'b0}};
                    timeout_pulse  <= 1'b0;
                    timeout_sticky <= 1'b0;
                end else begin
                    timeout_pulse <= 1'b0;
                    if (!active_reg) begin
                        if (start_fire) begin
                            active_reg  <= 1'b1;
                            elapsed_reg <= {TIMEOUT_WIDTH{1'b0}};
                            timeout_limit_reg <= timeout_limit;
                        end
                    end else if (done || abort) begin
                        if (start_fire) begin
                            active_reg  <= 1'b1;
                            elapsed_reg <= {TIMEOUT_WIDTH{1'b0}};
                            timeout_limit_reg <= timeout_limit;
                        end else begin
                            active_reg  <= 1'b0;
                            elapsed_reg <= {TIMEOUT_WIDTH{1'b0}};
                        end
                    end else if (timeout_fire) begin
                        active_reg     <= 1'b0;
                        elapsed_reg    <= timeout_limit_reg;
                        timeout_pulse  <= 1'b1;
                        timeout_sticky <= 1'b1;
                    end else begin
                        if (!(&elapsed_reg))
                            elapsed_reg <= elapsed_next[TIMEOUT_WIDTH-1:0];
                    end
                    if (clear_sticky && !timeout_fire)
                        timeout_sticky <= 1'b0;
                end
            end
        end
    endgenerate

endmodule
