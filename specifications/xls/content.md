# Stored-content API

[XLS](README.md) / Content

## `read_xls_content`

- **Source**
  - `doctokens_excel.read_xls_content(source, *, limits=None, locale="zh-CN")` accepts a path
    or complete immutable file bytes.
  - A CFB version 3 root-owned `Workbook` stream with BIFF8 BOF version `0x0600`.
- **Output**
  - `XlsContent(sheets, date_1904, warnings)`; all source handles close before return.
  - `XlsSheet(name, state, cells)` preserves workbook tab order and hidden state.
  - `XlsCell(row, column, kind, value, xf_index, from_formula, display_text)` uses one-based
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
  - `value` retains saved numeric values, including date/time serials;
    `display_text` supplies the supported reading display.
  - Do not calculate formulas, reconstruct their expressions, refresh external
    links, execute macros, parse objects, or construct merged/style/rule/pivot models.
- **Diagnostics**
  - `XlsError`: invalid input, unsupported version/encoding/record, encryption,
    damaged data or configured excess. Underlying CFB errors are chained.
  - Unsupported numeric display: one `XLS_NUMBER_FORMAT_UNSUPPORTED` warning per
    encountered format identifier; retain the saved number in `display_text`.
  - Detect FilePass and reject traditional encrypted XLS; reject CFB-wrapped
    encrypted OOXML identified by EncryptionInfo and EncryptedPackage.
  - Cancellation propagates independently of content errors.

## `XlsCell.display_text`

- **Source**
  - Cell `ixfe` indexes the Globals XF collection, including style XFs.
  - XF (`0x00E0`) has a 20-byte BIFF8 payload; `ifmt` is at offset 2,
    `fStyle` is bit 2 of the word at offset 4, and `ixfParent` is bits 4–15.
  - Format (`0x041E`) contains `ifmt:u16` and `stFormat:XLUnicodeString`:
    `cch:u16`, `fHighByte` in bit 0, then compressed Unicode or UTF-16LE.
- **Parsing**
  - Preserve XF record order. Reject missing/style cell references, invalid
    parent style references, duplicate Format identifiers and malformed payloads.
  - Format strings contain 1–255 UTF-16 units. Accept identifiers 5–8, 23–26,
    41–44, 63–66 and 164–392 as specified by MS-XLS 2.4.126.
  - A saved Format code takes precedence, including localized built-in IDs such
    as 7. Do not substitute a US dollar template for a saved yuan format.
  - Read a cell XF's saved `ifmt`. CellXF `fAtrNum` controls later updates when
    a parent style changes; it does not replace the saved `ifmt` during reading.
  - General preserves the saved number's precision; XLS omits a redundant `.0`
    for integral values. It does not shorten values to Excel's visual width.
    XLS uses a round-trip representation of binary64 values; XLSX can retain a
    longer XML numeric spelling for the same binary value.
    Fixed-point number, percentage and currency
    formats support precision, section selection, signs/parentheses and literals.
    `0` keeps required zeroes, `#` omits optional zeroes, and `?` retains alignment
    spaces. Decimal rounding uses the shared engine's decimal half-up rule.
  - Commas inside the integer placeholders group thousands. Scaling commas
    divide by 1000 per comma. Each unquoted/unescaped `%` multiplies by 100;
    a quoted or escaped percent sign remains a literal without scaling.
    Named color directives are skipped; no color/style model is produced here.
  - XLS and XLSX use the same `doctokens_excel.formatting.display` dispatcher,
    with separate decimal, fraction, scientific, Chinese and date algorithms.
    Number syntax and decimal operations are compiled within the workbook owner.
    Unknown directives, unbalanced syntax and more than four sections are unsupported.
    Unsupported syntax
    returns an explicit unavailable result rather than guessing a display.
    A supported format may legitimately render the same text as the saved value;
    equality alone does not mean the format is unsupported.
  - Never normalize currency symbol code points using locale. A saved `¥`
    (U+00A5) remains `¥`; a saved `￥` (U+FFE5) remains `￥`.
    `[$<Currency String>-<language info>]` preserves its currency string.
  - `locale` affects built-in fallback resolution, not saved literal characters.
    Locale-dependent built-ins without a saved code remain unsupported rather
    than borrowing an unrelated currency. Missing custom Format records fail.
  - String cells apply a fourth text section, or a single section containing
    `@`, without converting the stored value or type. Repeated `@` tokens each
    insert the original string. Empty formula results remain existing cells.
    Boolean/error values retain their own display rather than numeric formatting.
    Booleans use `TRUE`/`FALSE`; the parser always fills `display_text`.
