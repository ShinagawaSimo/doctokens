# Placeholders

[PPTX](../README.md) / Placeholders

Placeholder type supplies title identity and inherited defaults.

## Fields

### `placeholderType`

- **Output**
  - Both XML densities use title for single-paragraph title/ctrTitle text, or
    textbox/@role="title" for a title with multiple paragraphs. Neither repeats
    the role as a placeholder attribute.
  - Other known reading roles use @role as defined below. Raw @placeholder and
    internal idx are not reading fields. Plain retains the same readable text.

- **OOXML**
  - p:ph/@type and @idx.

- **IR**
  - `ShapeBlock.placeholderType: str`

- **Parsing**
  - Direct nonempty type wins. Every reading plan resolves layout by idx
    (default 0), then by own type, and takes the inherited type when needed.
    Internal placeholder identity still supports inheritance and default-name
    filtering; rendering applies the same role projection in sessions.

- **Absence and defaults**
  - Unknown types add no guessed role. body/obj and categories already
    represented by img/chart/table/smartart/media add no repeated type field.

### `role`

- **Output**
  - A known additional reading role on the primary shape element in structural
    and semantic output. A title element already expresses the title role;
    a multi-paragraph title instead uses textbox/@role="title".
- **OOXML**
  - Direct or inherited p:ph/@type.
- **Parsing**
  - subTitle → subtitle; sldNum → slide-number; dt → date; hdr → header;
    ftr → footer; sldImg → slide-preview.
  - Preserve saved text without recalculating the slide number or date, or
    inserting text from a layout/master.
- **Example**
  - `<title shape-id="s1">Budget</title>`
  - `<p role="slide-number" shape-id="s2">4</p>`

### `idx`

- **Output**
  - Internal lookup key.

- **OOXML**
  - p:ph/@idx.

- **IR**
  - LayoutContext.placeholders key.

- **Parsing**
  - Default "0". Layout placeholders can inherit master geometry by type; template text is not inserted into slide content.
