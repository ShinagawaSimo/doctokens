# doctokens

> **面向 LLM 下游消费的 Office 文档解析工具集：直接读取 OOXML，保留阅读所需的结构与语义，按任务选择信息密度。**

实际对话中，用户对 Office 文档常有这样的需求：

- 这篇文档第 3 页讲了什么？
- 能不能帮我获取脚注里引用的文献？
- 文章中标红的部分可以怎样修改？
- 这张幻灯片的演讲者备注补充了什么？
- Excel 里“合计”列的数字是怎么算出来的？哪些行的金额超过了 100？

只提取正文，往往不足以回答这些问题。编号、脚注、修订和批注可能包含关键内容；颜色和高亮可能表达作者的意图；表格需要保留合并关系，工作簿需要同时看到公式与保存的结果。另一方面，概括全文时又不一定需要所有格式细节。

`doctokens` 围绕这些实际任务提供 DOCX、PPTX、XLSX 三种解析器。当前正文输出为 **DTP 1.0 纯文本**或 **DTX 1.0 XML**，并提供解析报告、显式读取会话和资源读取接口。它是读取工具，不负责修改或重新排版 Office 文件。

[解析行为参考](specifications/README.md) · [DOCX](specifications/docx/README.md) · [PPTX](specifications/pptx/README.md) · [XLSX](specifications/xlsx/README.md)

### 设计理念

1. **保留完成阅读任务需要的信息。** 正文之外，处理编号、附注、批注、公式、图表和 SmartArt；将强调、颜色、修订状态等放入 semantic 输出。DOCX 的页码来自文件保存的分页线索，便于按页读取。
2. **直接解析文件，依赖保持轻量。** 核心路径直接读取 ZIP/XML，不依赖 `python-docx`、`openpyxl`、Word COM 或 LibreOffice。各格式包可分别安装，OCR 引擎按需引入。
3. **让调用方控制读取粒度。** 提供 plain、structural、semantic 三档密度，以及页、幻灯片、工作表、单元格范围和资源读取。大表和复杂对象可能先输出摘要，需要时再读取细节。
4. **输出明确、生命周期明确。** XML 标签闭合、属性加引号并转义；返回值声明语法版本。重复读取使用 `open_*` 会话，调用方负责跨请求缓存和任务编排。

---

### 项目组成

```text
doctokens/
  packages/
    ooxml_llm_core/   # OPC 包、关系、XML、共享图表与输出基础设施
    docx_llm_parser/  # Word：段落、编号、表格、分页、附注、修订、对象
    pptx_llm_parser/  # PowerPoint：幻灯片、形状、文字、备注、批注、对象
    xlsx_llm_parser/  # Excel：网格、公式、样式、规则、透视表、检索与查询
    ocr_llm_core/     # 可选 OCR 适配层
  specifications/    # 当前解析行为、输出字段与限制
  test_support/      # 真实 Office 文件、素材、golden 与手动更新脚本
  tests/             # 真实文件全文回归与更新脚本测试
  scripts/           # wheel 构建和安装验证
```

核心解析能力如下。表中标签指正文 DTX 输出；各密度保留的具体字段见[密度参考](specifications/common/density.md)。

**DOCX**

