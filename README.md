# doctokens

> **为 LLM 下游消费而生的 Office 文档解析工具集——零外部依赖、LLM友好、忠于实际任务需求的结构解析方式**。

实际对话场景中，用户对 DOCX/XLSX 文档常有以下类型的需求：

* 这篇文档第3页概括了哪些内容？

* 能不能帮我获取文章脚注中引用的文献？

* 文章中标红的部分能被怎么优化修改？

* 这个 Excel 里"合计"列的数字是怎么算出来的？

* 帮我找出所有同比增长超过 20% 的行。

当前市场中常见的 agent 工具中，文档解析流程基本会直接使用发展成熟的各种解析库，如 Docling、MarkItDown、Pandoc 等，将 `.docx`/`.xlsx` 转化为 markdown 格式文本进行读取。然而它们都没有为实际与文档相关的需求进行优化设计，只是忠实地执行了格式转化的任务，LLM 常常无法从解析结果中获取到足以完成任务的信息。

> **当前状态：** DOCX、PPTX、XLSX 和 OCR 核心均已具备可用的 v1 解析能力。XLSX 的 `query_data` 仍是实验性 SQL-like 查询层，尚未覆盖完整 SQL 语义、公式求值、缓存或外部数据刷新；生产调用应以解析出的原始值和公式文本为准。

常见的文档解析流程通常会面对以下问题：

* 脚注、尾注、编号、文本框文字等文字信息丢失；
* 下划线、文字颜色、高亮、上下标等内联格式未处理（大部分库只处理粗体、斜体）；
* 嵌套表格、图表、SmartArt 等复杂结构无法获得信息；
* **文字所在页数信息无法获取**。这明明是常见的需求场景，然而现有流程基本都完全没有进行处理，LLM 既不能从解析结果中直接获得页数信息，也不能获取到字体、行距等信息稍作估算，通常只能乱猜一个范围或者重问一次；
* Excel 合并单元格展开后丢失结构语义、公式只保留计算值、透视表直接被忽略；
* 精度更高的解析工具，往往依赖重、速度慢；
* 采用 markdown 之外的其它格式作为解析结果，往往浪费 token；
* 模型无法控制自己获取信息的密度，获取到的大量格式信息可能对简单需求（如"为我概括这篇文章"）毫无用处，同样是对 token 的浪费。

`doctokens` 是一个专为 **LLM 下游消费** 设计的文档解析工具集，在设计之初便遵循以下理念：

1. **忠于实际对话需求**。

   * 所有的在原始文档中出现的文字信息，均会以合适的方式进入文字流；

   * 在最高信息密度等级的解析中，文本的各种格式数据均被妥善地处理；（字体及字号信息被有意地排除在外——能有"帮我总结微软雅黑字体的14号字的内容"这种需求的人，就让大模型生成脚本狠狠地耗他的 token 吧。）

   * `<page=N>` 的标记将会出现在对应页面的第一个段落前，并提供页码窗口区间读取工具；

   * 复杂结构（图表、SmartArt、透视表）可以选择性解析并按需读取。

2. **极致轻量化**。

   * 核心解析器**不依赖任何第三方库**（包括 `python-docx`、`openpyxl`）、系统级工具（LibreOffice / Word COM）、GPU 模型，即插即用；

   * 各解析器（docx、xlsx、pptx 及后续的 pdf）均可单独安装配置；

   * OCR 作为可选适配层独立存在，按需引入引擎依赖，不影响核心解析器的零依赖特性。

3. **LLM 友好**。

   * 标签及属性名基本上使用了 LLM 训练语料中常见的 HTML 语义（`<b>`、`<table>`、`<a href=...>`、`colspan`），避免大模型额外的理解成本；

   * 提供**三种信息密度**（plain / structural / semantic）供 LLM 按需选择粒度，以及**页码窗口读取**和**按需资源提取**，避免为一个简单问题加载全文。
   * `stream=True` 只表示流式输出（未来也可扩展为流式输入），不表示流式解析；当前实现会先完成解析，再返回输出迭代器。

---

### 项目组成

