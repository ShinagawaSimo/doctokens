# Stored-content API

[XLS](README.md) / Content

## `read_xls_content`

- **Source**
  - `doctokens_excel.read_xls_content(source, *, limits=None)` accepts a path
    or complete immutable file bytes.
  - A CFB version 3 root-owned `Workbook` stream with BIFF8 BOF version `0x0600`.
- **Output**
  - `XlsContent(sheets, date_1904, warnings)`; all source handles close before return.
  - `XlsSheet(name, state, cells)` preserves workbook tab order and hidden state.
  - `XlsCell(row, column, kind, value, xf_index, from_formula)` uses one-based
    coordinates. `ref` derives the A1 address. Cells are ordered by row and column.
  - Content and collections are frozen dataclasses/tuples. They are values, not
    a DTP/DTX projection. Existing `parse_xlsx` output contracts remain format-specific.
- **Parsing**
  - Read BoundSheet8, shared strings and Date1904 from workbook globals.
  - Decode SST/Continue with separate character, formatting-run and extension
    states. BIFF8 compressed Unicode stores low bytes, not system-codepage text.
  - Validate string headers within their record. Skip rich-text and phonetic
    annotation bytes without constructing annotation models. Decode a complete
    string's UTF-16 units together to preserve cross-fragment surrogate pairs.
  - Read ordinary worksheets including hidden sheets. Skip chart/macro/other
    sheet types and dialog sheets with `XLS_SHEET_TYPE_UNSUPPORTED` warnings.
  - Skip nested BOF/EOF substreams within a worksheet; maximum nested depth is 32.
  - Read LabelSst, Number, RK, MulRk and BoolErr into a sparse cell map.
  - Read Formula's saved numeric/boolean/error/empty-string result. A string
    result is associated with its subsequent String record, allowing the recognized
    shared/array/table helper records in between. Missing results fail.
  - Preserve existing formula empty strings as cells; omit Blank/MulBlank style-only cells.
  - Validate coordinates, shared-string indexes, result discriminators, Xnum and
    BErr. Reject duplicate cell coordinates and unsupported inline Label/RString.
  - Numbers are saved numeric values, without XF display formatting. Dates remain
    serial numbers; `date_1904` and `xf_index` retain interpretation metadata.
  - Do not calculate formulas, reconstruct their expressions, refresh external
    links, execute macros, parse objects, or construct merged/style/rule/pivot models.
- **Diagnostics**
  - `XlsError`: invalid input, unsupported version/encoding/record, encryption,
    damaged data or configured excess. Underlying CFB errors are chained.
  - Detect FilePass and reject traditional encrypted XLS; reject CFB-wrapped
    encrypted OOXML identified by EncryptionInfo and EncryptedPackage.
  - Cancellation propagates independently of content errors.

## `XlsLimits`

- **Defaults**
  - `cfb`: the defaults of `CfbLimits`.
  - `max_sheets = 256`; `max_records = 1000000`; `max_cells = 500000`.
  - `max_strings = 500000`; `max_string_characters = 32767` UTF-16 units.
  - `max_total_string_characters = 16000000` UTF-16 units.
- **Parsing**
  - Positive integers only; reject booleans. Counters cover all parsed sheets.
  - BIFF payload size is at most 8224 bytes. The reader uses a bounded 64-KiB
    logical read buffer, but retains decoded SST strings and the result content.
  - These bounds do not promise constant memory or a hard RSS ceiling.
- **Diagnostics**
  - Invalid limit argument: `ValueError`.

## Example

```python
from doctokens_excel import read_xls_content

content = read_xls_content("saved.xls")
for sheet in content.sheets:
    for cell in sheet.cells:
        print(sheet.name, cell.ref, cell.kind, cell.value)
```

## References

- [MS-XLS](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/):
  Workbook Stream, BOF/EOF, BoundSheet8, SST/Continue, basic cell records and FormulaValue.
