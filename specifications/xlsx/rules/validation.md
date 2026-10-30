# Data validation

[XLSX](../README.md) / Data validation

Read declarations without enforcing constraints or evaluating formulas.
Both XML densities retain constraints and messages; plain omits readable rule
declarations by its existing policy. Default values are omitted from DTX.

## Processing

Core rules use s:dataValidations/s:dataValidation. Extended rules use
x14:dataValidations/x14:dataValidation inside worksheet extensions, where:

- `s = http://schemas.openxmlformats.org/spreadsheetml/2006/main`.
- `x14 = http://schemas.microsoft.com/office/spreadsheetml/2009/9/main`.
- `xm = http://schemas.microsoft.com/office/excel/2006/main`.

The primary worksheet scan retains complete rule subtrees before decoding.
Normalize both representations to DataValidation; identical effective
declarations are emitted once. No source-version attribute is needed.
The [x14 schema](https://github.com/dotnet/Open-XML-SDK/blob/main/data/schemas/schemas_microsoft_com_office_spreadsheetml_2009_9_main.json)
defines the extension structure.

## Fields

### `ranges`

- **Output**
  - data-validation/@ref.
- **OOXML**
  - Core @sqref; x14 direct xm:sqref text.
- **IR**
  - `DataValidation.ranges: str` in model/rules.py.
- **Parsing**
  - Preserve the saved range list, including disjoint areas. Missing/empty
    ranges cannot establish a usable constraint and retain an unsupported marker.

### `type`

- **Output**
  - data-validation/@type.
- **OOXML**
  - @type in either representation.
- **Parsing**
  - Default none. Recognize whole, decimal, list, date, time, textLength,
    custom and none. Unknown types retain their spelling, diagnostics and
    an unsupported marker.

### `operator`

- **Output**
  - @operator on numeric/date/time/textLength constraints.
- **OOXML**
  - @operator.
- **Parsing**
  - Default between. Read between, notBetween, equal, notEqual, lessThan,
    lessThanOrEqual, greaterThan, greaterThanOrEqual. List/custom rules
    do not gain a meaningless comparison operator.

### `formula1`

- **Output**
  - @formula1.
- **OOXML**
  - Core s:formula1 text; x14:formula1/xm:f text.
- **Parsing**
  - Copy the saved expression/list source; do not calculate it or resolve
    another sheet's values. Missing required expressions retain an
    unsupported marker and DATA_VALIDATION_FORMULA_MISSING.

### `formula2`

- **Output**
  - @formula2.
- **OOXML**
  - Core s:formula2 text; x14:formula2/xm:f text.
- **Parsing**
  - Copy when saved. between/notBetween numeric/date/time/textLength rules
    require this second boundary; it is never inferred from the first.

### `allowBlank`

- **Output**
  - @allow-blank=true when enabled; omitted means false.
- **OOXML**
  - @allowBlank.
- **Parsing**
  - Default false. Decode XML boolean 1/true and 0/false.

### `showDropDown`

- **Output**
  - @dropdown=false on list rules when the saved control is suppressed.
- **OOXML**
  - @showDropDown.
- **Parsing**
  - Default false. In this OOXML flag true suppresses the list dropdown;
    it is not an instruction to display it.

### `showInputMessage`

- **Output**
  - @show-input-message=true when enabled.
- **OOXML**
  - Rule @showInputMessage; parent dataValidations/@disablePrompts.
- **Parsing**
  - Default false. Parent disablePrompts=true overrides the rule's enabled
    input prompt. Preserve saved prompt text even when disabled.

### `showErrorMessage`

- **Output**
  - @show-error-message=true when enabled.
- **OOXML**
  - @showErrorMessage.
- **Parsing**
  - Default false. Saved messages remain readable independently of whether
    the application is configured to display them.

### `errorStyle`

- **Output**
  - @error-style for a non-default saved value.
- **OOXML**
  - @errorStyle.
- **Parsing**
  - Default stop; retain saved warning/information values.

### `imeMode`

- **Output**
  - @ime-mode for a non-default saved value.
- **OOXML**
  - @imeMode.
- **Parsing**
  - Default noControl; retain an explicit input constraint.

### `promptTitle`

- **Output**
  - @prompt-title.
- **OOXML**
  - @promptTitle.
- **Parsing**
  - Decode one ST_Xstring layer, preserving literal escapes, whitespace
    and XML-safe decoded characters; see [shared strings](../cells/shared-string.md).

### `prompt`

- **Output**
  - @prompt.
- **OOXML**
  - @prompt.
- **Parsing**
  - The same saved-text decoding as promptTitle.

### `errorTitle`

- **Output**
  - @error-title.
- **OOXML**
  - @errorTitle.
- **Parsing**
  - The same saved-text decoding as promptTitle.

### `error`

- **Output**
  - @error.
- **OOXML**
  - @error.
- **Parsing**
  - The same saved-text decoding as promptTitle.
  - Example: decimal 1..10 with prompt 请输入1到10 yields formula1=1,
    formula2=10, operator=between and the saved prompt; it is not reduced
    to the word decimal.

### `unparsed`

- **Output**
  - A partially unreadable declaration retains
    `<unsupported type="data-validation"/>` inside its data-validation.
    Plain emits `[Unparsed data validation]` for that failed declaration.
- **Diagnostics**
  - DATA_VALIDATION_UNSUPPORTED, DATA_VALIDATION_FORMULA_MISSING.
    Invalid booleans emit RULE_BOOLEAN_INVALID and use the defined default.
- **Parsing**
  - Unknown content/required-body failures mark an existing element.
    An invalid optional boolean does not create an extra element placeholder.
