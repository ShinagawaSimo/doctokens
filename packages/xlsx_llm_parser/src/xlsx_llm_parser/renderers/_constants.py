"""Renderer-wide constants and thresholds."""

# Sentinel used when scanning grid bounds: any real cell coordinate will be
# smaller than this, so the first real cell replaces it.
_GRID_BOUND_SENTINEL = 1_000_000

# Truncation budget per sheet when rendering the default view.
# Exceeding any one threshold triggers truncation (no rows output).
_CELL_BUDGET = 500  # max non-empty cells before truncation
_ROW_BUDGET = 50  # max data rows before truncation
_COL_BUDGET = 30  # max columns before truncation
