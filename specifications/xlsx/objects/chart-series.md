# Chart series

[XLSX](../README.md) / Chart series

XLSX adapts shared series arrays to point records.

## Fields

### `index`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#index)

- **IR**
  - `DrawingChartSeries.index`

- **Parsing**
  - Copy.

### `pointCount`

- **Output**
  - Chart resource detail.

- **OOXML**
  - Shared series arrays.

- **IR**
  - `DrawingChartSeries.pointCount`

- **Parsing**
  - Maximum length of all five shared category/value/x/y/bubble arrays.

### `name`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#name)

- **IR**
  - `DrawingChartSeries.name`

- **Parsing**
  - Copy nonempty.

### `min`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#min)

- **IR**
  - `DrawingChartSeries.min`

- **Parsing**
  - Copy when present.

### `max`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#max)

- **IR**
  - `DrawingChartSeries.max`

- **Parsing**
  - Copy when present.

### `plotIndex`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#plot_index)

- **IR**
  - `DrawingChartSeries.plotIndex`

- **Parsing**
  - Copy when present.

### `chartType`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#chart_type)

- **IR**
  - `DrawingChartSeries.chartType`

- **Parsing**
  - Copy when present.

### `xValues`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#x_values)

- **IR**
  - `DrawingChartSeries.xValues`

- **Parsing**
  - Copy nonempty list.

### `yValues`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#y_values)

- **IR**
  - `DrawingChartSeries.yValues`

- **Parsing**
  - Copy nonempty list.

### `bubbleSizes`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#bubble_sizes)

- **IR**
  - `DrawingChartSeries.bubbleSizes`

- **Parsing**
  - Copy nonempty list.

### `hidden`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#hidden)

- **IR**
  - `DrawingChartSeries.hidden`

- **Parsing**
  - Store true only.

### `points`

- **Output**
  - Chart resource detail.

- **OOXML**
  - Shared series arrays.

- **IR**
  - `DrawingChartSeries.points`

- **Parsing**
  - For each position0..pointCount-1, copy in-bounds array values to [point fields](chart-point.md); omit only an empty dictionary.


## Source references

- [_parse_chart_part](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/post.py#L527)
- [_render_chart_resource](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/api.py#L437)
