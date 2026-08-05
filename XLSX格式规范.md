# XLSX 解析输出格式说明

本文档面向下游开发者和 LLM tool description 编写者，解释 `xlsx-llm-parser` 输出的语义 HTML5 标记格式。

## 总体设计

解析器将 `.xlsx` 工作簿转化为结构化的 HTML5 标记输出。三种密度与 DOCX 解析器一致：

| 密度 | 枚举值 | 内容 |
|---|---|---|
| 语义级 | `semantic` | 完整网格 + 单元格坐标 + 数据类型 + 样式语义（待开发） |
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
<grid ref=A1:D5>
<tr row=1><td>Product<td>Q1<td>Q2<td>Q3
<tr row=2><td>Widget<td>99<td col=E>150
<tr row=5><td>Gadget<td col=D>42
```

- `ref`：实际单元格占据的 A1 范围（扫描计算，不信任 OOXML `<dimension>` 声明）
- `<tr>`：行。`row=N` 始终输出真实 Excel 行号
- `<td>`：单元格。列在 `<td>` 间隐式连续推进
- `col=`：仅当列号不连续时输出（恢复真实 Excel 列位置）

### 大表格截断

超出预算（200 格 / 20 行 / 12 列）时保留 head + tail 样本，`grid ref` 显示完整范围并标记 `truncated`：

```
<grid ref=A1:A50000 truncated>
<tr row=1><td>Header
...
<tr row=8><td>Row8
<tr row=49997><td>Row49997
...
<tr row=50000><td>Row50000
```

### 坐标规则

`row=N` 始终输出真实 Excel 行号。`col=` 仅当列跳跃时出现：

```
<grid ref=A1:F10>
<tr row=3><td>折现率<td col=F>8.0%
```

### 单元格值

所有单元格输出可读显示值：

| `t=` | 含义 | 输出 |
|------|------|------|
| 无 / `n` | 数字 | 日期格式 → ISO 8601；百分比格式 → `12.5%`；否则原文 |
| `s` | 共享字符串 | `xl/sharedStrings.xml` 索引查找 |
| `inlineStr` | 内联字符串 | `<is><t>` 原文 |
| `str` | 公式结果字符串 | `<v>` 缓存结果 |
| `b` | 布尔 | `"1"` → `true`，`"0"` → `false` |
| `e` | 错误 | 保留原值如 `#DIV/0!` |
| `d` | ISO 日期 | `<v>` 原文 |

### 数字格式化

解析 `xl/styles.xml` 中的数字格式定义，对 `t="n"` 且带 `s` 属性的单元格应用格式化：

- **日期**：numFmtId 14–81 或自定义格式含日期 token（`y`/`m`/`d`/`h`/`s`）→ 解码序列号为 ISO 8601 日期
- **百分比**：numFmtId 9/10 或格式含 `%` → 乘以 100 追加 `%`
- 支持 1900 和 1904（Mac）双日期系统
- 无 `styles.xml` 时安全降级为原始数值

## 范围读取

`render_range(wb, sheet, range, density=...)` 按 A1 范围筛选单元格，返回 `<grid ref=...>` 块：

```python
from xlsx_llm_parser import render_range

html = render_range(wb, "Sheet1", "B2:D10")
```

## 公共 API

```python
from xlsx_llm_parser import parse_xlsx, render_workbook, render_range, iter_workbook

wb = parse_xlsx("workbook.xlsx")
html = render_workbook(wb)                      # structural（默认）
html = render_workbook(wb, density="plain")     # 纯文本
part = render_range(wb, "Sheet1", "A1:H30")     # 按范围筛选
```

- `parse_xlsx(source)` — 解析 `.xlsx` 文件或 bytes
- `render_workbook(wb, *, density)` — 渲染完整工作簿
- `render_range(wb, sheet, range, *, density)` — 渲染指定 A1 范围
- `iter_workbook(wb, *, density)` — 流式渲染

## 尚未支持

- 公式原文保存
- 合并单元格
- 富文本格式、超链接、批注
- 图表、数据透视表、图片
