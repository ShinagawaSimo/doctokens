# Conditional formatting

[XLSX](../README.md) / Conditional formatting

Rules describe conditions and formatting; they do not calculate effective per-cell styles.
Both XML densities retain conditions, valid priorities and stop behavior.
Only semantic emits resolved reading styles and visual details, independently
of whether a one-shot parse or a session supplied the IR. No public dxf index
is emitted. Differential alignment is outside the reading projection.

## Processing

Read both core s:conditionalFormatting and worksheet-extension
x14:conditionalFormattings/x14:conditionalFormatting. The namespaces are
s=SpreadsheetML/main, x14=`http://schemas.microsoft.com/office/spreadsheetml/2009/9/main`,
and xm=`http://schemas.microsoft.com/office/excel/2006/main`.
Extended ranges use direct xm:sqref; expressions use direct xm:f.

When a core rule's extLst/ext/x14:id matches an x14:cfRule/@id
(case-insensitive), merge only that explicitly linked representation.
Keep the core priority/conditions when the extension omits them; overlay
saved extension attributes and merge visual-detail keys. Emit one effective
rule, without the decoder's source ID. Independent extension rules remain
separate and in saved order. No positional or similar-formula matching occurs.

## Fields

### `ranges`

- **Output**
  - conditional-format/@ref

- **OOXML**
  - `s:conditionalFormatting/@sqref`; x14:conditionalFormatting/xm:sqref.

- **IR**
  - `ConditionalFormat.ranges`

- **Parsing**
  - Copy, default empty; one container per parsed rule.

### `priority`

- **Output**
  - rule/@priority

- **OOXML**
  - `s:cfRule/@priority`

- **IR**
  - `ConditionalFormat.priority`

- **Parsing**
  - int; missing, zero and negative values are omitted. Source order is retained
    without priority sorting; no invented priority is added.

### `ruleType`

- **Output**
  - rule/@type

- **OOXML**
  - `s:cfRule/@type`

- **IR**
  - `ConditionalFormat.ruleType`

- **Parsing**
  - Copy, default empty.

### `formulas`

- **Output**
  - rule/@formula or @formulas

- **OOXML**
  - `s:cfRule/s:formula/text()`; x14:cfRule/xm:f.

- **IR**
  - `ConditionalFormat.formulas`

- **Parsing**
  - One → formula; several → join with ` | ` as formulas; none → omit.


### `stopIfTrue`

- **Output**
  - rule/@stop-if-true

- **OOXML**
  - `s:cfRule/@stopIfTrue`

- **IR**
  - `ConditionalFormat.stopIfTrue`

- **Parsing**
  - XML boolean 1/true → true, 0/false → false; DTX omits false.

### `operator`

- **Output**
  - rule/@operator

- **OOXML**
  - `s:cfRule/@operator`

- **IR**
  - `ConditionalFormat.operator`

- **Parsing**
  - Copy nonempty.

### `text`

- **Output**
  - rule/@text

- **OOXML**
  - `s:cfRule/@text`

- **IR**
  - `ConditionalFormat.text`

- **Parsing**
  - Copy nonempty.

### `rank`

- **Output**
  - rule/@rank

- **OOXML**
  - `s:cfRule/@rank`

- **IR**
  - `ConditionalFormat.rank`

- **Parsing**
  - Nonempty → int, failure 0.

### `percent`

- **Output**
  - rule/@percent

- **OOXML**
  - `s:cfRule/@percent`

- **IR**
  - `ConditionalFormat.percent`

- **Parsing**
  - Store/output only true for XML boolean 1/true.

### `formatKind`

- **Output**
  - rule/@format only when it differs from rule/@type.

- **OOXML**
  - Core or x14 cfRule/colorScale, dataBar, iconSet.

- **IR**
  - `ConditionalFormat.formatKind`

- **Parsing**
  - First recognized child local name.

### `formatDetails`

- **Output**
  - Semantic rule/@details

- **OOXML**
  - The child selected by `formatKind`.

- **IR**
  - `ConditionalFormat.formatDetails`

- **Parsing**
  - See [visual rules](visual-format.md). Serialize scalar key=value; stops/thresholds records use colon-separated fields and semicolon-separated entries; then join top-level items with semicolon.

### `dxfStyle`

- **Output**
  - Semantic rule/@style; structural never emits it.

- **OOXML**
  - `xl/styles.xml`: `s:styleSheet/s:dxfs/s:dxf`, selected by zero-based `dxfId`.

- **IR**
  - `ConditionalFormat.dxfStyle`

- **Parsing**
  - Resolve core dxfId through the format index. Extended direct
    x14:dxf uses its SpreadsheetML font/fill/numFmt children through the same
    compact differential-style reader. Retain explicit emphasis changes,
    resolved font/fill colors and number formats; omit alignment and layout.
    The source index is used during decoding and is not retained in the rule.

### `aboveAverage`

- **Output**
  - rule/@above-average=false for below-average conditions; omit true.
- **OOXML**
  - cfRule/@aboveAverage in either namespace.
- **Parsing**
  - Default true; honor an explicit false.

### `equalAverage`

- **Output**
  - @equal-average=true when enabled.
- **OOXML**
  - cfRule/@equalAverage.
- **Parsing**
  - Default false.

### `bottom`

- **Output**
  - @bottom=true for bottom-ranked conditions.
- **OOXML**
  - cfRule/@bottom.
- **Parsing**
  - Default false; keep it distinct from top ranking.

### `stdDev`

- **Output**
  - @std-dev.
- **OOXML**
  - cfRule/@stdDev.
- **Parsing**
  - Retain a nonzero saved integer; do not calculate the sample deviation.

### `timePeriod`

- **Output**
  - @time-period.
- **OOXML**
  - cfRule/@timePeriod.
- **Parsing**
  - Retain the saved discriminator without using the current clock to
    evaluate the rule.

### `unparsed`

- **Output**
  - An existing unreadable rule contains
    `<unsupported type="conditional-format"/>`.
    Plain emits `[Unparsed conditional format]` for that failed declaration.
- **Diagnostics**
  - CONDITIONAL_FORMAT_UNSUPPORTED for unknown rule/list content or missing
    required type/range/body. RULE_BOOLEAN_INVALID uses the scalar default.
- **Parsing**
  - Conditions with readable cached cell values never replace those values
    by calculated formatting. Unknown elements are not silently treated as
    empty rules. Optional attribute/default fallback alone adds no placeholder.
