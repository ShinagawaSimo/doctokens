# Content-control bindings

[DOCX](../README.md) / Content-control bindings

`w:sdtPr/w:dataBinding` describes a stored binding. Parsing retains its attributes without evaluating XPath or reading a bound custom XML value.

## Fields

### `xpath`

- **Output**
  - Semantic `content-control/@binding`.

- **OOXML**
  - `w:dataBinding/@w:xpath`

- **IR**
  - `ContentControl.binding["xpath"]: str`

- **Parsing**
  - Copy the nonempty value verbatim; XML serialization escapes it.

- **Absence and defaults**
  - Absent or empty: omit.

### `storeItemID`

- **Output**
  - Internal custom XML store identifier.

- **OOXML**
  - `w:dataBinding/@w:storeItemID`

- **IR**
  - `ContentControl.binding["storeItemID"]: str`

- **Parsing**
  - Copy the nonempty value; no GUID normalization or store lookup.

- **Absence and defaults**
  - Absent or empty: omit.

### `prefixMappings`

- **Output**
  - Internal namespace declarations for XPath.

- **OOXML**
  - `w:dataBinding/@w:prefixMappings`

- **IR**
  - `ContentControl.binding["prefixMappings"]: str`

- **Parsing**
  - Copy the nonempty string; do not parse declarations. The binding dictionary is omitted if all three attributes are absent or empty.

- **Absence and defaults**
  - Absent or empty: omit.
