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

### 支持的内容

| 格式 | 主要能力 |
| --- | --- |
| DOCX | 段落与标题、自动编号、表格、链接、数学公式、图片、图表、SmartArt、脚注尾注、批注及修订 |
| XLSX | 工作表与区域读取、合并单元格、公式与保存结果、数字显示格式、批注、筛选与规则、图表、透视信息、搜索与查询 |
| PPTX | 幻灯片文字与表格、图片与媒体、图表、SmartArt、演讲者备注、批注及主题样式 |

旧版 XLS 另提供独立的单元格内容读取接口，支持范围见 [XLS 参考](specifications/xls/README.md)。

### 安装

需要 Python 3.10 或以上版本。克隆仓库后，在根目录安装需要的格式包：

```sh
python -m pip install ./packages/doctokens_core ./packages/doctokens_word ./packages/doctokens_excel ./packages/doctokens_powerpoint
```

只需要一种格式时，安装共享核心 `doctokens_core` 和对应的格式包即可。

### 快速使用

```python
from doctokens_word import parse_docx
from doctokens_excel import parse_xlsx
from doctokens_powerpoint import parse_pptx

document = parse_docx("report.docx", density="semantic")
workbook = parse_xlsx("sales.xlsx", sheet="Sales", range_spec="A1:C20")
presentation = parse_pptx("slides.pptx", slide=2, span=2)

print(document.text)
print(workbook.text)
print(presentation.text)
```

返回结果包含文本、解析报告和资源目录。输入可以是文件路径或完整文件的 `bytes`。

需要对同一文件重复读取或搜索时，可以使用会话：

```python
from doctokens_excel import open_xlsx

with open_xlsx("sales.xlsx") as workbook:
    print(workbook.render(sheet="Sales", range_spec="A1:C20").text)
    print(workbook.find_cells("合计", sheets=["Sales"]).text)
```

页码窗口、修订视图、资源读取和查询等用法见各格式的 [DOCX](specifications/docx/api.md)、[XLSX](specifications/xlsx/api.md)、[PPTX](specifications/pptx/api.md) API 参考。

### 选择输出密度

| 密度 | 输出 | 适合的任务 |
| --- | --- | --- |
| `plain` | DTP 纯文本 | 概括、分类、提取文字 |
| `structural` | DTX XML | 理解层级、表格、工作表结构和公式 |
| `semantic` | DTX XML | 结合强调、颜色、修订、批注状态等阅读语义进行分析 |

密度影响保留哪些信息；具体范围见[密度说明](specifications/common/density.md)。

### 智能体工具与 MCP

工具接口支持文档导航、按范围读取、文字定位、资源读取和表格查询，可供智能体按需获取内容。

安装可选的 MCP 服务端后，将它配置到支持 MCP 的客户端：

```sh
python -m pip install "./packages/doctokens_agent_tools[mcp]"
doctokens-mcp --root /absolute/path/to/documents
```

将 `--root` 替换为允许读取的文档目录。连接配置见 [MCP 接入说明](specifications/agent-tools/mcp.md)，直接集成 Python 工具接口见[工具参考](specifications/agent-tools/README.md)。

### 可选 OCR

DOCX、PPTX 可以通过 OCR 补充图片内的文字。支持本地 Tesseract、EasyOCR，以及 PaddleVL 服务适配；OCR 引擎或服务需要单独配置，默认不开启。

本地 Tesseract 适配依赖可按需安装：

```sh
python -m pip install "./packages/ocr_llm_core[tesseract]"
```

还需安装 Tesseract 程序及所需语言包。配置方式见 [OCR 参考](specifications/common/ocr.md)。

### 使用边界

- Excel 读取文件保存的公式与结果，不重新计算公式或刷新外部数据。
- DOCX 按文件保存的分页线索定位，不执行 Word 的实时排版；重新排版后的页码可能不同。

各格式的支持范围、参数和限制以[解析行为参考](specifications/README.md)为准。