| 内容 | DTX 表达 | 说明 |
| --- | --- | --- |
| 标题与段落 | `<h1>`–`<h9>`、`<p>` | 基于大纲级别和样式继承解析，保留正文顺序 |
| 强调与颜色 | `<b>`、`<i>`、`<u>`、`<s>`、`<sup>`、`<sub>`、`<small-caps>`、`<color>`、`<mark>` | semantic 中保留已解析的阅读语义 |
| 自动编号 | 段落中的编号文本 | 多级占位组合、起点、续编、重启、项目符号及编号样式 |
| 表格 | `<table>`、`<tr>`、`<td>` | 合并、嵌套、跨页分段；完整表可按资源读取 |
| 链接、书签与域 | `<a>`、`<field>`、`<cite>` 及锚点属性 | 外部链接、内部跳转、域指令和保存的显示文字 |
| 公式 | `<equation notation="latex">` | 将支持的 OMML 结构转为 LaTeX 表达 |
| 图片、文本框、嵌入对象 | `<img>`、`<textbox>`、`<embedded>` | 文字、描述和对象引用；嵌入对象不等于递归解析其文件 |
| 图表与 SmartArt | `<chart>`、`<smartart>` | 摘要与资源细节，读取保存的数据和节点关系 |
| 脚注、尾注、批注 | `<footnote-ref>`、`<endnote-ref>`、`<comment-ref>` | 引用与附属正文；批注可包含回复、作者和解决状态 |
| 页眉与页脚 | `<supplemental>` 下的 `<headers>`、`<footers>` | semantic 中保留已解析内容 |
| 修订 | `<ins>`、`<del>` | final、original、review 三种视图 |
| 内容控件 | `<content-control>` | 类型、内容、选项、复选状态、锁定和绑定等 |
| 分页 | `<page number="N" />` | 保存分页提示；plain 使用独立的 `<page=N>` 行 |

**XLSX**

| 内容 | DTX 表达 | 说明 |
| --- | --- | --- |
| 工作表与网格 | `<sheet>`、`<grid>`、`<tr>`、`<cell>` | 稀疏坐标、行列顺序、隐藏与分组状态 |
| 合并单元格 | `colspan`、`rowspan` | 保留跨度和后续单元格位置 |
| 公式 | 单元格的 `formula` 等属性 | 保存的结果、公式文本、共享公式展开、数组与溢出信息；不计算公式 |
| 样式 | 单元格格式、内联标签、`<style-range>` | 字体强调、颜色、填充及支持的数字显示格式 |
| 数据表 | `<table-summary>` | 表名、范围、列信息；数据仍在网格中 |
| 筛选与规则 | `<filter>`、`<data-validation>`、`<conditional-format>` | 保存的条件、阈值和样式，不重新执行 Excel 的规则引擎 |
| 透视数据 | `<pivot-table>`、`<pivot-cache>`、`<slicer>`、`<timeline>` | 保存的布局、字段、缓存与关联信息，不刷新数据源 |
| 图片与图表 | `<img>`、`<chart>` | 锚点、资源引用和图表数据摘要 |
| 名称与外部引用 | `<defined-name>`、`<external-link>` | 命名范围、作用域和外部工作簿目标 |
| 批注与链接 | `<comment-ref>`、`<comment>`、`<a>` | 传统备注、现代批注线程和单元格链接 |
| 现代单元格 | `<cell>` 的控件、富值属性 | 支持的复选框、单元格内图片和保存的富值信息 |

**PPTX**

| 内容 | DTX 表达 | 说明 |
| --- | --- | --- |
| 幻灯片 | `<slide>` | 文件中的幻灯片顺序、隐藏状态和节名称 |
| 标题与文字 | `<title>`、`<p>` | 占位符角色、段落、项目符号、编号和内联格式 |
| 形状与连接 | `<shape>`，连接符使用 `kind="connector"` | 描述、对象身份和连接端点；公共密度保持源形状顺序 |
| 图片与媒体 | `<img>`、`<media>` | 嵌入图片、音视频；外部资源只记录目标 |
| 表格 | `<table>` | 单元格文字与合并；支持表资源切片和聚合 |
| 图表与 SmartArt | `<chart>`、`<smartart>` | 类型、系列、节点与资源细节 |
| 备注与批注 | `<speaker-notes>`、`<comments>` | 演讲者备注、批注及所属幻灯片 |
| 主题与模板 | 有效颜色、占位符信息 | 解析适用的主题、布局和母版默认值；不把模板提示文字插入正文 |

---

### 安装

Python ≥ 3.10。在仓库根目录安装需要的子包：

