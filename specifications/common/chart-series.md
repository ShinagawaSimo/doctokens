# Chart series

[COMMON](README.md) / Chart series

Each field belongs to ChartSeriesInfo.

## Processing

Saved points use the same indexed reader for literal data and reference caches. Enumerate direct pt children; int(idx) or enumeration index on missing/malformed idx. A duplicate index replaces its preceding value. Prefer the direct v child's text, including an explicitly empty v; otherwise use direct point text, as in ChartEx. Formatting whitespace around a v child is not a point value. Return positions 0..max(index), filling holes with empty strings; declared ptCount does not manufacture points or set list length. ChartEx numeric dimensions use their last lvl. ChartEx dataId resolves a catalog of chartData/data; later duplicate IDs replace earlier records.

## Fields

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
  - 1-based plot index; retained for combination charts only.

### `chart_type`

- **Output**
  - Resource series family.

- **OOXML**
  - Owning plot family.

- **IR**
  - `ChartSeriesInfo.chart_type: `str``

- **Parsing**
  - Same mapping as chart_type; retained for combination charts only.

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
