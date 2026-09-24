# Bullet symbols

[DOCX](../README.md) / Bullet symbols

Bullet templates can contain literal Unicode or font-specific private-use characters.

## Processing

```python
def bullet_symbol(template: str | None, marker_font: str | None = None) -> str:
    if not template:
        return "•"
    symbols = {
        "\uf06c": "●",
        "\uf06e": "■",
        "\uf075": "◆",
        "\uf0b7": "•",
        "\uf0a7": "▪",
        "\uf0fc": "✓",
        "\uf0fd": "✓",
        "\uf0fe": "✕",
    }
    font_symbols = {
        "symbol": {"\uf0b7": "•", "\uf0a7": "▪", "\uf06c": "●", "\uf06e": "■", "\uf075": "◆"},
        "wingdings": {"\uf0a7": "▪", "\uf0b7": "•", "\uf0fc": "✓", "\uf0fd": "✓", "\uf0fe": "✕"},
        "wingdings 2": {"\uf0a7": "▪", "\uf0fc": "✓", "\uf0fe": "✕"},
        "wingdings 3": {"\uf0fc": "✓", "\uf0fe": "✕"},
    }
    font_key = (marker_font or "").strip().lower()
    resolved = font_symbols.get(font_key, {})
    return "".join(resolved.get(char, symbols.get(char, "•" if 0xE000 <= ord(char) <= 0xF8FF else char)) for char in template)
```

## Fields

### `template`

- **Output**
  - Visible bullet text.

- **OOXML**
  - `w:lvl/w:lvlText/@w:val`

- **IR**
  - `NumberingLevel.level_text: str | None`

- **Parsing**
  - An absent or empty template yields `"•"`. Otherwise convert each character independently; preserve ordinary characters.

### `marker_font`

- **Output**
  - Selects a symbol-font mapping.

- **OOXML**
  - `w:lvl/w:rPr/w:rFonts`

- **IR**
  - `NumberingLevel.marker_font: str | None`

- **Parsing**
  - Use `(marker_font or "").strip().lower()`. Font-specific mapping takes precedence over the generic mapping. Unknown private-use characters from U+E000 through U+F8FF become `"•"`.


## Source references

- [bullet_symbol](../../../packages/docx_llm_parser/src/docx_llm_parser/ooxml/numbering/models.py#L45)
