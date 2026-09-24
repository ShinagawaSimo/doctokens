# Chart series

[DOCX](../README.md) / Chart series

DOCX adapts the shared chart series record.

## Fields

### `index`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#index)

- **IR**
  - `ChartSeries.index`

- **Parsing**
  - Copy 1-based index.

### `pointCount`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - Cached category/value arrays.

- **IR**
  - `ChartSeries.pointCount`

- **Parsing**
  - `max(len(categories), len(values))`; unlike shared aggregate point_count, extra x/y/bubble arrays do not enlarge this DOCX series count.

### `preview`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#preview)

- **IR**
  - `ChartSeries.preview`

- **Parsing**
  - Copy.

### `name`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#name)

- **IR**
  - `ChartSeries.name`

- **Parsing**
  - Copy when nonempty.

### `min`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#min)

- **IR**
  - `ChartSeries.min`

- **Parsing**
  - Copy when present, including zero.

### `max`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#max)

- **IR**
  - `ChartSeries.max`

- **Parsing**
  - Copy when present, including zero.

### `formula`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#formula)

- **IR**
  - `ChartSeries.formula`

- **Parsing**
  - Copy nonempty cached source formula.

### `categories`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#categories)

- **IR**
  - `ChartSeries.categories`

- **Parsing**
  - Copy nonempty list.

### `values`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#values)

- **IR**
  - `ChartSeries.values`

- **Parsing**
  - Copy nonempty list.

### `plotIndex`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#plot_index)

- **IR**
  - `ChartSeries.plotIndex`

- **Parsing**
  - Copy when present.

### `chartType`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#chart_type)

- **IR**
  - `ChartSeries.chartType`

- **Parsing**
  - Copy when present.

### `xValues`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#x_values)

- **IR**
  - `ChartSeries.xValues`

- **Parsing**
  - Copy nonempty list.

### `yValues`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#y_values)

- **IR**
  - `ChartSeries.yValues`

- **Parsing**
  - Copy nonempty list.

### `bubbleSizes`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#bubble_sizes)

- **IR**
  - `ChartSeries.bubbleSizes`

- **Parsing**
  - Copy nonempty list.

### `categoryFormula`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#category_formula)

- **IR**
  - `ChartSeries.categoryFormula`

- **Parsing**
  - Copy nonempty string.

### `hidden`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#hidden)

- **IR**
  - `ChartSeries.hidden`

- **Parsing**
  - Store only true.


## Source references

- [parse_chart_root](../../../packages/docx_llm_parser/src/docx_llm_parser/parsing/modules/resources/objects.py#L188)
- [charts.py](../../../packages/docx_llm_parser/src/docx_llm_parser/rendering/objects/charts.py)
