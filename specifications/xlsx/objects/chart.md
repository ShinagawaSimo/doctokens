# Drawing charts

[XLSX](../README.md) / Drawing charts

Chart summaries attach to the worksheet independently of grid truncation.

## Fields

### `id`

- **Output**
  - chart/@id.

- **OOXML**
  - Resolvable chart reference with supported relation type.

- **IR**
  - `DrawingChart.id: str`

- **Parsing**
  - chart1,chart2,... across sheets.

### `ref`

- **Output**
  - chart/@ref.

- **OOXML**
  - Drawing start anchor.

- **IR**
  - `str`

- **Parsing**
  - See [anchors](drawing.md).

### `type`

- **Output**
  - chart/@type.

- **OOXML**
  - Shared chart_type.

- **IR**
  - `str`

- **Parsing**
  - Copy; failed part leaves empty type, which is an explicit empty attribute.

### `title`

- **Output**
  - chart/@title.

- **OOXML**
  - Shared title.

- **IR**
  - `str`

- **Parsing**
  - Copy if nonempty; initial empty string retained otherwise.

### `series_count`

- **Output**
  - chart/@series.

- **OOXML**
  - Shared series_count.

- **IR**
  - `int`

- **Parsing**
  - Default 0.

### `part`

- **Output**
  - Resource chart part.

- **OOXML**
  - Resolved chart relation.

- **IR**
  - `str`

- **Parsing**
  - Missing → CHART_PART_MISSING; read/parse exception → CHART_XML_INVALID; retain placeholder summary.

### `series`

- **Output**
  - Resource series; inline @names.

- **OOXML**
  - Shared saved literal points, reference caches, or ChartEx dimensions.

- **IR**
  - `list[DrawingChartSeries]`

- **Parsing**
  - See [series](chart-series.md); names are nonempty names joined with comma.

### `axes`

- **Output**
  - Axis child elements in structural/semantic worksheet chart summaries and complete chart resources. Plain summaries retain their existing compact chart text.
- **OOXML**
  - Shared ChartML plotArea catAx/valAx/dateAx/serAx records.
- **IR**
  - `DrawingChart.axes: list[dict[str, str]]`.
- **Parsing**
  - Carry the complete parsed axes from the chart-part result into its attached drawing-chart record. Preserve saved order, IDs and cross-axis references, titles, position, number format, explicit scale bounds/orientation/log base, built-in units and custom unit factors. Omit absent fields and axis data when none is saved.
  - Example: a value-axis title USD, display unit thousands and bounds 0..100 produce `<axis display-unit="thousands" kind="valAx" maximum="100" minimum="0" title="USD"/>` plus any other saved axis attributes in both XML reading paths.
  - Units/scales describe the source axis. Do not divide the saved point values by the display factor, infer unsaved bounds, or substitute the axis title for an absent chart title. See [shared axes](../../common/chart.md#axes).

### `plotTypes`

- **Output**
  - chart/@plots.

- **OOXML**
  - Shared combination plots.

- **IR**
  - `list[str]`

- **Parsing**
  - Copy families in plot order only for combination charts.

### `truncated`

- **Output**
  - chart/@truncated=true.

- **OOXML**
  - Inline summary policy.

- **IR**
  - Derived.

- **Parsing**
  - Always true.
