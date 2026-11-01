# Chart series

[XLSX](../README.md) / Chart series

XLSX adapts shared arrays once to the common ChartPoint records. Point order is the cache position; no duplicate coordinate arrays are retained in its drawing-series model.
Body previews retain the same series identity and cached point positions under
the [shared limits](../../common/chart.md#body-preview); resources remain complete.

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

### `plotIndex`

- **Output**
  - Chart resource detail.

- **OOXML**
  - [Shared series](../../common/chart-series.md#plot_index)

- **IR**
  - `DrawingChartSeries.plotIndex`

- **Parsing**
  - Copy when present.

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
