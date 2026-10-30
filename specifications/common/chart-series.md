# Chart series

[COMMON](README.md) / Chart series

Each field belongs to ChartSeriesInfo.

## Processing

Saved points use the same indexed reader for literal data and reference caches. Enumerate direct pt children; int(idx) or enumeration index on missing/malformed idx. A duplicate index replaces its preceding value. Prefer the direct v child's text, including an explicitly empty v; otherwise use direct point text, as in ChartEx. Formatting whitespace around a v child is not a point value. Return positions 0..max(index), filling holes with empty strings; declared ptCount does not manufacture points or set list length. ChartEx numeric dimensions use their last lvl. ChartEx dataId resolves a catalog of chartData/data; later duplicate IDs replace earlier records.

## Fields

### `labels`

- **Output**
  - series/label with zero-based index, optional position/deleted and saved text.
    label-options retains saved visibility and separator declarations.
- **OOXML**
  - c:dLbls/c:dLbl/c:idx and c:tx rich text/strRef cache.
    c15:datalabelsRange/c15:dlblRangeCache/c:pt supplies explicitly indexed
    range labels (DrawingML 2012 chart namespace).
    ChartEx dataLabels/dataLabel/dataLabelHidden retains indices, position,
    hidden state and visibility declarations.
- **Parsing**
  - Direct labels override plot defaults and saved range text at that index.
    Preserve paragraph/soft-break text. Do not open external workbooks or
    generate numeric/percentage labels from visibility flags.
  - DOCX/PPTX previews retain at most eight labels for points 0..7 in the first
    eight series; full resources retain all saved labels. XLSX keeps its compact
    body summary, with annotations in full chart resources.
  - A label reference with no saved cache retains an unsupported chart-label
    marker; an explicitly empty saved label remains empty. The reader does
    not fetch/compute missing label text.

### `trendlines`

- **Output**
  - series/trendline: saved type, name, order/period, forward/backward, intercept,
    display-equation/display-r-squared and label when available.
- **OOXML**
  - c:trendline and c:trendlineLbl/c:tx.
- **Parsing**
  - Read saved configuration/text only. A saved y=2x+1 remains readable;
    an enabled equation without saved text never causes fitting/reconstruction.
    DOCX/PPTX previews cap at eight trendlines; full resources retain all.

### `axis_ids`

- **Output**
  - series/@axes for explicit ChartEx axis references.
- **OOXML**
  - cx:series/cx:axisId.
- **Parsing**
  - Preserve source ID order; use the matching axis metadata for meaning.

### `index`

- **Output**
  - Resource series ordinal.

- **OOXML**
  - Series traversal order.

- **IR**
  - `ChartSeriesInfo.index: `int``

- **Parsing**
  - 1-based across all plots; source c:idx/c:order do not reorder the result.

### `plot_index`

- **Output**
  - Resource plot ownership.

- **OOXML**
  - Owning parsed plot.

- **IR**
  - `ChartSeriesInfo.plot_index: `int``

- **Parsing**
  - 1-based plot index whenever plot metadata is retained, including explicit
    grouping/axis relationships on a single-family chart.

### `chart_type`

- **Output**
  - Resource series family.

- **OOXML**
  - Owning plot family.

- **IR**
  - `ChartSeriesInfo.chart_type: `str``

- **Parsing**
  - Same mapping as chart_type; retained with plot ownership.

### `name`

- **Output**
  - Resource/summary series name.

- **OOXML**
  - c:ser/c:tx or cx:series/cx:tx.

- **IR**
  - `ChartSeriesInfo.name: `str``

- **Parsing**
  - Concatenate a:t then strip; fallback first descendant local-name v with text; omit if empty.

### `categories`

- **Output**
  - Resource category strings.

- **OOXML**
  - c:cat (fallback c:xVal); ChartEx strDim[@type="cat"].

- **IR**
  - `ChartSeriesInfo.categories: `list[str]``

- **Parsing**
  - ChartML multiLvlStrCache wins, otherwise read the category source's direct numLit/strLit points or numRef/numCache and strRef/strCache. Numeric categories remain saved strings. Multi-level labels join nonempty levels at each point with ` / `. ChartEx strDim joins cx:lvl similarly.

- **Absence and defaults**
  - Empty list.

### `values`

- **Output**
  - Resource saved value strings.

- **OOXML**
  - c:val (fallback c:yVal); ChartEx numDim.

- **IR**
  - `ChartSeriesInfo.values: `list[str]``

- **Parsing**
  - Read the first recognized direct source: numLit/strLit supplies its own indexed points; numRef/strRef supplies its matching direct numCache/strCache when saved. An absent cache is not populated by evaluating a formula, opening an embedded workbook, or searching unrelated descendant extension data.
  - ChartEx uses nonempty val, then y, then the first numeric dimension. Preserve saved zeros, negatives, empty point positions, and lexical value strings. The same arrays drive previews, point counts, numeric min/max and full resource data.

- **Absence and defaults**
  - Empty list.

### `x_values`

- **Output**
  - Resource x coordinate strings.

- **OOXML**
  - c:xVal literal points or reference cache; cx:numDim[@type="x"].

- **IR**
  - `ChartSeriesInfo.x_values: `list[str]``

- **Parsing**
  - Use indexed literal/cache/dimension values; omit empty list.

### `y_values`

- **Output**
  - Resource y coordinate strings.

- **OOXML**
  - c:yVal literal points or reference cache; cx:numDim[@type="y"].

- **IR**
  - `ChartSeriesInfo.y_values: `list[str]``

- **Parsing**
  - Use indexed literal/cache/dimension values; omit empty list.

### `bubble_sizes`

- **Output**
  - Resource bubble size strings.

- **OOXML**
  - c:bubbleSize literal points or reference cache; cx:numDim[@type="size"].

- **IR**
  - `ChartSeriesInfo.bubble_sizes: `list[str]``

- **Parsing**
  - Use indexed literal/cache/dimension values; omit empty list.

### `preview`

- **Output**
  - Readable series summary.

- **OOXML**
  - Category/value arrays.

- **IR**
  - `ChartSeriesInfo.preview: `str``

- **Parsing**
  - First min(point_count,8) positions; category fallback is 1-based ordinal string. Nonempty value → `category=value`, otherwise category. Join with `; `.

### `min`

- **Output**
  - Resource numeric minimum.

- **OOXML**
  - values.

- **IR**
  - `ChartSeriesInfo.min: `float``

- **Parsing**
  - Convert each value with float(); ignore ValueError; take min when at least one conversion succeeds. No finite-number filter.

### `max`

- **Output**
  - Resource numeric maximum.

- **OOXML**
  - values.

- **IR**
  - `ChartSeriesInfo.max: `float``

- **Parsing**
  - Same conversion as min; take max.

### `formula`

- **Output**
  - Resource formula text.

- **OOXML**
  - First c:f below value source; ChartEx val/y dimension cx:f.

- **IR**
  - `ChartSeriesInfo.formula: `str``

- **Parsing**
  - Copy nonempty formula; do not calculate.

### `category_formula`

- **Output**
  - Resource category formula text.

- **OOXML**
  - First c:f below category source; ChartEx cat dimension cx:f.

- **IR**
  - `ChartSeriesInfo.category_formula: `str``

- **Parsing**
  - Copy nonempty formula.

### `hidden`

- **Output**
  - Resource hidden-series flag.

- **OOXML**
  - ChartEx cx:series/@hidden.

- **IR**
  - `ChartSeriesInfo.hidden: `bool``

- **Parsing**
  - Store true for 1/true/True. ChartML path supplies false, which is omitted.
