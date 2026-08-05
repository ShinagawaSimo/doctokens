# XLSX 解析输出格式说明

本文档面向下游开发者和 LLM tool description 编写者，解释 `xlsx-llm-parser` 输出的语义 HTML5 标记格式。

## 总体设计

解析器将 `.xlsx` 工作簿转化为结构化的 HTML5 标记输出。三种密度与 DOCX 解析器一致：

| 密度 | 枚举值 | 内容 |
|---|---|---|
| 语义级 | `semantic` | 完整网格 + 单元格坐标 + 样式语义 + 公式 + 合并 + 溢出 |
| 结构级 | `structural`（默认） | sheet 边界 + 坐标 + 单元格可读值 |
| 纯文本 | `plain` | 制表符分隔的单元格值，无坐标 |

XLSX 默认密度为 structural。输出首行标记密度（如 `density=structural`）。

## 隐式闭合规则

块级元素省略闭合标签，与 DOCX 解析器一致。

**隐式闭合的块级元素**：`<sheet>`、`<chartsheet>`、`<grid>`、`<tr>`、`<td>`

## 输出格式

### 工作表 `<sheet>` 与 `<chartsheet>`

```
<sheet name=Sheet1>
<sheet name=Calculations hidden>
<sheet name=Archive veryHidden>
<chartsheet name=Charts>
```

- `name`：工作表名称（Excel 内唯一，是 `read_range()` 的定位符）
- `hidden` / `veryHidden`：仅不可见时输出；可见状态省略
- `<chartsheet>`：仅图表页使用专用标签，不含 `<grid>` 内容
- 多 sheet 按 workbook.xml 声明顺序输出

### 网格 `<grid>`

```
<grid ref=A1:E5>
<tr row=1><td>Product<td>Q1<td>Q2<td>Q3
<tr row=2><td>Widget<td>99<td col=E>150
<tr row=5><td>Gadget<td col=D>42
```

- `ref`：实际单元格占据的 A1 范围（扫描计算，不信任 OOXML `<dimension>` 声明）
- `<tr>`：行。`row=N` 始终输出真实 Excel 行号
- `<td>`：单元格。列在 `<td>` 间隐式连续推进
- `col=`：仅当列号不连续时输出（恢复真实 Excel 列位置）

### 大表格截断

超出预算（500 格 / 50 行 / 30 列）时不输出行数据，仅标记 `truncated`，由模型通过 `render_range` 按需读取：

```
<grid ref=A1:Z1000 truncated>
```

### 坐标规则

`row=N` 始终输出真实 Excel 行号。`col=` 仅当列跳跃时出现：

```
<grid ref=A1:F10>
<tr row=3><td>折现率<td col=F>8.0%
```

### 单元格值

所有单元格输出可读显示值：

| 单元格类型 | 存储方式 | 输出 |
|------|------|------|
| `number` | `<v>` 数字或缺失 | 日期序列 → ISO 8601；百分比 → `12.5%`；否则原文 |
| `string` | 共享字符串 / 内联字符串 / 公式结果 | 解析后文本 |
| `boolean` | `<v>` 为 1 或 0 | `true` / `false` |
| `error` | `<v>` 错误码 | 保留原值如 `#DIV/0!` |
| `date` | `<v>` ISO 8601 | 原文 |

### 数字格式化

解析 `xl/styles.xml` 中的数字格式定义，对 `t="n"` 且带 `s` 属性的单元格应用格式化：

- **日期**：numFmtId 14–81 或自定义格式含日期 token（`y`/`m`/`d`/`h`/`s`）→ 解码序列号为 ISO 8601 日期
- **百分比**：numFmtId 9/10 或格式含 `%` → 乘以 100 追加 `%`
- 支持 1900 和 1904（Mac）双日期系统
- 无 `styles.xml` 时安全降级为原始数值

## 范围读取

`render_range(source, sheet, range_spec, *, density)` 解析源文件并按 A1 范围筛选单元格，返回 `<grid ref=...>` 块。不输出密度标记。

