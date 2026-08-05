"""Renderer-wide constants and thresholds."""

# Sentinel used when scanning grid bounds: any real cell coordinate will be
# smaller than this, so the first real cell replaces it.
_GRID_BOUND_SENTINEL = 1_000_000

# Truncation budget per sheet when rendering the default view.
# Exceeding any one threshold triggers head+tail sampling.
_CELL_BUDGET = 200   # max non-empty cells before truncation
_ROW_BUDGET = 20     # max data rows before truncation
_COL_BUDGET = 12     # max columns before truncation

# When truncated: how many head / tail rows and columns to keep.
_HEAD_ROWS = 8
_TAIL_ROWS = 4
_HEAD_COLS = 8
_TAIL_COLS = 4