- **Example**
  - Saved value `1234.5`, XF 62 → `ifmt=7`, and saved code
    `"¥"#,##0.00;"¥"\-#,##0.00` produce `display_text="¥1,234.50"`.
  - Saved value `0.125` and code `0.0%` produce `display_text="12.5%"`.

## Additional numeric format families

### Fraction patterns

- **Output**
  - Improper or mixed fractions, fixed denominators, required zeroes and literal affixes.
- **Parsing**
  - Placeholder denominators use the nearest bounded rational with denominator
    at most `10**placeholder_count - 1`; fixed denominators retain their literal
    value and round the numerator half up. Mixed fractions carry a rounded numerator.
  - Omit fraction-only alignment spaces while preserving required zeroes, quoted
    literal spaces and one separator between a whole number and its numerator.
  - Zero `?/?` displays `0/1`; zero `00/00` displays `00/01`; zero mixed fractions
    retain a readable `0` rather than dropping the cell's value.
  - This bounded-rational policy can differ from Excel's approximation heuristic.
    For example, `0.123456` with `# ????/????` displays `1229/9955`, while the
    observed Excel version chooses `10/81`. The saved numeric value is unchanged.

### Scientific and engineering patterns

- **Source**
  - Uppercase `E+` or `E-` between mantissa and exponent placeholders.
- **Parsing**
  - Use Decimal scaling, exponent padding and sign rules; normalize rounding
    carry into the exponent. Multiple integer mantissa positions select engineering
    exponent groups. Do not use binary powers that overflow or underflow first.
  - Lowercase exponent syntax remains unsupported; retain the saved value.
- **Example**
  - `123456` with `0.00E+00` displays `1.23E+05`.

### Embedded numeric literals and text

- **Parsing**
  - Compile integer/fractional digit positions separately from literal operations.
    Masks such as `000\-00\-0000` retain embedded punctuation; `0.0"X"0` retains
    a literal between fractional positions. Do not translate digits inside literals.
  - Decimal points remain visible even when all adjacent optional zeroes are omitted.
    Width-fill characters are omitted; underscore spacing follows the reading policy.
- **Examples**
  - `0.125` with `.00` displays `.13`; zero with `#.##` displays `.`.
  - `12.34` with `0.0"X"0` displays `12.3X4`.

### DBNum

- **Parsing**
  - Simplified Chinese DBNum1/2/3 supports General integers/decimals with absolute
    value below `1e16`, fixed-point digit masks, dates, clocks and elapsed fields.
    Explicit LCID 804 is authoritative; other DBNum locales remain unsupported.
  - General uses Chinese counting groups `万`, `亿`, `兆`; fixed-point masks
    translate numeric digit positions only, preserving separators and literal text.
  - DBNum1 zero is `○` (U+25CB), DBNum2 uses financial digits, and DBNum3 uses
    fullwidth decimal digits. Date/time fields retain their field-specific padding
    and counting rules; month names remain locale words rather than numeric fields.
  - Percent/fraction DBNum combinations, other variants and unsupported magnitude
    ranges retain the saved value with a warning.
- **Examples**
  - DBNum3 General `1234` displays `１千２百３十４`.
  - DBNum1 fixed-point `0" ID2"` with `1234.56` displays `一二三五 ID2`.

## Date and time display

