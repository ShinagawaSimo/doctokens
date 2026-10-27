# Display number formats

[XLSX](../README.md) / Display number formats

Display formatting applies the effective Excel number format from the cell XF to the saved cell value. The parser uses the explicit workbook locale (default `zh-CN`) and does not evaluate formulas. The displayed text and formula-bar text are separate concepts: `<v>` is not itself the formula-bar string.

Format syntax is compiled per effective format code and locale within the
workbook's FormatIndex. Section directives, classifications, syntax masks and
date operations are reused; each value still selects its section and is formatted
independently using the active date system. No global cache or per-cell/value
result cache is introduced.

XLS and XLSX share the format-family dispatcher. Decimal placeholder/literal
operations are compiled per core pattern; fraction and scientific algorithms
retain their own numeric semantics. General preserves the saved precision and
does not emulate Excel's width-dependent shortening. Fraction display omits only
alignment padding while retaining explicit literal spaces.

Date compilation resolves literals, month/minute roles, weekday/month names,
AM/PM, elapsed fields and fractional-second suffixes from the effective locale
context once. Execution converts each saved serial using its workbook epoch and
performs value rounding before applying those operations. Cell decoding reads
coordinates, type, XF index and formula presence once and shares them across
display, raw, style and control processing; output and fallback rules are unchanged.

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
  - Split sections only at semicolons outside quoted text and bracket directives. Select conditional sections first, then positive/negative/zero/text sections. Ignore quoted literals and escapes while detecting date fields. Preserve bracket directives separately from field tokens. Recognize `y`, `m`, `d`, `h`, `s`, `AM/PM`, `A/P`, and elapsed `[h]`, `[m]`, `[s]`. In effective `zh-CN`, recognize `aaa` and `aaaa` as short and long weekdays (for example, `周六` and `星期六`). An `m/mm` token after hours or before seconds is minutes; otherwise it is a month.
  - Percent sections multiply the value by 100. Numeric sections apply `0`, `#`, `?`, grouping commas, scaling commas, and decimal rounding. `0` pads a required zero and `?` reserves an insignificant position for alignment. Fraction numerator/denominator alignment is omitted from textual output: saved `0.25` with `# ??/??` produces `1/4`, and `1.25` produces `1 1/4`. Required zeroes in `00/00` remain visible (`01/04`). Quoted literal spaces and the mixed-fraction separator remain intact. Decimal alignment behavior is unchanged. Currency and other literal text are retained from the selected section. Scientific notation requires an uppercase `E+` or `E-` marker; fractions require numeric placeholders around `/`. Unsupported tokens preserve the saved value instead of inventing a display.
  - Named color directives such as `[Red]` are removed from display text and, in semantic XML, expose the selected section color through the cell's semantic `color` attribute. Condition directives select a section by the saved numeric value; if no condition matches, the parser keeps the saved value as a safe display fallback rather than selecting a failed condition.

### `DBNum`

- **Output**
  - Chinese counting text for supported numeric sections and Chinese date fields for supported date sections. Numeric `raw` is independent of date display.
- **OOXML**
  - `[DBNum1]`, `[DBNum2]` or `[DBNum3]` in `numFmt/@formatCode`, optionally accompanied by the Simplified Chinese locale directive `[$-804]`.
- **IR**
  - Resolved `Cell.text`; `Cell.raw` retains an independently supported ordinary numeric edit form. Date serials do not become `raw`.
- **Parsing**
  - Support General integers/decimals with absolute value below `1e16`. DBNum1 uses `○一二三四五六七八九` (U+25CB for zero) and `十百千`; DBNum2 uses `零壹贰叁肆伍陆柒捌玖` and `拾佰仟`; DBNum3 uses fullwidth digits with Chinese units. Split integers into four-digit groups, attach `万`, `亿`, or `兆`, and insert a zero across missing positions. General retains the leading one before ten. Fractional digits follow the decimal point without counting units.
  - Fixed-point patterns translate numeric positions after rounding and padding. Preserve grouping separators and all literal text: `1234.56` with `[DBNum1]0" ID2"` displays `一二三五 ID2`, leaving the literal `2` intact.
  - An explicit locale ID is authoritative; `804` and `0804` select Simplified Chinese even when the parser locale differs. Without an explicit locale directive, require `zh-CN`. Preserve literal prefixes/suffixes and the selected positive/negative/zero section. Literal bracket text is not a locale directive.
  - Date classification precedes numeric DBNum dispatch. Convert year digits, month/day fields, clocks, elapsed fields and fractional seconds with their field-specific padding and counting rules. DBNum2 keeps financial leading ones in tens; DBNum3 ordinary dates/clocks use fullwidth positions while elapsed fields use counting units. Month-name tokens retain locale words. Saved `46235` with `[DBNum1][$-804]yyyy"年"m"月"d"日"` displays `二○二六年八月一日`. Never convert the entire date serial as an ordinary integer.
  - Percent/fraction combinations, other variants/locales and out-of-range General values retain the saved value. Do not substitute Word numbering: its glyphs and counting rules differ.

