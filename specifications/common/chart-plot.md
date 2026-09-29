# Chart plots

[COMMON](README.md) / Chart plots

Plot membership is retained for combination charts.

## Fields

### `index`

- **Output**
  - Resource plot ordinal.

- **OOXML**
  - ChartML recognized plot order; ChartEx first occurrence of layoutId.

- **IR**
  - `ChartPlotInfo.index: int`

- **Parsing**
  - 1-based.

### `chart_type`

- **Output**
  - Resource plot family.

- **OOXML**
  - Plot element / layoutId.

- **IR**
  - `ChartPlotInfo.chart_type: str`

- **Parsing**
  - See [chart types](chart.md#chart_type).

### `series_indices`

- **Output**
  - Resource series ownership.

- **OOXML**
  - Series assigned to this plot.

- **IR**
  - `ChartPlotInfo.series_indices: list[int]`

- **Parsing**
  - Global series indices in traversal order. ChartEx series with the same layoutId share one plot record.


## Source references

- [ChartParser._parse_chartml](../../packages/ooxml_llm_core/src/ooxml_llm_core/chart_ml.py#L142)
- [ChartParser._parse_chartex](../../packages/ooxml_llm_core/src/ooxml_llm_core/chart_ml.py#L207)
