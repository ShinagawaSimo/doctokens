"""Renderer-wide constants and thresholds."""

# Sentinel used when scanning grid bounds: any real cell coordinate will be
# smaller than this, so the first real cell replaces it.
_GRID_BOUND_SENTINEL = 1_000_000