### Fraction approximation

- **Parsing**
  - Choose the nearest rational whose denominator fits the placeholder count,
    or round the numerator against an explicit fixed denominator. Retain required
    zeroes and literal spaces; omit only alignment padding.
  - Excel can choose a different approximate fraction for the same saved value.
    With `# ????/????`, saved `0.123456` yields `1229/9955` under this policy;
    observed Excel yields `10/81`. This is separate from alignment-space removal.

### Unsupported format syntax

- **Parsing**
  - Require balanced literals/directives and at most four sections. Unknown bracket
    directives, unsupported DBNum/locales/calendar bits, lowercase exponent forms,
    explicit `b1/b2` calendar selectors and sub-millisecond time patterns retain saved data.
  - Quoted/escaped bracket text is literal. Named colors and indexed color
    directives do not become display characters; only supported named colors
    are projected through the existing semantic color mapping.

### Date locale and system long date

- **Output**
  - Localized date fields in `Cell.text`, shared across all three densities.
- **OOXML**
  - The selected section's `[$<currency>-<language info>]`. ISO/IEC 29500-1 §18.8.30 defines the 32-bit hexadecimal language, calendar and number-system information, with special values F800 (system long date) and F400 (system time).
- **IR**
  - A date context retains the effective code, locale and DBNum mode.
- **Parsing**
  - Explicit `0409`/`409` selects `en-US`; `0804`/`804` selects `zh-CN`, overriding the parser locale. Normalize locale case and underscores. Pass this context to AM/PM, weekday/month names and DBNum; literal bracket text has no such effect.
  - In `en-US`, `mmm`, `mmmm`, `mmmmm` produce abbreviated, full and initial English month names; `AM/PM` produces `AM` or `PM`. In `zh-CN`, month names use the month number plus `月`, and AM/PM uses `上午` or `下午`.
  - F800 replaces the saved following date template with a deterministic locale default: `yyyy"年"m"月"d"日"` for `zh-CN`, and `dddd, mmmm d, yyyy` for `en-US`. For 2026-08-01 these produce `2026年8月1日` and `Saturday, August 1, 2026`. The English pattern is an explicit parser policy, not a claim that ISO mandates one English system setting.
  - Do not read the host OS regional preferences. The workbook does not preserve the producer's customized system long-date pattern. Other F800 locales, F400, and unsupported explicit language/calendar/number-system combinations retain the saved value; they are not silently interpreted as another locale or calendar.

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
  - Preserve decoded text before applying a supported text section. For ordinary numeric formats, emit the edit-form value only when it is independently recoverable. A supported uppercase scientific display token (`E+`/`E-`) is formatting syntax and does not by itself prevent recovery of the saved ordinary number. Omit `raw` silently when reconstruction would require guessing; do not emit a formula-bar-unavailable diagnostic. Formula cells expose their expression through `formula` and do not copy the cached `<v>` into `raw`; this also applies to data-table members whose expression is reconstructed from the master's attributes.
  - Numeric reconstruction supports `zh-CN` and `en-US`, up to 15 significant decimal digits, and zero or magnitudes from `1e-9` inclusive to `1e15` exclusive. These limits also apply to scientific display formats. For example, saved `123456` with `0.00E+00` produces `<cell raw="123456">1.23E+05</cell>`; `raw` retains the unrounded number rather than reconstructing it from the rounded display.
  - For `zh-CN` numeric times in `[0, 1)` with `h:mm:ss` or `hh:mm:ss`, optionally followed by one to three fractional-second zeroes, reconstruct the formula bar as `h:mm:ss` without fractional seconds. Resolve serial noise to milliseconds before taking the whole seconds. The cell display is calculated separately at its requested precision. For example, saved `0.52083478009259254` represents `12:30:00.125` to millisecond precision; `h:mm:ss.0` produces `<cell raw="12:30:00">12:30:00.1</cell>`. Here `raw` is an application edit-form rendering, not a lossless representation of the stored serial.
  - Date-bearing serials, negative/elapsed times, AM/PM, explicit locale directives, and other time patterns remain outside this formula-bar reconstruction. The 1900/1904 epoch does not affect supported times within the first day. A rounded serial at the next-day boundary is excluded.

## Time precision and Excel's formula bar

ISO/IEC 29500-1 §18.17.4.1 defines serial date-times in days, with fractional days carrying the time. §18.8.31 defines the independent display format, including fractional seconds (`h:mm:ss.00`). These storage/display rules do not require the formula bar to reproduce fractional seconds. The saved real-workbook case retains `.125` even though its cell shows `.1` and the user-observed Simplified Chinese Excel formula bar shows whole seconds. Re-entering a time and seeing the formula bar omit the fraction therefore does not establish that the saved value was truncated. A parser reads the saved serial and does not reproduce Excel's editing or saving actions.
