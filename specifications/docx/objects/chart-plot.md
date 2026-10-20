# Chart plots

[DOCX](../README.md) / Chart plots

Only combination charts retain a plot collection.

## Fields

### `index`

- **Output**
  - Resource plot ordinal.

- **OOXML**
  - Shared ChartPlotInfo.index.

- **IR**
  - `ChartPlot.index: int`

- **Parsing**
  - Copy 1-based ordinal.

### `chartType`

- **Output**
  - Resource plot family.

- **OOXML**
  - Shared ChartPlotInfo.chart_type.

- **IR**
  - `ChartPlot.chartType: str`

- **Parsing**
  - Copy family.

### `seriesIndices`

- **Output**
  - Resource plot membership.

- **OOXML**
  - Shared ChartPlotInfo.series_indices.

- **IR**
  - `ChartPlot.seriesIndices: list[int]`

- **Parsing**
  - Copy global series ordinals in their plot order.
