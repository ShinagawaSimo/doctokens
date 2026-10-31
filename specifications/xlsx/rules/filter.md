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
  - XML boolean 1/true enables blank matching; false is omitted.

### `calendarType`

- **Output**
  - filter/condition/@calendar-type.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:filters/@calendarType`

- **IR**
  - `FilterColumn["calendarType"]`

- **Parsing**
  - Copy nonempty string, omitting the default none calendar.

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
  - True for XML boolean 1/true, applied only to the first emitted custom rule.

### `top`

- **Output**
  - filter/condition/@top.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:top10/@top`

- **IR**
  - `FilterColumn["top"]`

- **Parsing**
  - Default true; DTX omits true and emits top=false for bottom-ranked filtering.

### `percent`

- **Output**
  - filter/condition/@percent.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:top10/@percent`

- **IR**
  - `FilterColumn["percent"]`

- **Parsing**
  - Default false; XML boolean 1/true enables percent matching, output only true.

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

### `color`

- **Output**
  - Both XML densities: filter/condition/@color as #RRGGBB.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:colorFilter/@dxfId`

- **IR**
  - `FilterColumn["color"]`

- **Parsing**
  - Resolve the source dxf index while parsing. cellColor=true selects its fill;
    false selects font color. Resolve theme/indexed/tint colors through the
    workbook palette. No bare source index or guessed color is emitted.

### `cellColor`

- **Output**
  - filter/condition/@cell-color.

- **OOXML**
  - `s:autoFilter/s:filterColumn/s:colorFilter/@cellColor`

- **IR**
  - `FilterColumn["cellColor"]`

- **Parsing**
  - Default true; XML boolean 1/true or 0/false selects fill/font color.
    DTX emits the explicit color target.

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
  - Retain year/month/day/hour/minute/second/dateTimeGrouping only. Serialize
    groups with ;, attributes sorted by key as key=value joined by :. No date calculation.