```
doctokens/
  ooxml_llm_core/     # 共享基础设施：ZIP 包读取、关系索引、XML 工具、debug/metrics
  docx_llm_parser/    # DOCX → 语义 HTML5（标题、表格、编号、脚注、修订、公式、图表、SmartArt）
  xlsx_llm_parser/    # XLSX → 结构化 HTML5（合并单元格、公式、数据表、透视表、实验性 SQL-like 查询）
  pptx_llm_parser/    # PPTX → 幻灯片结构化 HTML5（备注、批注、主题、母版、图表、SmartArt）
  ocr_llm_core/       # OCR 可选适配层（Tesseract / EasyOCR / PaddleVL），为 PDF 解析做准备
```

核心解析能力：

**DOCX**

| 元素 | 标签 | 说明 |
|------|------|------|
| **标题** | `<h1>`–`<h6>` | 基于样式链的六级标题层级 |
| **段落** | `<p>` | 文本段落，含所有内联格式标注 |
| **表格** | `<table>`, `<tr>`, `<th>`, `<td>` | 合并单元格、嵌套表、表头完整还原 |
| **自动编号** | — | 多级编号文本还原（如 "3.1.2"） |
| **超链接** | `<a>` | 内部书签 + 外部 URL |
| **公式** | `<equation>` | 原生公式转可读文本 |
| **图表** | `<chart>` | 类型、标题、系列摘要 |
| **SmartArt** | `<smartart>` | 节点文本 + 连接关系摘要 |
| **图片** | `<img>` | 嵌入图片按需提取 |
| **文本框** | `<textbox>` | 文本框内容提取 |
| **脚注 / 尾注** | `<footnoteref>`, `<endnoteref>` | 引用标记 + 内容独立展示 |
| **批注** | `<commentref>` | 引用标记 + 内容独立展示 |
| **页眉 / 页脚** | — | 内容独立展示 |
| **修订追踪** | `<ins>`, `<del>` | final / original / review 三策略 |
| **域代码** | `<field>` | 超链接、页码引用、交叉引用 |
| **分页标记** | `<page=N>` | 渲染分页位置标记 |

**XLSX**

| 元素 | 标签 | 说明 |
|------|------|------|
| **单元格** | `<td>`, `<th>` | 值、公式、格式、数据类型 |
| **合并单元格** | `colspan`, `rowspan` | 合并语义保留 |
| **公式** | — | 原始公式文本 + 共享公式展开 |
| **数据表** | `<table>` | 结构化表格提取，含列名和范围 |
| **数据透视表** | `<pivotTable>` | 轻量摘要（布局 + 字段） |
| **图表** | `<chart>` | 类型、标题、系列摘要 |
| **图片** | `<image>` | 嵌入图片按需提取 |
| **定义名称** | `<definedName>` | 命名范围识别和搜索 |
| **批注 / 超链接** | `<comment>`, `<a>` | 按单元格关联 |

**PPTX**

| 元素 | 标签 | 说明 |
|------|------|------|
| **幻灯片** | `<slide>` | 按 `sldIdLst` 顺序输出，保留隐藏状态 |
| **标题 / 文本** | `<title>`, `<p>` | 占位符角色、段落、项目符号和内联格式 |
| **图片 / 媒体** | `<img>`, `<media>` | 外部资源只记录关系，嵌入资源按需读取 |
| **表格** | `<table>` | 合并单元格、行列切片和聚合资源查询 |
| **图表 / SmartArt** | `<chart>`, `<smartart>` | 图表系列、数据点、节点和连接摘要 |
| **备注 / 批注** | `<notes>`, supplemental | 演讲者备注和 threaded comments 独立保留 |
| **主题 / 母版** | — | 解析继承后的有效主题色、几何和占位符信息 |

---

### 安装

Python ≥ 3.10。

**完整安装（所有包）：**

```bash
pip install -e .
```

**独立安装（按需选择）：**

```bash
pip install -e packages/ooxml_llm_core    # 共享基础设施（各格式解析器依赖此项）
pip install -e packages/docx_llm_parser   # 仅 DOCX 解析
pip install -e packages/xlsx_llm_parser   # 仅 XLSX 解析
pip install -e packages/pptx_llm_parser   # 仅 PPTX 解析
pip install -e packages/ocr_llm_core      # OCR provider 核心
```

