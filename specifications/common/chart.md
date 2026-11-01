# Chart parts

[COMMON](README.md) / Chart parts

ChartML and ChartEx are parsed from saved literal points, reference caches, and ChartEx dimensions without evaluating formulas or opening embedded workbooks.

Body chart previews in DOCX/PPTX retain the first eight series and up to eight
saved points per series. They remain explicitly truncated and can be expanded
through the existing resource operation; point/category boundaries use XML child
elements, even when labels contain commas. PPTX resources also contain
comma-joined summary attributes; explicit point children are the unambiguous
data representation.

## Processing

Dispatch to ChartEx only for `{http://schemas.microsoft.com/office/drawing/2014/chartex}chartSpace`; otherwise use ChartML.
Unknown chart-family elements retain unsupported plot records. Format adapters
handle missing parts and parse exceptions.

## Fields

### `body preview`

- **Output**
  - DOCX/PPTX/XLSX structural and semantic share a bounded projection: at most
    8 series, 8 saved points per series, 8 axes, 8 plots and 16 annotation elements
    across the chart. Root @series counts parsed series; @points sums each
    series' largest cached array length, rather than distinct categories.
  - Series names occur only on series; categories occur only on points. Point
    @index preserves the zero-based cache position. Plot membership lists have
    at most 8 shown identities; references do not claim omitted definitions exist.
- **Projection**
  - Saved scalar strings share 2,400 characters, at most 160 per field. Human
    labels can end with an ellipsis. Numeric point fields are indivisible: omit
    an unfittable point rather than show a false numeric prefix. Empty cache
    positions preserve their indices without pretending they are numeric zero.
  - Retain applicable units, axis titles/formats/scales, grouping/direction,
    hidden-series state, labels and trendlines within the budget. Labels only
    refer to displayed points. Do not evaluate chart formulas or scale caches.
  - Actual omissions mark the chart truncated=true and affected series/points
    where applicable. A complete small chart omits this flag. Unreadable objects
    retain unsupported placeholders; resources bypass body preview limits.
- **Plain**
  - `[Chart chart1: Sales (bar, 1 series); A]` identifies the resource, title,
    type, total series count and at most 8 names. Title/name strings share 512
    characters and the 160-character field cap. Explicit truncated text marks
    omitted labels; plain does not duplicate point arrays.
- **Resources**
  - Complete serializers retain their existing supported full arrays, axes,
    plots and annotations. Body rendering does not mutate them. Use the body's
    chart ID for lookup; ref/shape-id remain format-specific navigation.

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
  - ChartML chartSpace/chart/title; ChartEx chart/cx:title.

- **IR**
  - `ChartInfo.title: str`

- **Parsing**
  - Concatenate the chart title's descendant a:t, strip; omit if empty. An axis title under plotArea is independent and is never promoted to chart title when chart/title is absent.

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
  - Saved series literal/cache/dimension arrays.

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
  - Retain for combination charts or explicit grouping/axis relationships.
    Keep per-series plot ownership whenever plots remain. A simple family
    without these fields retains the compact projection. See [plots](chart-plot.md).

### `axes`

- **Output**
  - `axis` children in chart body metadata and full resources across DOCX/PPTX/XLSX.
- **OOXML**
  - Standard ChartML `plotArea` children `catAx`, `valAx`, `dateAx`, `serAx`.
- **IR**
  - `ChartInfo.axes: list[dict[str, str]]`, retained by format chart records.
- **Parsing**
  - Apply the same closed reading field set to body metadata and complete
    resources: id, kind, cross-axis, title, num-format, minimum, maximum,
    log-base, orientation, display-unit and custom-unit. Plain does not expand
    axis records. Units/formats do not recalculate the cached chart numbers.
  - Omit position, default minMax orientation, empty format codes and General
    (case-insensitive after trimming). Retain nonempty other saved format codes
    verbatim, including percent, currency and date codes. Preserve explicit
    limits, log base and reverse maxMin orientation. Missing/auto limits are
    not calculated. Axis titles are not chart titles.
  - ChartEx uses only declared axis identity, known valScaling min/max,
    catScaling/valScaling identity, saved title, non-General number format and
    units/@unit. Normalize unit to display-unit. Do not copy hidden, category
    gap width, tick spacing majorUnit/minorUnit or arbitrary source attributes.
    Built-in units are hundreds, thousands, tenThousands, hundredThousands,
    millions, tenMillions, hundredMillions, billions, trillions and ChartEx
    percentage; unknown unit declarations add no guessed interpretation.

### `axis identity`

- **Output**
  - Chart-local axis1, axis2, ... in saved axis declaration order. Plot/series
    @axes and axis/@cross-axis refer to these same IDs in all formats.
- **OOXML**
  - ChartML axId/crossAx and plot axId; ChartEx axis/@id and series/axisId.
- **IR**
  - Compact axes/@id and cross_axis, ChartPlotInfo/ChartSeriesInfo.axis_ids.
    Source identities are discarded after the per-chart mapping pass.
- **Parsing**
  - Rewrite only references that resolve uniquely to a declared axis. Missing,
    dangling or duplicate ambiguous source identities produce no guessed link;
    independently readable axis records remain. No primary/secondary role is
    inferred from position, value ranges, chart type or proximity.
  - Body preview limits can omit axis records and their links under the existing
    budget. Complete resources retain all parsed reading axes, using the same
    numbering. A body render never renumbers or mutates the resource model.