```sh
python -m pip install -e ./packages/ooxml_llm_core -e ./packages/docx_llm_parser -e ./packages/pptx_llm_parser -e ./packages/xlsx_llm_parser
```

只需要 Word 时，安装共享核心和 DOCX 包即可：

```sh
python -m pip install -e ./packages/ooxml_llm_core -e ./packages/docx_llm_parser
```

三个格式包互不依赖，共用 `ooxml_llm_core`。共享核心没有必需的第三方运行依赖；DOCX 另依赖 `typing_extensions`。OCR 的安装方式见下文。

### 架构边界

解析器负责 OOXML 包读取、关系解析、限制与诊断、格式专属中间表示（IR），以及文本和资源输出。分块、检索增强、向量化、模型调用、跨请求缓存由下游实现。

一次性 `parse_*` 根据密度与选区解析；`open_*` 会话保留后续读取需要的语义数据，退出 `with` 时关闭文件资源。两种入口的提取计划可能不同，尤其是对象摘要和诊断；不要假设不同计划得到完全相同的资源编号或细节。

`iter_render()` 迭代已解析内容的输出块，不表示流式解析，也不保证恒定内存占用。当前没有公开的 `stream`、`full` 或 `details` 参数。

### API

三个格式的一次性入口都接收路径或完整文件 bytes，返回 `ParseResult`：

```python
from docx_llm_parser import parse_docx
from pptx_llm_parser import parse_pptx
from xlsx_llm_parser import parse_xlsx

report = parse_docx("report.docx", density="semantic")
slides = parse_pptx("slides.pptx", density="structural")
sales = parse_xlsx("sales.xlsx", density="structural")

print(report.text)
print(report.report.to_dict())
print(report.resources)
print(report.selection, report.syntax_version, report.media_type)
```

**DOCX：分页、修订与资源**

```python
from docx_llm_parser import ParseOptions, open_docx

with open_docx("report.docx", options=ParseOptions(revision_mode="review")) as document:
    page = document.render(density="semantic", page_hint=3, span=1)
    last_page = document.render(density="plain", page_hint=-1)
    print(page.text)

    # 使用资源目录实际返回的 ID。
    for resource in document.resources:
        if resource.kind == "image" and resource.source == "embedded":
            image_bytes = document.read_resource("image", resource.id)
        elif resource.kind == "table":
            table = document.render_resource("table", resource.id)
            print(table.text)
```

**XLSX：范围读取、搜索与查询**

以下假设 Sales 表的 A1:C5 为 Name、Group、Amount 三列表格，首行为列名：

```python
from xlsx_llm_parser import open_xlsx

with open_xlsx("sales.xlsx") as workbook:
    grid = workbook.render(sheet="Sales", range_spec="A1:C5")
    matches = workbook.find_cells("Alice", sheets=["Sales"], limit=20)
    rows = workbook.query_data(
        sheet="Sales",
        range_spec="A1:C5",
        header_row=1,
        select=["Name", "Amount"],
        where=[{"column": "Amount", "op": "gt", "value": 10}],
        order_by=[{"column": "Amount", "direction": "desc"}],
        limit=2,
    )
    print(grid.text)
    print(matches.text)
    print(rows.text)
```

`query_data` 是实验性查询接口，支持有限的投影、筛选、分组、聚合和排序。它读取文件中保存的数据，不求值公式，不刷新外部连接，也不是完整 SQL 引擎。范围参数需带两端地址，单格写作 `A1:A1`。

**PPTX：幻灯片窗口与输出迭代**

```python
from pptx_llm_parser import open_pptx

with open_pptx("slides.pptx") as presentation:
    selected = presentation.render(slide=2, span=2, density="semantic")
    print(selected.text)
    for chunk in presentation.iter_render(density="plain"):
        print(chunk, end="")
```

#### 三种密度与输出语法