```python
from xlsx_llm_parser import render_range

html = render_range("workbook.xlsx", "Sheet1", "B2:D10")
```

## 公共 API

所有函数直接接受源文件路径或 bytes，内部完成解析和渲染。内部 IR（`ParsedWorkbook`）不暴露为公开 API。

```python
from xlsx_llm_parser import parse_xlsx, render_range, iter_workbook

# 主入口：解析并渲染完整工作簿
html = parse_xlsx("workbook.xlsx")                             # structural（默认）
html = parse_xlsx("workbook.xlsx", density="semantic")         # 语义级
html = parse_xlsx("workbook.xlsx", density="plain")            # 纯文本

# 流式迭代
for chunk in iter_workbook("workbook.xlsx", density="structural"):
    ...

# 范围读取
html = render_range("workbook.xlsx", "Sheet1", "A1:H30")       # structural（默认）
html = render_range("workbook.xlsx", "Sheet1", "A1:H30", density="semantic")
```

- `parse_xlsx(source, *, density)` — 解析并渲染完整工作簿
- `render_range(source, sheet, range_spec, *, density)` — 解析并渲染指定 A1 范围
- `iter_workbook(source, *, density)` — 解析并流式渲染

## 公式

semantic 密度下，`<td>` 可带公式属性：

```
<tr row=1><td formula="SUM(B1:B10)">42
<tr row=2><td formulaType=array formulaRange=A1:C3>1
```

共享公式自动展开：slave 单元格通过 `si` 索引找到 master，应用行列偏移量生成各自公式文本。

### 动态数组溢出（仅 semantic）

array 公式 `ref` 范围大于锚点单元格自身时，标记溢出关系：

```
<tr row=1><td formula="SORT(A1:A3)" formulaType=array formulaRange=B1:B3 spillRange=B1:B3>Alice
<tr row=2><td spillFrom="B1">Bob
```

- `spillRange`：锚点公式的溢出范围（A1 格式）
- `spillFrom`：溢出从属单元格，值为源公式的 A1 地址

## 合并单元格

semantic 密度下，左上角单元格输出 `colspan=N rowspan=N`，shadow 格跳过：

## 样式（仅 semantic）

`<td>` 可带 `bold`、`italic`、`underline`、`color=#RRGGBB`、`fill=#RRGGBB` 属性。

颜色来源包括显式 RGB 值和主题色引用：`xl/styles.xml` 中的 `<color theme="N"/>` 通过解析 `xl/theme/theme1.xml` 的 `clrScheme` 映射为 RGB；`tint` 属性按 OOXML 规范线性插值亮/暗变化。theme1.xml 缺失时降级为 Office 默认主题色。

## 隐藏行与隐藏列

`<row hidden="1">` 在 structural 和 semantic 中输出 `<tr row=N hidden>`。

隐藏列通过 `<cols><col hidden="1"/>` 解析，以 `<columns ref=C:D hidden/>` 标注在 `<grid>` 之前。隐藏列中的单元格照常输出，不另加标记。

## 大纲分组（仅 semantic）

`<row outlineLevel="1" collapsed="1">` 在 semantic 中输出 `<tr outlineLevel=N collapsed>`，structural 忽略。

## 保护（仅 semantic）

`<sheetProtection>` 存在时，semantic 在 `<grid>` 前输出 `<sheetProtection/>`。

单元格 `xf` 中 `<protection locked="0">` 输出 `<td unlocked>`，`<protection hidden="1">` 输出 `<td formulaHidden>`。Excel 默认已锁定且公式可见，仅非默认值输出。

## 富文本（仅 semantic）

共享字符串中的格式化 run 展开为内联 `<b>`、`<i>`、`<u>`、`<color>` 标记。

## 超链接

`<hyperlink>` 通过 relationship 解析外部 URL 或内部位置。structural 和 semantic 均输出 `<a href="...">` 包裹单元格正文：

```
<tr row=1><td><a href="https://example.com">Click</a>
<tr row=2><td><a href="#Sheet2!B5">Go
```

## 尚未支持

- 批注
- 图表、数据透视表、图片
