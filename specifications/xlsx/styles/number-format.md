# Display number formats

[XLSX](../README.md) / Display number formats

Display formatting is a compact date/percentage projection.

## Fields

### `numFmtId`

- **Output**
  - Determines display interpretation.

- **OOXML**
  - styles.xml cellXfs/xf/@numFmtId.

- **IR**
  - `FormatIndex._cell_formats[style_index][0]: int`

- **Parsing**
  - Parse integer; custom numFmts map ID to formatCode. Builtin dates:14..22,27..36,45..47,50..58,71..81. Builtin percentages:9,10.

### `formatCode`

- **Output**
  - Date/percentage recognition.

- **OOXML**
  - numFmt/@formatCode.

- **IR**
  - `FormatIndex._cell_formats[style_index][1]: str`

- **Parsing**
  - Date: ignore quoted literals and non-elapsed bracket sections, then match y/m/d/h/s or AM/PM,A/P,[h],[m],[s]. Percentage: any % in original code. Date wins. General decimals/currency/localized rendering is not applied.

### `date1904`

- **Output**
  - Date epoch.

- **OOXML**
  - workbookPr/@date1904.

- **IR**
  - `FormatIndex.date_1904: bool`

- **Parsing**
  - `@date1904 == "1"` selects the 1904 system; every other value selects the 1900 system.
  - 1904 system: `(datetime(1904, 1, 1) + timedelta(days=int(serial))).date().isoformat()`.
  - 1900 system: `serial <= 0` returns `str(serial)`. Otherwise set `ordinal = int(serial)`; `ordinal == 60` returns `"1900-02-29"`. For `ordinal > 60`, subtract one before adding that many days to `1899-12-31`.
  - Fractional time is discarded.

### `text`

- **Output**
  - Cell display text.

- **OOXML**
  - Numeric cell v with explicit s.

- **IR**
  - `Cell.text: str`

- **Parsing**
  - float(raw); failed conversion keeps raw. Percent → `f"{num * 100:g}%"`. Date → ISO date. No format match → raw. Missing styles → raw.


## Source references

- [FormatIndex.format_value](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/index.py#L185)
- [FormatIndex._resolve](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/index.py#L245)
- [_decode_date](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/styles/index.py#L487)
- [_formatted_text](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L660)