| 密度 | 语法与类型 | 典型用途 |
| --- | --- | --- |
| plain | `doctokens-plain/1.0`，`text/plain` | 概括、分类、提取文字；仍有元信息行和必要的导航标记 |
| structural | `doctokens-xml/1.0`，`application/xml` | 读取段落、表格、对象引用、工作表结构和公式 |
| semantic | `doctokens-xml/1.0`，`application/xml` | 在结构上增加已解析的强调、颜色、状态和对象关系 |

DTX 的根节点分别为 `<document>`、`<presentation>`、`<workbook>`，是闭合且可由 XML 解析器读取的文档。以下示例为便于阅读增加了缩进：

```xml
<document density="semantic" format="docx" pagination="last-rendered-hints" revision-view="final" schema="doctokens-xml" version="1.0">
  <body><page number="1" /><p>Hello <b>world</b>.</p></body>
</document>
```

对应的 plain 内容：

```text
density=plain format=docx pagination=last-rendered-hints revision_view=final syntax=doctokens-plain/1.0
<page=1>

Hello world.
```

PPTX 和 XLSX 的结构示例：

```xml
<presentation density="structural" format="pptx" schema="doctokens-xml" version="1.0">
  <slide number="1"><title placeholder="title">Quarterly report</title></slide>
</presentation>
```

```xml
<workbook density="structural" format="xlsx" schema="doctokens-xml" version="1.0">
  <sheet name="Sales"><grid ref="A1:B1"><tr number="1"><cell>Total</cell><cell>42</cell></tr></grid></sheet>
</workbook>
```

**资源、搜索和查询的解释性输出尚未迁移为 DTX。** `render_resource()`、`find_cells()`、`query_data()` 目前返回 `legacy-markup/0`、`text/plain`；即使含有类似标签的文本，也不能当作 XML。以 `ParseResult.syntax_version` 和 `media_type` 判断语法。二进制资源由 `read_resource()` 直接返回 bytes。

#### API 速查

| 入口 | 说明 |
| --- | --- |
| `parse_docx(source, density=..., page_hint=..., span=..., options=...)` | 全文或保存分页提示窗口；默认 semantic |
| `parse_pptx(source, density=..., slide=..., span=..., options=...)` | 全部或连续幻灯片；默认 semantic |
| `parse_xlsx(source, density=..., sheet=..., range_spec=..., options=...)` | 工作簿、工作表或区域；默认 structural |
| `open_docx` / `open_pptx` / `open_xlsx` | 显式 `with` 会话；通过 `render` 重复读取 |
| `session.iter_render(...)` | 在会话内迭代输出字符串 |
| `session.report` / `session.resources` | 诊断报告和资源目录 |
| `session.read_resource(kind, resource_id)` | DOCX/XLSX 支持图片，PPTX 支持图片和媒体；不下载外部目标 |
| `session.render_resource(kind, resource_id, ...)` | DOCX/PPTX 支持表格、图表、SmartArt；XLSX 支持图表和透视表摘要 |
| `workbook.find_cells(...)` / `workbook.query_data(...)` | 单元格搜索与实验性表格查询 |

所有选择参数均为关键字参数；详细签名、选项和限制见各格式的 [DOCX API](specifications/docx/api.md)、[PPTX API](specifications/pptx/api.md)、[XLSX API](specifications/xlsx/api.md) 与[会话参考](specifications/common/session.md)。

### Word 实显与规范

OOXML 格式定义说明文件如何表示内容，Microsoft 的实现说明记录 Word 与该规范的部分差异；两者仍未必覆盖本机 Word 的实际行为。尤其是编号格式，不能仅凭枚举名称推导最终字符，也不能把 Excel 列号算法直接用于 Word 列表。

本项目面向简体中文 Word 文件建立真实样例。遇到差异，以用户本机 Word 显示和人工确认的 golden 为依据；不宣称能够在所有语言、字体和 Office 版本中完全复现编号。

