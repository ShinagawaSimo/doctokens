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

超出预算（500 格）时停止输出剩余行，`<grid>` 标记 `truncated`，由模型通过 `render_range` 按需读取：

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

Excel 单元格的 `numFmt` 是数值的显示格式，不是段落或文本流的自动编号定义。XLSX 不提供与 Word 列表或 PowerPoint 文本自动编号等价的段落级编号体系，因此本解析器不生成项目符号、列表序号或编号状态。

## 范围读取

`parse_xlsx(source, sheet=..., range_spec=..., density=...)` 解析源文件并按 A1 范围筛选单元格，返回包含 `<grid ref=...>` 的 `ParseResult`。session 可通过 `render(sheet=..., range_spec=...)` 重复执行相同读取。

```python
from xlsx_llm_parser import parse_xlsx

result = parse_xlsx("workbook.xlsx", sheet="Sheet1", range_spec="B2:D10")
```

## 公共 API

`parse_xlsx()` 接受源文件路径或 bytes，并返回 `ParseResult`。内部 IR（`ParsedWorkbook`）不暴露为公开 API；需要连续读取时使用 context-managed session。

```python
from xlsx_llm_parser import open_xlsx, parse_xlsx

# 主入口：解析并渲染完整工作簿
result = parse_xlsx("workbook.xlsx")  # structural（默认）
semantic = parse_xlsx("workbook.xlsx", density="semantic")
window = parse_xlsx("workbook.xlsx", sheet="Sheet1", range_spec="A1:H30")

with open_xlsx("workbook.xlsx") as workbook:
    grid = workbook.render(sheet="Sheet1", range_spec="A1:H30")
    matches = workbook.find_cells("预算")
    rows = workbook.query_data(table_id="Orders", limit=20)
    image_bytes = workbook.read_resource("image", "image1")
```

- `parse_xlsx(source, *, density, sheet?, range_spec?, options?)` — 返回文本、report 和资源目录
- `open_xlsx(source, *, options?)` — 打开 `XlsxReadSession`
- `session.render(sheet?, range_spec?, density?)` — 渲染完整工作簿、单个工作表或指定 A1 区域
- `session.iter_render(...)` — 迭代已解析 IR 的输出块

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

## 批注

旧式批注（`xl/commentsN.xml`）解析 authors 和 commentList，通过 sheet 的 relationship 关联。structural 和 semantic 均输出内联 `<commentref id=commentN/>` 和网格后 `<comment>` 块：

```
<tr row=1><td>8.0%<commentref id=comment0/>
<comment id=comment0 cell="'Inputs'!B4" author=Alice>采用审计批准的折现率
```

## Excel Table (ListObject)

`xl/tables/tableN.xml` 中声明的 ListObject 在 structural 中输出 `<table id=... name=... ref=...>`；semantic 额外输出 `cols="Col1,Col2"` 和 `totalsRow`。Table 定位不复制 grid 中的实际数据。

## Defined Name（仅 semantic）

`<definedNames>` 中的用户定义名称（非 `_xlnm.*` 内置名）在 semantic 中输出：

```
<definedName name=DiscountRate refersTo="0.08">
<definedName name=TaxRate refersTo="'Data'!$B$1">
```

## 筛选与排序

`<autoFilter>` 在 structural 中输出 `<filter ref=A1:K50>`；semantic 额外输出 `<condition>` 条件。

## 数据验证（仅 semantic）

`<dataValidations>` 在 semantic 中输出 `<dataValidation ref=... type=.../>`。

## 条件格式（仅 semantic）

`<conditionalFormatting>` 在 semantic 中输出范围及含公式的 `<rule>`。

## 外部引用（仅 semantic）

definedName 中检测到的 `[Budget.xlsx]` 外部引用输出为 `<externalLink target=.../>`。

## Drawing、图片与图表

`xl/drawings/drawingN.xml` 中锚定的图片和图表在 structural/semantic 中输出：

```
<image id=image1 ref=A1/>
<chart id=chart1 ref=D5 type=bar series=3/>
<pivotTable id=pivot1/>
```

图片 bytes 通过 `session.read_resource("image", id)` 读取，图表详情通过 `session.render_resource("chart", id)` 按需获取。图表标签恒带 `truncated`——其语义是"这是摘要视图"。

## 专项工具

`find_cells()` 和实验性的 `query_data()` 是 `XlsxReadSession` 方法。`read_resource("image", id)` 返回原始嵌入 bytes；`render_resource("chart", id)` 或 `render_resource("pivot_table", id)` 返回 `ParseResult`。未知工作表或资源 ID 分别抛出 `KeyError`；非法范围和参数抛出 `ValueError`。

## 架构边界

XLSX parser 只负责读取 package、解析确定性 SpreadsheetML 结构、生成 workbook/cell IR 和密度输出。`query_data` 目前是实验性、有限能力的下游辅助查询，不执行完整 SQL、公式求值或外部刷新。源文件缓存、跨请求 loaded session、重复文件参数去重、分块、检索、向量化和模型调用属于下游消费者；parser 不设置隐式全局缓存，也不替下游维护文档生命周期。

没有 `stream` 布尔参数。`iter_render()` 只迭代已解析 IR 的输出，不承诺流式解析或常量内存。
