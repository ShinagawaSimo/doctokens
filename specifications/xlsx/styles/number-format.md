# Display number formats

[XLSX](../README.md) / Display number formats

Display formatting applies the effective Excel number format from the cell XF to the saved cell value. The parser uses the explicit workbook locale (default `zh-CN`) and does not evaluate formulas. The displayed text and formula-bar text are separate concepts: `<v>` is not itself the formula-bar string.

## Fields

### `numFmtId`

- **Output**
  - Determines the effective display format.

- **OOXML**
  - `styles.xml/cellXfs/xf/@numFmtId` and, for custom IDs, `styles.xml/numFmts/numFmt`.

- **IR**
  - `FormatIndex._cell_formats[style_index][0]: int`

- **Parsing**
  - Parse the integer and map custom IDs to `formatCode`. Resolve `cellXfs/xf/@xfId` through `cellStyleXfs` and honor `applyNumberFormat`. Built-in IDs without a `numFmt` element use the explicit locale table. IDs whose language-specific code is not specified by the target evidence remain parameterized rather than guessed.

### `formatCode`

- **Output**
  - Controls the displayed text when the saved value is numeric and the cell has a format.

- **OOXML**
  - `styles.xml/numFmts/numFmt/@formatCode`; built-in formats are selected by `numFmtId`.

- **IR**
  - `FormatIndex._cell_formats[style_index][1]: str`

- **Parsing**
  - Split sections only at semicolons outside quoted text and bracket directives. Select conditional sections first, then positive/negative/zero/text sections. Ignore quoted literals, escapes, color/condition/locale brackets, and `DBNum` directives while detecting date tokens. Recognize `y`, `m`, `d`, `h`, `s`, `AM/PM`, `A/P`, and elapsed `[h]`, `[m]`, `[s]`. An `m/mm` token after hours or before seconds is minutes; otherwise it is a month.
  - Percent sections multiply the value by 100. Numeric sections apply `0`, `#`, `?`, grouping commas, scaling commas, and decimal rounding. `0` pads a required zero and `?` pads an insignificant position with a space; a fraction such as `# ??/??` must never turn those positions into visible zeroes. Currency and other literal text are retained from the selected section. Scientific notation requires an uppercase `E+` or `E-` marker; fractions require numeric placeholders around `/`. Unsupported tokens preserve the saved value instead of inventing a display.
  - Named color directives such as `[Red]` are removed from display text and, in semantic XML, expose the selected section color through the cell's semantic `color` attribute. Condition directives select a section by the saved numeric value; if no condition matches, the parser keeps the saved value as a safe display fallback rather than selecting a failed condition.

### `date1904`

- **Output**
  - Selects the workbook date epoch.

- **OOXML**
  - `workbook.xml/workbookPr/@date1904`.

- **IR**
  - `FormatIndex.date_1904: bool`

- **Parsing**
  - `@date1904` values `1`, `true`, and `on` select the 1904 system; other values select the 1900 system. The 1904 system uses 1904-01-01 as the serial-zero base. The 1900 path follows the OOXML base for negative serials, applies Excel's historical offset for ordinary positive dates, and exposes serial 60 as the Office-visible compatibility date 1900-02-29. Keep the integer day, seconds, and fractional seconds separate; do not discard the fractional time.
  - Render date/time tokens from the effective format code. A pure time format emits only time, while a combined date/time format retains both.

### `text`

- **Output**
  - Cell display text.

- **OOXML**
  - Numeric cell `v` with an effective style.

- **IR**
  - `Cell.text: str`

- **Parsing**
  - Read the saved value once and convert only as needed for deterministic format operations. Failed conversion or an unsupported format keeps the saved value as the display text. Plain output emits only this display text. Structural and semantic DTX may also emit a reliably reconstructed formula-bar `raw` value when it differs.

### `raw`

- **Output**
  - Structural and semantic DTX `cell/@raw` when a non-formula cell's reliably reconstructed formula-bar value differs from `Cell.text`.

- **OOXML**
  - Decoded text for shared strings or inline strings, or a deterministic reconstruction from the numeric value and effective format. Formula caches are not formula-bar values.

- **IR**
  - `Cell.raw: str`

- **Parsing**
  - Preserve decoded text before applying a supported text section. For ordinary numeric formats, emit the edit-form value only when it is independently recoverable. A supported uppercase scientific display token (`E+`/`E-`) is formatting syntax and does not by itself prevent recovery of the saved ordinary number. Omit it and add `XLSX_FORMULA_BAR_UNAVAILABLE` when the format needs Excel-specific rendering or would require guessing. Formula cells expose `<f>` through `formula` and do not copy the cached `<v>` into `raw`.
  - Numeric reconstruction supports `zh-CN` and `en-US`, up to 15 significant decimal digits, and zero or magnitudes from `1e-9` inclusive to `1e15` exclusive. These limits also apply to scientific display formats. For example, saved `123456` with `0.00E+00` produces `<cell raw="123456">1.23E+05</cell>`; `raw` retains the unrounded number rather than reconstructing it from the rounded display.

## Source references

- [FormatIndex.format_value](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/index.py#L80)
- [parse_styles](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/parser.py#L17)
- [format_value](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/number_format.py#L17)
- [_parse_cell](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/cells.py#L42)
- [_cell_attrs](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L156)