| 情况 | 需要区别的行为 |
| --- | --- |
| Word 字母编号 | 27、28 的扩展为 AA、BB；PowerPoint 的字母自动编号可为 AA、AB |
| 天干、地支 | 有效范围到 10、12；其后的项显示十进制 11、13，不回到甲、子 |
| 片假名编号 | 当前实现按 Word 行为循环序列，不能直接套用字符重复规则 |
| 中文数字与大写计数 | `〇`、`零`、`万`、`萬`，以及省“一”和补零位置，都需要实际文件确认 |

例如当前 `chineseCountingThousand` 的 10050 golden 为 `一万〇五十`，`chineseLegalSimplified` 为 `壹萬零伍拾`。这些是当前保存的基线，仍应由本机显示复核，不作为所有 Word 版本的保证。

相关资料：[OOXML 编号定义](reference/C071691e-17.18.59-ST_NumberFormat.md)、[Word 编号实现差异](reference/MS-OI29500-2.1.548-ST_NumberFormat.md)、[编号修订差异](reference/MS-OI29500-2.1.1772-numberingChange.md)。更完整的规范资料位于 `reference/`。

分页也有明确边界：DOCX 解析器读取显式分页、节信息和保存的渲染分页线索，**不运行 Word 排版引擎**。字体、纸张或环境改变后重新排版得到的页数，可能与文件中的旧线索不同。PPTX 公共输出同样不提供完整坐标或几何还原；相关内部能力不等于已公开的排版密度。

### OCR 适配层

OCR 默认关闭。DOCX、PPTX 可通过各自的 `ParseOptions(ocr=...)` 显式传入适配器；XLSX 当前没有该选项。

| Provider | 运行方式 | 额外要求 |
| --- | --- | --- |
| `TesseractProvider` | 本地 Tesseract | 安装 Tesseract 程序、语言包以及 Python 适配依赖 |
| `EasyOcrProvider` | 本地 EasyOCR | EasyOCR、PyTorch、模型文件；可配置 CPU/GPU |
| `PaddleVLProvider` | 云端服务适配 | 服务凭据和网络连接；使用时会向服务提交图片 |

以本地 Tesseract 为例：

```sh
python -m pip install -e "./packages/ocr_llm_core[tesseract]"
```

```python
from docx_llm_parser import ParseOptions, parse_docx
from ocr_llm_core import TesseractProvider

provider = TesseractProvider(lang="chi_sim+eng")
result = parse_docx("scan.docx", density="semantic", options=ParseOptions(ocr=provider))
print(result.text)
```

`chi_sim+eng` 需要本机安装简体中文和英文语言数据。OCR 结果附在相应图片附近；它补充图片中的文字，不重新解释文档里的原生文字。

### 路线图

- [x] DOCX、PPTX、XLSX 的三档 DTP/DTX 正文输出与显式读取会话
- [x] 可选 OCR 适配、资源读取和实验性工作簿查询
- [ ] 用小型真实 Office 文件逐步替代正常内容的手工 XML 测试，人工审查 golden
- [ ] 资源、搜索和查询输出的后续契约完善
- [ ] PDF 解析器
- [ ] 更细的只读排版信息及可编辑投影；`typography`、`geometry`、`full` 尚非公开 API

### 运行测试

安装开发依赖后，在仓库根目录运行：

```sh
python -m pip install -e ".[dev]" -e ./packages/ocr_llm_core
python -m pytest -q
```

真实 Office 文件位于 `test_support/fixtures/`，对应三档输出位于 `test_support/golden/`；手工创建清单见[Office 真实测试文件清单](docs/测试夹具与文件输出契约.md)。开发时比较当前输出与旧 golden；预期行为变化后，人工对照 Office 显示确认，再更新相应基线。单个文件的更新命令：

```sh
python test_support/update_goldens.py --only docx-list-decimal.docx
```

脚本支持 DOCX、PPTX、XLSX，按目录发现文件；省略 `--only` 更新全部文件。生成后人工审查输出。真实文件回归统一放在 `tests/test_file_goldens.py`，只做全文比较，缺少 golden 就报错；测试不会更新基线，也不受 `UPDATE_GOLDEN` 影响。