每个解析器只依赖 `ooxml-llm-core`，相互之间无耦合。

OCR 引擎可选依赖（按需安装，不影响核心包）：
```bash
pip install -e ".[ocr]"         # OCR provider 核心
pip install -e ".[tesseract]"   # Tesseract adapter + Pillow
pip install -e ".[easyocr]"     # EasyOCR + PyTorch + Pillow
pip install -e ".[paddle]"      # 内置 PaddleOCR-VL 云 API adapter（无额外本地依赖）
pip install -e ".[all]"         # OCR 核心及本地引擎依赖
```

---

### 架构边界

本项目是 Office 文档解析器的底层架构，不是下游 agent 运行时。解析器只负责读取 OOXML package、解析确定性结构、生成格式专属 IR，并渲染 LLM 可消费的输出。

源文件缓存、跨请求的读取会话、避免下游反复传入相同文件参数、调用去重、任务编排、分块策略、向量化和模型提示词均属于下游消费者或平台层职责。解析器不引入隐式全局缓存，也不替下游保存文档生命周期。

三种格式保留各自的导航单元和 IR；共享层只承载 OPC package、关系、XML、图表、限制和诊断等确实共用的基础设施，不为了表面统一引入空泛的 Office 文档基类。

连续执行多个读取操作时，下游可以显式创建 loaded/session facade 复用一次解析结果：DOCX 使用 `load_docx()`，XLSX 使用 `load_xlsx()`，PPTX 使用 `open_pptx()` 上下文管理器。便利函数仍然是无状态入口，不会隐式缓存源文件。

---

### API

**DOCX：**

```python
from docx_llm_parser import parse_docx, render_window, get_resource, Density

# 解析渲染
html = parse_docx("example.docx")
html = parse_docx("example.docx", density=Density.STRUCTURAL)

# 流式输出（大文档或网络传输场景）
for chunk in parse_docx("large.docx", stream=True):
    send(chunk)

# 按页读取
content = render_window("example.docx", page=3)
last_page = render_window("example.docx", page=-1)  # 最后一页

# 按需提取资源
image = get_resource("example.docx", "image", "img3")
table = get_resource("example.docx", "table", "t2")
```

**XLSX：**

`query_data` 当前是实验性能力。它支持有限的投影、筛选、分组、聚合和排序，不执行公式求值、外部刷新或完整 SQL 语义；不支持的操作会显式报错。

```python
from xlsx_llm_parser import parse_xlsx, render_range, find_cells, query_data, get_resource

# 解析渲染
text = parse_xlsx("example.xlsx")
text = parse_xlsx("example.xlsx", density="plain")

# 流式输出
for chunk in parse_xlsx("large.xlsx", stream=True):
    send(chunk)

# 按范围渲染
html = render_range("example.xlsx", sheet="Sheet1", range_spec="A1:D20")

# 全文搜索
results = find_cells("example.xlsx", "预算", limit=50)

# SQL-like 查询
rows = query_data(
    "sales.xlsx",
    table_id="Orders",
    select=["产品", "金额"],
    where=[{"column": "金额", "op": "gt", "value": 10000}],
    limit=20,
)

# 按需提取资源
chart = get_resource("example.xlsx", "chart", "chart1")
```

**PPTX：**

```python
from pptx_llm_parser import parse_pptx, iter_slides, render_window, get_resource, Density

html = parse_pptx("deck.pptx")
html = parse_pptx("deck.pptx", density=Density.STRUCTURAL)

for chunk in iter_slides("deck.pptx", density=Density.PLAIN):
    send(chunk)

content = render_window("deck.pptx", slide=3, span=2)
chart = get_resource("deck.pptx", "chart", "chart1")
```

显式复用入口：

```python
from docx_llm_parser import load_docx
from xlsx_llm_parser import load_xlsx
from pptx_llm_parser import open_pptx

doc = load_docx("example.docx")
doc_html = doc.render()
doc_page = doc.render_window(page=3)

workbook = load_xlsx("example.xlsx")
sheet = workbook.render_range("Sheet1", "A1:D20")
matches = workbook.find_cells("预算")

with open_pptx("deck.pptx") as presentation:
    slide = presentation.render_window(slide=2)
    report = presentation.report.to_dict()
```

