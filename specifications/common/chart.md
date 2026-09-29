# Chart parts

[COMMON](README.md) / Chart parts

ChartML and ChartEx are parsed from saved caches without evaluating formulas or opening embedded workbooks.

## Processing

Dispatch to ChartEx only for `{http://schemas.microsoft.com/office/drawing/2014/chartex}chartSpace`; otherwise use ChartML. Unknown plot elements are skipped. The shared extractor emits no warnings; format adapters handle missing parts and parse exceptions.

## Fields

### `chart_type`

- **Output**
  - Input to format-specific chart type attributes.

- **OOXML**
  - ChartML plot child local name; ChartEx cx:series/@layoutId.

- **IR**
  - `ChartInfo.chart_type: str`

- **Parsing**
  - ChartML maps areaChart/area3DChart/barChart/bar3DChart/bubbleChart/doughnutChart/lineChart/line3DChart/ofPieChart/pieChart/pie3DChart/radarChart/scatterChart/stockChart/surfaceChart/surface3DChart to area/area3d/bar/bar3d/bubble/doughnut/line/line3d/ofPie/pie/pie3d/radar/scatter/stock/surface/surface3d. More than one distinct family → combination.

- **Absence and defaults**
  - unknown if no family.

### `title`

- **Output**
  - Format-specific chart title.

- **OOXML**
  - ChartML first c:title; ChartEx chart/cx:title.

- **IR**
  - `ChartInfo.title: str`

- **Parsing**
  - Concatenate descendant a:t, strip; omit if empty.

### `series`

- **Output**
  - Ordered series records.

- **OOXML**
  - ChartML direct c:ser per recognized plot; ChartEx plotAreaRegion/cx:series.

- **IR**
  - `list[ChartSeriesInfo]`

- **Parsing**
  - [Series](chart-series.md).

### `series_count`

- **Output**
  - Format-specific series count.

- **OOXML**
  - Retained series.

- **IR**
  - `int`

- **Parsing**
  - `len(series)`.

### `point_count`

- **Output**
  - Format-specific total point count.

- **OOXML**
  - Series caches.

- **IR**
  - `int`

- **Parsing**
  - Sum, over series, of maximum length of categories/values/x_values/y_values/bubble_sizes.

### `plots`

- **Output**
  - Combination-plot records.

- **OOXML**
  - ChartML plot children; ChartEx layout family.

- **IR**
  - `list[ChartPlotInfo]`

- **Parsing**
  - Retain only when chart_type == combination. Single-family charts also remove per-series plot_index/chart_type. See [plots](chart-plot.md).


## Source references

- [ChartParser.parse](../../packages/ooxml_llm_core/src/ooxml_llm_core/chart_ml.py#L137)
- [_chart_info](../../packages/ooxml_llm_core/src/ooxml_llm_core/chart_ml.py#L289)
