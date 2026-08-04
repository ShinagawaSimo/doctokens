# XLSX 解析输出格式说明

本文档面向下游开发者和 LLM tool description 编写者，解释 `xlsx-llm-parser` 输出的语义 HTML5 标记格式。
文档随开发阶段逐步更新。

当前阶段：**B1 — 最小端到端解析骨架**（2026-08-05）

## 总体设计

解析器将 `.xlsx` 工作簿转化为结构化的 HTML5 标记输出。三种密度与 DOCX 解析器一致：

| 密度 | 枚举值 | 内容 |
|---|---|---|
| 语义级 | `semantic` | 完整网格 + 单元格坐标 + 数据类型 + 样式语义（待开发） |
| 结构级 | `structural`（默认） | sheet 边界 + 坐标 + 单元格可读值 |
| 纯文本 | `plain` | 制表符分隔的单元格值（待开发） |

XLSX 默认密度为 structural，因为大型工作簿常见。

## 隐式闭合规则

块级元素省略闭合标签，与 DOCX 解析器一致。

**隐式闭合的块级元素**：`<sheet>`、`<grid>`、`<tr>`、`<td>`

## 当前能力（B1）

### 工作表 `<sheet>`

```
<sheet name=Sheet1>
<sheet name=Calculations hidden>
<sheet name=Archive veryHidden>
```

- `name`：工作表名称（Excel 内唯一，是 `read_range()` 的定位符）
- `hidden` / `veryHidden`：仅不可见时输出；可见状态省略

### 网格 `<grid>`

```
<grid ref=A1:B3>
<tr><td>Product<td>Price
<tr><td>Widget<td>99
```

- `ref`：实际单元格占据的 A1 范围（扫描计算，不信任 OOXML `<dimension>` 声明）
- `<tr>`：行。默认行号从 `ref` 起始行连续递增
- `<td>`：单元格
- `row=`：仅实际行号不连续时输出（恢复位置）
- `col=`：仅行内列号不连续时输出（恢复位置）

### 支持的单元格类型

| `t=` | 含义 | 处理 |
|------|------|------|
| `inlineStr` | 内联字符串 | 读取 `<is><t>` 文本 |
| 无 / `n` | 数字 | 读取 `<v>` 原文 |
| `b` | 布尔 | `"1"` → `true`，`"0"` → `false` |
| `e` | 错误 | 保留原值如 `#DIV/0!` |

### 尚未支持（后续阶段）

- `t="s"` 共享字符串（B3）
- 日期/时间格式化（C1）
- 公式（C2）
- 合并单元格（C4）
- 样式、富文本、超链接、批注
- 图表、数据透视表、图片

## 坐标隐式推进规则

`<grid ref=A1:D4>` 给出范围后：

```
<grid ref=A1:D4>
<tr><td>产品<td>地区<td>销量<td>金额     ← 从 A1 起，列连续推进
<tr><td>A<td>华东<td>12<td>3600          ← 行连续推进
```

遇到空白区时，用 `row=` / `col=` 恢复位置：

```
<tr row=8><td>折现率<td col=F>8.0%
```

## 公共 API

```python
from xlsx_llm_parser import parse_xlsx, render_workbook, iter_workbook

wb = parse_xlsx("workbook.xlsx")
html = render_workbook(wb)
```

- `parse_xlsx(source)` — 解析 `.xlsx` 文件或 bytes
- `render_workbook(wb)` — 渲染完整 structural HTML5 字符串
- `iter_workbook(wb)` — 流式渲染，供大工作簿使用
