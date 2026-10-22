// Split a linear transfer into bursts constrained by maximum beats and a
// power-of-two address boundary (normally 4KB).
// in_beats is the total number of beats, not AXI's encoded AxLEN value.
module wql32_axi_burst_splitter #(
    parameter integer ADDR_WIDTH       = 64,
    parameter integer LEN_WIDTH        = 16,
    parameter integer SIZE_WIDTH       = 6,
    parameter integer MAX_BURST_BEATS  = 16,
    parameter integer BOUNDARY_BYTES   = 4096
)(
    input  wire                   clk,
    input  wire                   reset_n,
    input  wire                   in_valid,
    output wire                   in_ready,
    input  wire [ADDR_WIDTH-1:0]  in_addr,
    input  wire [LEN_WIDTH-1:0]   in_beats,
    input  wire [SIZE_WIDTH-1:0]   in_size,
    output wire                   out_valid,
    input  wire                   out_ready,
    output wire [ADDR_WIDTH-1:0]  out_addr,
    output wire [LEN_WIDTH-1:0]   out_beats,
    output wire                   out_last,
    output reg                    error_pulse,
    output reg  [1:0]             error_code
);

    localparam integer CALC_WIDTH     = (ADDR_WIDTH > LEN_WIDTH) ? ADDR_WIDTH : LEN_WIDTH;
    localparam integer BOUNDARY_SHIFT = $clog2(BOUNDARY_BYTES);
    localparam [1:0] ERROR_NONE        = 2'd0;
    localparam [1:0] ERROR_ZERO_BEATS  = 2'd1;
    localparam [1:0] ERROR_ALIGNMENT   = 2'd2;
    localparam [1:0] ERROR_SIZE        = 2'd3;

    reg                  active_reg;
    reg [ADDR_WIDTH-1:0] addr_reg;
    reg [LEN_WIDTH-1:0]  beats_reg;
    reg [SIZE_WIDTH-1:0] size_reg;

    wire [ADDR_WIDTH-1:0] one_addr = {{(ADDR_WIDTH-1){1'b0}}, 1'b1};
    wire [ADDR_WIDTH-1:0] in_beat_bytes = one_addr << in_size;
    wire in_size_error = (in_size >= ADDR_WIDTH) || (in_size > BOUNDARY_SHIFT);
    wire in_alignment_error = !in_size_error &&
                              ((in_addr & (in_beat_bytes - 1'b1)) != 0);

    wire [ADDR_WIDTH-1:0] boundary_mask = BOUNDARY_BYTES - 1;
    wire [ADDR_WIDTH-1:0] addr_offset = addr_reg & boundary_mask;
    wire [ADDR_WIDTH-1:0] boundary_bytes_left = BOUNDARY_BYTES - addr_offset;
    wire [CALC_WIDTH-1:0] boundary_bytes_ext = boundary_bytes_left;
    wire [CALC_WIDTH-1:0] boundary_beats_ext = boundary_bytes_ext >> size_reg;
    wire [CALC_WIDTH-1:0] beats_ext = beats_reg;
    wire [CALC_WIDTH-1:0] max_burst_ext = MAX_BURST_BEATS;
    wire [CALC_WIDTH-1:0] chunk_ext =
        (beats_ext < max_burst_ext) ?
        ((beats_ext < boundary_beats_ext) ? beats_ext : boundary_beats_ext) :
        ((max_burst_ext < boundary_beats_ext) ? max_burst_ext : boundary_beats_ext);
    wire [CALC_WIDTH-1:0] addr_increment_ext = chunk_ext << size_reg;
    wire internal_zero_chunk = active_reg && (chunk_ext == 0);

    assign in_ready  = ~active_reg;
    assign out_valid = active_reg && !internal_zero_chunk;
    assign out_addr  = addr_reg;
    assign out_beats = chunk_ext[LEN_WIDTH-1:0];
    assign out_last  = out_valid && (beats_ext <= chunk_ext);

    always @(posedge clk) begin
        if (!reset_n) begin
            active_reg <= 1'b0;
            addr_reg   <= {ADDR_WIDTH{1'b0}};
            beats_reg  <= {LEN_WIDTH{1'b0}};
            size_reg   <= {SIZE_WIDTH{1'b0}};
            error_pulse <= 1'b0;
            error_code  <= ERROR_NONE;
        end else begin
            error_pulse <= 1'b0;
            error_code  <= ERROR_NONE;
            if (in_valid && in_ready) begin
                if (in_beats == 0) begin
                    active_reg  <= 1'b0;
                    error_pulse <= 1'b1;
                    error_code  <= ERROR_ZERO_BEATS;
                end else if (in_size_error) begin
                    active_reg  <= 1'b0;
                    error_pulse <= 1'b1;
                    error_code  <= ERROR_SIZE;
                end else if (in_alignment_error) begin
                    active_reg  <= 1'b0;
                    error_pulse <= 1'b1;
                    error_code  <= ERROR_ALIGNMENT;
                end else begin
                    active_reg <= 1'b1;
                    addr_reg   <= in_addr;
                    beats_reg  <= in_beats;
                    size_reg   <= in_size;
                end
            end else if (internal_zero_chunk) begin
                active_reg  <= 1'b0;
                error_pulse <= 1'b1;
                error_code  <= ERROR_SIZE;
            end else if (out_valid && out_ready) begin
                if (beats_ext <= chunk_ext) begin
                    active_reg <= 1'b0;
                    beats_reg  <= {LEN_WIDTH{1'b0}};
                end else begin
                    addr_reg  <= addr_reg + addr_increment_ext[ADDR_WIDTH-1:0];
                    beats_reg <= beats_reg - chunk_ext[LEN_WIDTH-1:0];
                end
            end
        end
    end

`ifndef SYNTHESIS
    initial begin
        if ((BOUNDARY_BYTES <= 0) || ((BOUNDARY_BYTES & (BOUNDARY_BYTES - 1)) != 0))
            $error("BOUNDARY_BYTES must be a positive power of two");
        if (MAX_BURST_BEATS <= 0)
            $error("MAX_BURST_BEATS must be greater than zero");
    end
`endif

endmodule
