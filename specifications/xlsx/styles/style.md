# Cell styles

[XLSX](../README.md) / Cell styles

Semantic styles use the effective cell-XF and its font/fill references. Cell XF selection is defined in [cells](../cells/cell.md#style). Font/fill IDs inherit a valid cellStyleXf parent when the corresponding apply flag is false or the direct ID is absent, matching effective number-format inheritance.

Differential-style summaries retain explicitly disabled font properties as `bold=false`, `italic=false`, or `underline=false`. A false override in a saved conditional rule is not equivalent to an absent property and must not be summarized as an enabled style.

## Fields

### `strike`

- **Output**
  - Cell/style-range strike=true.
- **OOXML**
  - The effective font's strike element.
- **Parsing**
  - Read the saved boolean. Rich-run false values clear this context only
    where explicitly declared.

### `superscript` and `subscript`

- **Output**
  - Cell/style-range vertical reading identity.
- **OOXML**
  - Effective font/vertAlign.
- **Parsing**
  - Preserve superscript/subscript and explicit baseline cancellation.
    No editable font offset is emitted.

### `bold`

- **Output**
  - cell/style-range @bold=true.

- **OOXML**
  - Referenced font/b.

- **IR**
  - `FontInfo.bold`

- **Parsing**
  - Absent: false. Present with no val: true. Explicit 0/false/off: false. Source values are case-normalized for this on/off interpretation.

### `italic`

- **Output**
  - @italic=true.

- **OOXML**
  - font/i.

- **IR**
  - `FontInfo.italic`

- **Parsing**
  - Same on/off interpretation as bold.

### `underline`

- **Output**
  - @underline=true.

- **OOXML**
  - font/u.

- **IR**
  - `FontInfo.underline`

- **Parsing**
  - No val means single; 0/false/off/none disable underline. Other underline styles collapse to one reading underline.

### `color`

- **Output**
  - @color.

- **OOXML**
  - font/color.

- **IR**
  - `FontInfo.color`

- **Parsing**
  - Resolve [color](color.md); omit #000000 in ordinary cell style_attrs.

### `fill`

- **Output**
  - @fill.

- **OOXML**
  - fill/patternFill/fgColor.

- **IR**
  - `FillInfo.fill`

- **Parsing**
  - Resolve color regardless of pattern type; background/gradient fills are not represented.

### `locked`

- **Output**
  - Semantic cell/@locked=true only when saved sheet protection is enabled
    and the effective cell protection is locked. False/unknown values are
    omitted; plain and structural emit no protection attributes.

- **OOXML**
  - xf/protection/@locked.

- **IR**
  - Optional cell-format boolean; None represents an invalid/unknown flag.

- **Parsing**
  - Decode 1/true and 0/false. With no direct protection group, or with
    applyProtection=0/false, use the valid cellStyleXf parent protection group.
    Otherwise use the cell-XF group. Missing attributes in the chosen group
    use the intrinsic defaults: locked=true and hidden=false.
  - A missing cell style selects the default cell XF (index 0). Without a style
    table, it uses the intrinsic defaults. Invalid/negative/out-of-range cell
    style indices yield no protection attributes. Invalid boolean values and
    applyProtection values are unknown, not affirmative restrictions.
  - Retain the existing blank-cell and reading-window policy; protection does
    not materialize every empty grid location. An omitted flag is not evidence
    that the cell is editable, especially when its style is unreadable.

### `formulaHidden`

- **Output**
  - Semantic cell/@formula-hidden=true only with enabled saved sheet protection,
    a resolved nonempty formula, and an effective hidden=true setting. False,
    unknown, non-formula and inactive settings are omitted at every density.

- **OOXML**
  - xf/protection/@hidden.

- **IR**
  - Optional cell-format boolean, resolved with the same inheritance/default
    algorithm as locked.

- **Parsing**
  - Default false; 1/true enables the saved formula-hiding setting.
  - Formula text remains available. These fields describe supported saved
    restrictions, not a computed user permission model. The parser neither
    enforces protection nor opens password/allowed-edit-range exceptions.
  - Row/column/sheet visibility is independent of formula hiding.

## Example

```xml
<sheet-protection/>
<grid ref="A1:C1"><tr number="1">
  <cell locked="true">Read-only value</cell>
  <cell>Editable value</cell>
  <cell formula="A1*2" locked="true" formula-hidden="true">4</cell>
</tr></grid>
```
