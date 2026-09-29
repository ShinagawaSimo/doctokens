# Chart series

[COMMON](README.md) / Chart series

Each field belongs to ChartSeriesInfo.

## Processing

Cache points: enumerate direct pt children; int(idx) or enumeration index on missing/malformed idx. A duplicate index replaces its preceding value. Value is point.text, else first descendant v, else empty. Return positions 0..max(index), filling holes with empty strings; declared ptCount does not set length. ChartEx numeric dimensions use their last lvl. ChartEx dataId resolves a catalog of chartData/data; later duplicate IDs replace earlier records.

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
  - ChartML multiLvlStrCache wins, otherwise numeric/string cache. Multi-level labels join nonempty levels at each point with ` / `. ChartEx strDim joins cx:lvl similarly.

- **Absence and defaults**
  - Empty list.

### `values`

- **Output**
  - Resource cached value strings.

- **OOXML**
  - c:val (fallback c:yVal); ChartEx numDim.

- **IR**
  - `ChartSeriesInfo.values: `list[str]``

- **Parsing**
  - ChartML first numCache, fallback strCache. ChartEx nonempty val, then y, then first numeric dimension. ChartML numLit/strLit do not populate the cache path.

- **Absence and defaults**
  - Empty list.

### `x_values`

- **Output**
  - Resource x coordinate strings.

- **OOXML**
  - c:xVal cache; cx:numDim[@type="x"].

- **IR**
  - `ChartSeriesInfo.x_values: `list[str]``

- **Parsing**
  - Use indexed cache/dimension values; omit empty list.

### `y_values`

- **Output**
  - Resource y coordinate strings.

- **OOXML**
  - c:yVal cache; cx:numDim[@type="y"].

- **IR**
  - `ChartSeriesInfo.y_values: `list[str]``

- **Parsing**
  - Use indexed cache/dimension values; omit empty list.

### `bubble_sizes`

- **Output**
  - Resource bubble size strings.

- **OOXML**
  - c:bubbleSize cache; cx:numDim[@type="size"].

- **IR**
  - `ChartSeriesInfo.bubble_sizes: `list[str]``

- **Parsing**
  - Use indexed cache/dimension values; omit empty list.

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


## Source references

- [ChartParser._parse_chartml_series](../../packages/ooxml_llm_core/src/ooxml_llm_core/chart_ml.py#L169)
- [ChartParser._parse_chartex](../../packages/ooxml_llm_core/src/ooxml_llm_core/chart_ml.py#L207)
- [_indexed_point_values](../../packages/ooxml_llm_core/src/ooxml_llm_core/_chart_values.py#L102)
- [_series_row](../../packages/ooxml_llm_core/src/ooxml_llm_core/chart_ml.py#L313)
