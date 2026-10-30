# Content controls

[DOCX](../README.md) / Content controls

A control retains its saved content and an optional human-readable label.
Plain emits `[content-control] LABEL: VALUE` or `[content-control] VALUE`.
Structural DTX retains the content's ordinary blocks and inline elements inside
`content-control`, with only an optional `label` attribute.

Semantic DTX adds useful type, choice, current-state and lock information.
One unadorned paragraph is inlined; headings, multiple paragraphs, tables,
objects, paragraph properties and review marks retain their reading structure.
Adjacent fragments of the same source control are grouped before projection.
Distinct controls remain distinct even when their metadata and values agree.
Source IDs are not read or emitted for this grouping.

## Fields

### `label`

- **Output**
  - Optional `content-control/@label` in both XML densities.
  - Optional label following the plain control marker.
- **OOXML**
  - `w:sdtPr/w:alias/@w:val`.
- **IR**
  - `ContentControl.label: str`.
- **Parsing**
  - Copy nonempty alias text. Do not use the programmatic tag as a fallback.
  - Preserve the saved content when no label exists.

### `type`

- **Output**
  - Semantic `content-control/@type`; omitted from structural and plain.
- **OOXML**
  - Recognized type child of `w:sdtPr`.
- **IR**
  - `ContentControl.controlType: str`.
- **Parsing**
  - Recognize text, richText, picture, date, comboBox, dropDownList, checkbox,
    group, repeatingSection and citation. docPartList/docPartObj map to
    buildingBlock. Last recognized type wins.
  - Unknown type is not emitted as a redundant default.

### `choice`

- **Output**
  - Direct semantic `content-control/choice` children, without a choices wrapper.
  - Character data is the readable candidate text; the current matching
    candidate carries `checked="true"`.
- **OOXML**
  - comboBox/dropDownList `w:listItem/@w:displayText`, falling back to
    `@w:value` only when displayText is empty.
  - Current display comes from retained `w:sdtContent`.
- **IR**
  - `ContentControl.options: list[str]`.
- **Parsing**
  - Retain distinct nonempty readable candidates in source order. Do not
    retain a separate internal value or output a display=value pair.
  - Match the complete saved display exactly, across adjacent formatted runs.
    Put its existing inline content in the matching choice once, preserving
    emphasis and links. Do not repeat the current value in a p.
  - A comboBox value outside the declared candidates becomes one additional
    choice with `checked="true" listed="false"`. This identifies a saved custom
    entry, without inventing another declared option.
  - An unmatched dropDownList display remains in a `value` element; no declared
    candidate is guessed to be selected. Empty display selects no candidate.
  - Unexpected multi-block/object content is retained as ordinary content with
    unselected candidates, rather than guessing a selection from flattened text.
  - Plain/structural omit candidates and retain only the current content.

### `checked`

- **Output**
  - Semantic `choice/@checked` for a list's current candidate or a checkbox state.
  - For a checkbox, explicit true and false are both meaningful. Unknown is
    omitted, rather than converted to false.
- **OOXML**
  - `w14:checkbox/w14:checked/@w14:val`, where w14 is
    `http://schemas.microsoft.com/office/word/2010/wordml`.
- **IR**
  - Optional `ContentControl.checked: bool`.
- **Parsing**
  - Decode 1/true/on and 0/false/off case-insensitively.
  - A semantic checkbox has one choice containing its saved inline content
    and, when known, its checked attribute.
  - Lower densities retain the displayed checkbox value without an extra
    state attribute. If no content is present but the saved state is known,
    use checked/unchecked as the readable current value.
  - An empty control remains represented; it is not an unreadable-element failure.

### `lock`

- **Output**
  - Semantic `content-control/@lock="content|control|both"`.
- **OOXML**
  - `w:sdtPr/w:lock/@w:val`.
- **IR**
  - Optional `ContentControl.lock: Literal["content", "control", "both"]`.
- **Parsing**
  - contentLocked → content: the saved content cannot be edited.
  - sdtLocked → control: the control cannot be removed; its content may remain editable.
  - sdtContentLocked → both.
  - unlocked, absent and unrecognized values add no lock attribute.
  - Plain/structural omit lock metadata. The parser describes saved restrictions;
    it does not enforce them or derive document-wide editing permission.

## Excluded source fields

Control tags, source IDs, dataBinding XPath/storeItemID/prefixMappings,
placeholder docPart identifiers, date-format strings, multiLine and temporary
settings are not extracted. Their saved visible content remains readable.
The reader does not evaluate bindings, change control values or compute dates.

## Example

```xml
<content-control label="Status" lock="content" type="dropDownList">
  <choice checked="true">Open</choice>
  <choice>Closed</choice>
</content-control>
```
