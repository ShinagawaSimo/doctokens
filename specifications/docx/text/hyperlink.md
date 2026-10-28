# Hyperlinks

[DOCX](../README.md) / Hyperlinks

Display text remains readable even when a relationship is missing.

## Processing

Plain emits display text, not hyperlink markup. Result-run links from fields use [field parsing](field.md).

## Fields

### `href`

- **Output**
  - `<a href="...">text</a>` in both XML densities.

- **OOXML**
  - `w:hyperlink/@r:id` → relationship target.

- **IR**
  - `Run.link.href: str`

- **Parsing**
  - Use `resolved_target or target`; keep source URL without fetching.

- **Absence and defaults**
  - No relation/href: omit href.

- **Diagnostics**
  - Unknown rId: `HYPERLINK_TARGET_MISSING`, locator is owning part.

### `anchor`

- **Output**
  - `a/@anchor`; can coexist with href.

- **OOXML**
  - `w:hyperlink/@w:anchor`, or reference field result.

- **IR**
  - `Run.link.anchor: str`

- **Parsing**
  - Copy nonempty anchor. With no href, it can retain a matching local [bookmark target](bookmark.md). With an href it identifies that document's fragment. No remote/local target execution.

- **Absence and defaults**
  - Absent: omit attribute.
