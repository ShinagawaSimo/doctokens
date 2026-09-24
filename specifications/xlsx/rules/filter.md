# AutoFilter

[XLSX](../README.md) / AutoFilter

Filter declarations describe saved conditions; they do not remove worksheet rows.

## Processing

Within each filterColumn, process values, custom, dynamic, top10, color, icon, then dateGroup. A values record is retained only if it has values, blank=true, or calendarType. Each customFilter is a separate record. Absent/empty/list-empty scalar attributes are omitted by DTX.

## Fields

### `ref`

- **Output**
  - filter/@ref.

- **OOXML**
  - s:autoFilter/@ref.

- **IR**
  - `SheetInfo.filter_range: str`

- **Parsing**
  - Copy; empty suppresses the filter element.

### `col`

- **Output**
  - filter/condition/@column.

- **OOXML**
  - `s:autoFilter/s:filterColumn/@colId`

- **IR**
  - `FilterColumn["col"]`

- **Parsing**
  - int, default/failure 0; zero-based relative to filter range.

### `type`

- **Output**
  - filter/condition/@type.

- **OOXML**
  - Children of `s:autoFilter/s:filterColumn`: `s:filters`, `s:customFilters`, `s:dynamicFilter`, `s:top10`, `s:colorFilter`, `s:iconFilter`, and `s:dateGroupItem`.

- **IR**
  - `FilterColumn["type"]`

- **Parsing**
  - values/custom/dynamic/top10/color/icon/dateGroup. Multiple kinds can produce separate condition records for one column.

### `values`

- **Output**
  - filter/condition/@values.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:filters/s:filter/@val`

- **IR**
  - `FilterColumn["values"]`

- **Parsing**
  - Keep nonempty source values; join with comma.

### `blank`

- **Output**
  - filter/condition/@blank.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:filters/@blank`

- **IR**
  - `FilterColumn["blank"]`

- **Parsing**
  - Store true exactly for 1; false omitted.

### `calendarType`

- **Output**
  - filter/condition/@calendar-type.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:filters/@calendarType`

- **IR**
  - `FilterColumn["calendarType"]`

- **Parsing**
  - Copy nonempty string.

### `operator`

- **Output**
  - filter/condition/@operator.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:customFilters/s:customFilter/@operator`
  - `s:autoFilter/s:filterColumn/s:dynamicFilter/@type`

- **IR**
  - `FilterColumn["operator"]`

- **Parsing**
  - Custom default equal; dynamic default empty.

### `value`

- **Output**
  - filter/condition/@value.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:customFilters/s:customFilter/@val`
  - `s:autoFilter/s:filterColumn/s:dynamicFilter/@val`

- **IR**
  - `FilterColumn["value"]`

- **Parsing**
  - Custom default empty; dynamic stores nonempty only.

### `value2`

- **Output**
  - filter/condition/@value2.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:dynamicFilter/@maxVal`

- **IR**
  - `FilterColumn["value2"]`

- **Parsing**
  - Copy nonempty string.

### `and`

- **Output**
  - filter/condition/@and.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:customFilters/@and`

- **IR**
  - `FilterColumn["and"]`

- **Parsing**
  - True for 1, applied only to first emitted custom rule.

### `top`

- **Output**
  - filter/condition/@top.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:top10/@top`

- **IR**
  - `FilterColumn["top"]`

- **Parsing**
  - Default true; exactly 1 → true. DTX emits only true, so false is omitted.

### `percent`

- **Output**
  - filter/condition/@percent.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:top10/@percent`

- **IR**
  - `FilterColumn["percent"]`

- **Parsing**
  - Default false; exactly 1 → true, output only true.

### `rank`

- **Output**
  - filter/condition/@rank.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:top10/@val`

- **IR**
  - `FilterColumn["rank"]`

- **Parsing**
  - Copy string, default empty.

### `filterValue`

- **Output**
  - filter/condition/@filter-value.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:top10/@filterVal`

- **IR**
  - `FilterColumn["filterValue"]`

- **Parsing**
  - Copy nonempty string.

### `dxfId`

- **Output**
  - filter/condition/@dxf-id.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:colorFilter/@dxfId`

- **IR**
  - `FilterColumn["dxfId"]`

- **Parsing**
  - Parse nonempty attribute int; malformed 0.

### `cellColor`

- **Output**
  - filter/condition/@cell-color.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:colorFilter/@cellColor`

- **IR**
  - `FilterColumn["cellColor"]`

- **Parsing**
  - Default true; exactly 1 → true. DTX emits explicit true or false when present.

### `iconSet`

- **Output**
  - filter/condition/@icon-set.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:iconFilter/@iconSet`

- **IR**
  - `FilterColumn["iconSet"]`

- **Parsing**
  - Copy nonempty string.

### `iconId`

- **Output**
  - filter/condition/@icon-id.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:iconFilter/@iconId`

- **IR**
  - `FilterColumn["iconId"]`

- **Parsing**
  - Parse nonempty attribute int; malformed 0.

### `dateGroup`

- **Output**
  - filter/condition/@groups.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:filters/s:dateGroupItem`
  - `s:autoFilter/s:filterColumn/s:dateGroupItem`

- **IR**
  - `FilterColumn["dateGroup"]`

- **Parsing**
  - Retain each full attribute dictionary. Serialize groups with ;, attributes sorted by key as key=value joined by :. No date calculation.


## Source references

- [_parse_filter_column](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/parsing/modules/worksheets/scanner.py#L377)
- [_append_sheet_metadata](../../../packages/xlsx_llm_parser/src/xlsx_llm_parser/rendering/dtx.py#L79)