#### 三种密度

| 密度 | 输出 | 典型场景 |
|------|------|----------|
| **plain** | 纯文本，段落间 `\n\n` 分隔 | 概括全文、分类、提取关键词 |
| **structural** | 块级 HTML5（无粗体/斜体/颜色等格式） | 定位段落、对比段落、读取表格 |
| **semantic** | 完整语义 HTML5（含所有格式 + 链接 + 公式） | 理解格式语义、链接目标、公式结构 |

每种密度下脚注、尾注、页码、表格的处理策略不同。plain 将脚注文本拼接到引用段落末尾、尾注拼接到文档末尾、表格退化为 `\t` 分隔文本；structural 和 semantic 保留引用标记并将完整内容放在独立区域。

#### API 速查

**docx_llm_parser**

| 函数 | 说明 |
|------|------|
| `parse_docx(source, *, density, stream?, options?)` | 解析 DOCX 并渲染为字符串或输出迭代器；stream 不表示流式解析 |
| `render_window(source, *, page, span?, density?, options?)` | 返回指定页码范围的内容片段 |
| `get_resource(source, resource_type, resource_id)` | 获取单个资源详情（图片/图表/表格等） |
| `load_docx(source, *, options?)` | 显式加载一次，返回可重复 render/window/resource 的 `LoadedDocx` |

**xlsx_llm_parser**

| 函数 | 说明 |
|------|------|
| `parse_xlsx(source, *, density, start_row?, stream?, options?)` | 解析 XLSX 并渲染为字符串或输出迭代器；stream 不表示流式解析 |
| `render_range(source, *, sheet, range_spec, density?)` | A1 风格区域渲染 |
| `find_cells(source, query, *, sheets?, kind?, limit?)` | 搜索单元格值/公式/批注/超链接/定义名称 |
| `query_data(source, *, table_id?, sheet?, range_spec?, select?, where?, group_by?, aggregates?, order_by?, limit?)` | 实验性 SQL-like 结构化查询 |
| `get_resource(source, resource_type, resource_id)` | 获取资源元数据（image/chart/pivot_table/embedded_object） |
| `load_xlsx(source, *, options?)` | 显式加载一次，返回可重复 render/range/search/query/resource 的 `LoadedWorkbook` |

**pptx_llm_parser**

| 函数 | 说明 |
|------|------|
| `parse_pptx(source, *, density, stream?, options?)` | 解析 PPTX 并渲染为字符串或逐幻灯片迭代器 |
| `iter_slides(source, *, density, start_slide?, options?)` | 解析完成后逐幻灯片输出，批注作为尾部 supplemental 分块 |
| `render_window(source, *, slide, span?, density?, options?)` | 返回指定幻灯片窗口 |
| `get_resource(source, resource_type, resource_id, ...)` | 提取图片、媒体、图表、SmartArt 或表格资源 |
| `open_pptx(source, *, options?)` | 打开 context-managed `PptxReadSession`，复用一次解析结果 |

---

### OCR 适配层

`ocr_llm_core` 是可选模块，为 Office 文件中的图片及 PDF 扫描页提供 OCR 引擎的统一抽象：

| Provider | 引擎 | 特点 |
|----------|------|------|
| `TesseractProvider` | Tesseract | 轻量，适合纯文本 OCR |
| `EasyOcrProvider` | EasyOCR | 中文识别好，需要 PyTorch |
| `PaddleVLProvider` | PaddleVL | 视觉-语言联合，支持版面分析 |

```python
from ocr_llm_core import TesseractProvider

provider = TesseractProvider(lang="chi_sim+eng")
text = provider.extract(open("scan.jpg", "rb").read())
```

---

### 路线图

- [x] DOCX 解析器（semantic / structural / plain）
- [x] XLSX 解析器（structural HTML5 + 实验性 SQL-like 查询）
- [x] PPTX 解析器（幻灯片结构、备注、批注、主题、母版、图表、SmartArt）
- [x] OCR 适配层（Tesseract / EasyOCR / PaddleVL）
- [ ] **PDF 解析器**——基于 `ocr_llm_core` 的扫描件 OCR + 原生文本层混合解析

---

### 运行测试

```bash
python -m pytest packages/ -v
```
