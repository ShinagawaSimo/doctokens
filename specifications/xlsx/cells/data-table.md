# Data table formulas

[XLSX](../README.md) / Data table formulas

A What-If data table substitutes trial values into one or two model input cells and saves the results of reevaluating the model. It is separate from an Excel Table (ListObject). Parsing reconstructs its formula description and reads saved values; it does not perform substitutions, recalculate formulas, or guarantee that caches are current.

## Fields

### `formula`

- **Output**
  - `cell/@formula` in structural and semantic DTX, together with `formula-type="dataTable"` and `formula-range`.
  - Example: `<cell formula="TABLE(,B1)" formula-range="D2:D3" formula-type="dataTable">6</cell>`.
- **OOXML**
  - `s:f[@t="dataTable"]/@dt2D`, `@dtr`, `@r1`, `@r2`, `@del1`, and `@del2` on the master cell.
  - The expression is reconstructed from attributes, not copied from the element's text.
- **IR**
  - `Cell.formula: str` on each existing result member retained by the parse selection.
- **Parsing**
  - If `dt2D` is true, emit `TABLE(r2,r1)`: the row input is the first argument and the column input is the second. `dtr` does not apply.
  - Otherwise, emit `TABLE(r1,)` when `dtr` is true, or `TABLE(,r1)` when it is false. `r2` and `del2` do not apply.
  - A true `del1` or applicable `del2` replaces that input with `#REF!`, even if its saved address is missing or obsolete. It does not replace the cached result with an error.
  - Accept XML boolean spellings `true`, `false`, `1`, and `0`; absent boolean attributes default to false.
  - Validate required live input references against worksheet bounds. A missing input is not an empty TABLE argument: empty arguments identify the unused axis of a one-variable table.
  - Do not translate references for subsequent members as if they were shared formulas.
- **Diagnostics**
  - `DATA_TABLE_FORMULA_INVALID` if an applicable input or boolean is invalid. Preserve saved values and known type/range, but omit reconstructed formula text.
- **Notes**
  - No leading `=` or display braces are emitted.
  - Raw `dt2D/dtr/r1/r2/del1/del2` attributes are not duplicated in DTX.
  - Result members omit `raw`; their cached values are not literal formula-bar content. Any provisional `XLSX_FORMULA_BAR_UNAVAILABLE` warning for such a cache is removed when the group is resolved.

### `formulaType`

- **Output**
  - `cell/@formula-type="dataTable"`.
- **OOXML**
  - `s:f/@t="dataTable"` on the master.
- **IR**
  - `Cell.formulaType: str` on the master and retained members of a valid result range.
- **Parsing**
  - Collect declarations across the selected worksheet, including masters outside a requested cell window.
  - Do not create missing cells or pull unselected values into the result.
  - Retain the type even when reconstruction fails.

### `formulaRange`

- **Output**
  - `cell/@formula-range` identifies the original result group, not the requested read window.
- **OOXML**
  - `s:f[@t="dataTable"]/@ref`; the master is the top-left cell of this range.
- **IR**
  - `Cell.formulaRange: str` on retained members.
- **Parsing**
  - Require an ordered cell range within worksheet bounds, starting at the master. A single-cell reference is accepted.
  - DTX emits the valid formula/type/range triplet on the first non-shadow member in each rendered grid and suppresses repeated triplets for the same range and formula. Rendering does not mutate cell IR.
  - Selecting only `D3:D3` from a `D2:D3` group still emits `formula-range="D2:D3"` on D3. This does not make D3 the OOXML master.
  - For a column-oriented one-variable table, source formulas are immediately above the result range and trial values are immediately to its left. For a row-oriented table, source formulas are immediately to its left and trial values immediately above. A two-variable table uses the single source formula diagonally above-left and trial values on both edges.
  - A rectangular range does not imply two variables: one-variable tables can evaluate multiple source formulas.
- **Diagnostics**
  - `DATA_TABLE_FORMULA_INVALID` if the range is missing, invalid, or does not start at the master. Preserve its saved nonempty text on the master, but do not infer membership from it.
  - Conflicting declarations or independent formulas in selected result cells prevent reconstruction of the affected groups; explicit cell formulas are not overwritten.
  - Emit one warning per affected declaration at `worksheet-part!first-selected-member`. Declarations unrelated to selected cells do not warn.

## Evidence and validation limits

ISO/IEC 29500-1 §18.3.1.40 defines the data-table attributes and §18.3.1.96 defines cached values. [Microsoft's data-table guide](https://support.microsoft.com/en-us/excel/calculate-multiple-results-by-using-a-data-table) describes the layouts and substitution behavior. The two-input argument order and deleted-input spelling are supported by the [ClosedXML formula reconstruction](https://github.com/ClosedXML/ClosedXML/blob/develop/ClosedXML/Excel/Cells/XLCellFormula.cs) and [attribute serialization](https://github.com/ClosedXML/ClosedXML/blob/develop/ClosedXML/Excel/IO/WorksheetPartWriter.cs) implementations; they are not quoted as explicit ISO parameter-order requirements.

The repository's native `xlsx-formula-data-table.xlsx` verifies a column-oriented one-variable group, its saved results, and selections excluding its master. Native horizontal, multiple-formula, two-variable, and deleted-input workbooks remain to be added; the implemented generalizations are not yet verified by those native fixtures.

## Source references

- [Data table decoding and membership](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/data_tables.py)
- [Worksheet scanning](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py)
- [DTX group compaction](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py)
