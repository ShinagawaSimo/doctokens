# Chart series

[COMMON](README.md) / Chart series

Each field belongs to ChartSeriesInfo.

## Processing

Saved points use the same indexed reader for literal data and reference caches. Enumerate direct pt children; int(idx) or enumeration index on missing/malformed idx. A duplicate index replaces its preceding value. Prefer the direct v child's text, including an explicitly empty v; otherwise use direct point text, as in ChartEx. Formatting whitespace around a v child is not a point value. Return positions 0..max(index), filling holes with empty strings; declared ptCount does not manufacture points or set list length. ChartEx numeric dimensions use their last lvl. ChartEx dataId resolves a catalog of chartData/data; later duplicate IDs replace earlier records.

Recognized scatter/bubble series expose only their x/y/bubble-size caches; category/value aliases are removed before reading projection. Other supported layouts retain their saved dimensions.

## Fields

### `labels`

- **Output**
  - series/label with zero-based index, optional deleted state and saved text.
    label-options retains defined content visibility and saved separator text.
    Pure label position is not extracted or serialized.
- **OOXML**
  - c:dLbls/c:dLbl/c:idx and c:tx rich text/strRef cache.
    c15:datalabelsRange/c15:dlblRangeCache/c:pt supplies explicitly indexed
    range labels (DrawingML 2012 chart namespace).
    ChartEx dataLabels/dataLabel/dataLabelHidden retains indices, hidden state
    and the defined seriesName/categoryName/value visibility declarations.
- **Parsing**
  - Direct labels override plot defaults and saved range text at that index.
    Preserve paragraph/soft-break text. Do not open external workbooks or
    generate numeric/percentage labels from visibility flags.
  - DOCX/PPTX/XLSX XML previews retain at most eight labels for shown points in
    the first eight series, within the shared annotation/character budget.
    Full resources retain all recovered saved text. Plain keeps its bounded
    chart summary; source annotation settings do not expand it.
  - Missing saved automatic/reference results add no generated text, new
    placeholder or diagnostic. Empty text without a state/visibility declaration
    contributes no reading label. The reader does not fetch external results
    or generate displayed numbers/percentages from flags.

### `label_options`

- **Output**
  - series/label-options and label/label-options in XML previews and resources.
- **Source**
  - ChartML showLegendKey/showVal/showCatName/showSerName/showPercent/showBubbleSize,
    separator, and supported c15:showDataLabelsRange; ChartEx visibility fields.
- **Parsing**
  - Use a closed set. Normalize saved 1/true and 0/false to true/false, including
    explicit false overrides. ChartEx seriesName/categoryName/value map to
    showSerName/showCatName/showVal. Unknown attributes are not retained.
  - These declarations identify displayed content kinds, not recovered values.
    A display flag must never be interpreted as the actual label text.

### `trendlines`

- **Output**
  - series/trendline: saved type, name, order/period, forward/backward, intercept,
    display-equation/display-r-squared and label when available.
- **OOXML**
  - c:trendline and c:trendlineLbl/c:tx.
- **Parsing**
  - Read saved configuration/text only. A saved y=2x+1 remains readable;
    an enabled equation without saved text never causes fitting/reconstruction.
    Preserve all saved label text, including a saved R² value and line breaks;
    no numerical value is inferred from the display boolean. Normalize display
    booleans to true/false and preserve explicit false. Missing generated text
    adds no extra status/unsupported marker in this contract.
  - All three formats' XML previews cap at eight trendlines within the common
    annotation/character budget; complete resources retain all recovered text.
- **References**
  - ISO/IEC 29500-1 §§21.2.2.43–44 define display-equation/display-r-squared as
    display booleans, and §21.2.2.212 defines the separate saved trendline label.
  - [Excel Trendline.DisplayRSquared](https://learn.microsoft.com/en-us/office/vba/api/excel.trendline.displayrsquared)
    and [DisplayEquation](https://learn.microsoft.com/en-us/office/vba/api/excel.trendline.displayequation)
    confirm that these values can appear together in the chart's data label.

### `axis_ids`

- **Output**
  - series/@axes for explicit ChartEx axis references.
- **OOXML**
  - cx:series/cx:axisId.
- **Parsing**
  - Preserve reference order while mapping to uniquely declared chart-local
    axisN IDs under the [axis identity](chart.md#axis-identity) rule. Unknown or
    ambiguous targets add no guessed link; matching axis metadata supplies meaning.

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
  - ChartEx uses nonempty val, then y, then the first numeric dimension. Preserve saved zeros, negatives, empty point positions, and lexical value strings. The same saved arrays drive previews, position counts and complete point resources. No float summary is calculated.

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
