# List of Test Files

  This folder(`test_support`) contains all the test files, including the true office files in `fixtures` ，the golden parsing results in `golden`，and files in other formats, such as images, in `fixture-assets`, which is used in office test files.

  The files in this folder should be treated as the frozen standard for the parser's actual behavior. All golden files are final parsing results that have been manually reviewed by developers and conform to their standards. All original input files have been reasonably designed to cover as many of the parser's parsing behaviors as possible and to minimize overlap among them when testing the same parsing behavior, so that modified parsing logic can be quickly located during future development.

  The current file set may not yet be complete. You are welcome to help improve this test folder, especially when new parsing behaviors need to be added to the parser's functionality. The current file set can only include file-editing actions that developers can perform in a Simplified Chinese Office (`zh-CN`) environment. For options that vary by country/region and language settings, such as Word list numbering and Excel date formats, you are welcome to add coverage.

## DOCX Test Files

Names of these DOCX test files all have the prefix "docx-". In the following list, these prefixes are omitted.

### Paragraphs and Styles

* paragraph : two paragraphs in order, without headings or numbering.
* heading-style : mixed paragraph and character styles across 23 paragraphs.

### Decimal Numbering

* list-decimal : standard decimal numbering.
* list-decimalFullWidth : full-width Arabic numerals.
* list-decimalZero : decimal numbering with leading zeroes.
* list-decimalEnclosedCircle : circled numerals.

### Alphabetic and Roman Numbering

* list-lowerLetter : lowercase Latin letters.
* list-upperLetter : uppercase Latin letters.
* list-lowerRoman : lowercase Roman numerals.
* list-upperRoman : uppercase Roman numerals.

### Chinese and Japanese Numbering

* list-chineseCountingThousand : Chinese counting numerals using 十、百、千、万.
* list-chineseLegalSimplified : simplified Chinese financial numerals.
* list-ideographDigital : digit-by-digit Chinese numerals.
* list-japaneseCounting : Chinese counting style omitting 一 before small units.
* list-japaneseLegal : Japanese formal numerals available in Simplified Chinese Word.

### Japanese Syllabary Numbering

* list-aiueo : half-width katakana sequence.
* list-aiueoFullWidth : full-width katakana sequence.
* list-iroha : half-width Iroha sequence.
* list-irohaFullWidth : full-width Iroha sequence.

### Number Words

* list-cardinalText : cardinal number words.
* list-ordinal : ordinal numbers such as 1st, 2nd, 3rd.
* list-ordinalText : ordinal number words.

### Cyclical Numbering

* list-ideographTraditional : Heavenly Stems sequence.
* list-ideographZodiac : Earthly Branches sequence.

### List Structure and Bullets

* list-bullet : default solid-circle bullets.
* list-bullet-color : colored bullet symbol.
* list-bullet-symbol : Unicode star bullet symbol.
* list-multilevel : parent and child numbering combined across two levels.
* list-none : list items without visible labels.

Existing numbering files also contain higher values such as 101, 1001, 10001 and 10050 where applicable. Letter files include 780; circled numbers reach 20, Heavenly Stems reach 10 and Earthly Branches reach 12. These saved examples are part of the full-file baseline, so separate scalar tests are unnecessary for the same behavior.

## XLSX Test Files

Names of these XLSX test files all have the prefix "xlsx-". In the following list, these prefixes are all omitted.

### Basic Value and Text

* empty : empty files.
* value-text : common text.
* value-number : common number.
* value-boolean : common boolean, TRUE / FALSE.
* text-special : text with Unicode, quotation marks and XML escape symbols.
* text-spaces : text with spaces.
* text-linebreak : text with a linebreak in a cell.
* sparse : sparse table with non-empty cells outside the first row and column.

### Rich Text Style

* rich-color : rich text with font color.
* rich-italic : rich text with italic formatting.
* rich-underline : rich text with underline formatting.
* rich-bold : rich text with bold formatting.

### Formula

* formula-absolute : absolute cell references remain fixed when filled.
* formula-array : legacy array formula over a range.
* formula-boolean : formula returning a boolean value.
* formula-cross-sheet : relative formulas filled down across sheets.
* formula-empty : formula returning an empty string, distinct from a missing cell.
* formula-escaped-quote : escaped double quotes in a string literal.
* formula-function-name : `LOG10` remains a function name when filled.
* formula-horizontal : relative references filled across columns.
* formula-mixed : partially absolute row and column references.
* formula-quoted-sheet : reference to a sheet name containing spaces.
* formula-quoted-text : cell-like text inside a string is not a cell reference.
* formula-range : both endpoints of a range shift when filled.
* formula-relative : relative row references when filled.
* formula-scientific : scientific notation in a formula constant.
* formula-sheet-scope : shared formula groups are independent per sheet.
* formula-string : formula returning text.
* formula-sum : formula text and its cached result.

### Text Format

* format-bracket : color directive in a custom number format.
* format-currency : currency symbol and decimal places.
* format-fraction : fraction display and denominator selection.
* format-literal : quoted display text in a custom number format.
* format-percent : percentage display with one decimal place.
* format-scientific : scientific number display while preserving the raw value.
* format-number-negative : grouping, decimal places and a negative number section.
* format-currency-negative : currency formatting of a negative value.
* format-accounting : currency, number and accounting alignment.
* format-fraction-two-digit : two-digit fraction placeholders; extracted text is `1/4` without alignment padding.
* format-special-lower : Simplified Chinese lowercase numbers using DBNum1.
* format-special-upper : Simplified Chinese financial numbers using DBNum2.
* format-time-fractional : `h:mm:ss.0` displays `12:30:00.1`; the recovered formula-bar value is `12:30:00`.

### Data Table

* formula-data-table : native one-variable, vertical what-if data table.

### Error Values

* error-div0 : division by zero, `#DIV/0!`.
* error-na : `#N/A`.
* error-name : an undefined name, `#NAME?`.
* error-null : non-intersecting ranges, `#NULL!`.
* error-num : invalid numeric operation, `#NUM!`.
* error-ref : a deleted referenced column, `#REF!`.
* error-value : incompatible value types, `#VALUE!`.

### Shared Strings

* shared-strings : repeated text stored through shared string indexes.

### Date and Time

* date-1900 : default 1900 date system.
* date-1904 : 1904 date system.
* date-leap-boundary : Excel's 1900 leap-day boundary.
* date-time : date and time in one cell.
* time : time-only serial value.

### Cell Layout

* blank-styled : a blank cell with yellow fill versus a missing cell; also covers ordinary cell fill parsing.


