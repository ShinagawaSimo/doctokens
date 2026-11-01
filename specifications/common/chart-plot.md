# Chart plots

[COMMON](README.md) / Chart plots

Plot membership is retained for combination charts and saved grouping/axis relationships.

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
  - plot/@type only when it differs from the root chart family. The root type
    supplies a single-family default; combination plots state their own family.

- **OOXML**
  - Plot element / layoutId.

- **IR**
  - `ChartPlotInfo.chart_type: str`

- **Parsing**
  - See [chart types](chart.md#chart_type).

### `grouping`

- **Output**
  - plot/@grouping in structural/semantic summaries and complete resources.
- **OOXML**
  - Direct c:grouping/@val, including clustered, stacked and percentStacked.
- **Parsing**
  - Preserve the saved discriminator; cached values are not recalculated as percentages.

### `direction`

- **Output**
  - plot/@direction.
- **OOXML**
  - c:barDir/@val.
- **Parsing**
  - Retain bar/col without editable geometry.

### `axis_ids`

- **Output**
  - plot/@axes, a space-separated list of chart-local axisN IDs;
    series/@plot identifies ownership.
- **OOXML**
  - Direct plot c:axId/@val in source order.
- **Parsing**
  - Map saved references to uniquely declared axes using the shared
    [axis identity](chart.md#axis-identity) rule, retaining source reference
    order. Axis titles/units stay on matching axis records. No primary/secondary
    assignment is inferred from values, ranges or element proximity.

### `unsupported`

- **Output**
  - `<unsupported type="chart-plot" source="SOURCE" index="N"/>`.
- **Parsing**
  - Retain an unreadable chart-family element instead of treating it as absent.
    Known axis/extension/property nodes do not become unknown plots.
