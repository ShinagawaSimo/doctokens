# Chart series

[DOCX](../README.md) / Chart series

DOCX adapts the shared chart series record. Saved labels, trendlines and axis
relationships use [common semantics](../../common/chart-series.md); the body
preview and full resource keep their existing distinct bounds.

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
  - Maximum saved length across category/value/x/y/bubble arrays; point positions and cache holes agree with the shared chart model.

### `name`

- **Output**
  - Resource series detail; inline projection is defined by [charts](chart.md).

- **OOXML**
  - [Shared chart series](../../common/chart-series.md#name)

- **IR**
  - `ChartSeries.name`

- **Parsing**
  - Copy when nonempty.

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