- **Source**
  - Globals Date1904 (`0x0022`) selects the date system: 0 for 1900, 1 for 1904.
    Absent Date1904 defaults to the 1900 system. Other values fail.
  - The cell XF's effective saved/built-in format code supplies the date fields.
    Date classification follows format syntax rather than the numeric range.
- **Output**
  - Date/time display is in `XlsCell.display_text`. `value` remains the original
    numeric serial and `XlsContent.date_1904` retains the selected system.
  - The same supported code, numeric value, locale and date system use the same
    rendering algorithms as [XLSX number formats](../xlsx/styles/number-format.md).
    This does not change XLS content values into XLSX DTP/DTX results.
- **Parsing**
  - Pass the workbook's date system to the display index after reading Globals
    and before reading any worksheet. Compiled syntax does not retain an epoch;
    each execution receives the workbook's current epoch explicitly.
  - The 1904 epoch is 1904-01-01 at serial 0. In the 1900 system, serials 1–59
    use Excel's historical day adjustment, serial 60 displays the fictitious
    1900-02-29, and serial 61 displays 1900-03-01.
  - A day's fractional part supplies time of day. Ordinary hour fields wrap at
    24 hours; elapsed `[h]`, `[m]` and `[s]` fields retain whole-day contributions.
  - Support year/month/day, month names, weekdays, hours/minutes/seconds, AM/PM,
    supported Chinese date fields, and fractional seconds up to milliseconds.
    An `m/mm` field after hours or before seconds means minutes; otherwise months.
  - Reuse XLSX's date locale/calendar validation and deterministic supported
    system-date defaults. Unsupported explicit language/calendar/number-system
    directives, sub-millisecond display and unrepresentable dates retain the
    saved value with the existing warning.
  - Built-in fallback lookup also covers locale-dependent date IDs 27–36 and
    50–58 when the requested locale has an explicit supported mapping.
- **Examples**
  - 1900 serial 46235 and 1904 serial 44773 with `yyyy/m/d` both display `2026/8/1`.
  - Serial 0.5208333333333334 with `h:mm:ss` displays `12:30:00`.
  - Serial 0.5208347800925925 with `h:mm:ss.0` displays `12:30:00.1`.

## `XlsLimits`

- **Defaults**
  - `cfb`: the defaults of `CfbLimits`.
  - `max_sheets = 256`; `max_records = 1000000`; `max_cells = 500000`.
  - `max_strings = 500000`; `max_string_characters = 32767` UTF-16 units.
  - `max_total_string_characters = 16000000` UTF-16 units.
  - `max_xfs = 4096`.
- **Parsing**
  - Positive integers only; reject booleans. Counters cover all parsed sheets.
  - BIFF payload size is at most 8224 bytes. The reader uses a bounded 64-KiB
    logical read buffer, but retains decoded SST strings and the result content.
  - These bounds do not promise constant memory or a hard RSS ceiling.
  - XF count is bounded before append. Format string units count toward the
    string character budgets; the finite identifier range bounds Format entries.
- **Diagnostics**
  - Invalid limit argument: `ValueError`.

## Example

```python
from doctokens_excel import read_xls_content

content = read_xls_content("saved.xls")
for sheet in content.sheets:
    for cell in sheet.cells:
        print(sheet.name, cell.ref, cell.display_text)
```

## References

- [MS-XLS](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/):
  Workbook Stream, BOF/EOF, BoundSheet8, SST/Continue, basic cell records and FormulaValue.
- [XF](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/993d15c4-ec04-43e9-ba36-594dfb336c6d),
  [CellXF](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/671c8577-901f-4215-9ebf-6f5890e5896d),
  [Format](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/300280fd-e4fe-4675-a924-4d383af48d3b),
  and [IFmt](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/9017e247-7995-4a9c-96e8-950df24735a2).
- ISO/IEC 29500-1:2016, section 18.8.30: number-format sections, quoted literals,
  currency symbols, and the `[$<Currency String>-<language info>]` directive.
