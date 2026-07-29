# Word 文档解析非功能性优化调研

日期：2026-07-28

分支：`dev/attachment-tool`

调研边界：本文最终服务的目标是一个干净的 Word 解析器，输入为原始 `.docx` 文件路径、字节流或 file-like object，输出为面向 LLM 阅读的结构化 XML。`tfile_*`、直链下载、临时文件生命周期、上层缓存、内容仓库、receipt 管理都属于 WisePenCloud-AI 工具平台能力，不应进入解析器核心。下文保留这些项目链路的调研，只用于识别哪些设计思想可以裁剪后借鉴，哪些应该明确排除。

## 1. 结论摘要

当前 WisePenCloud-AI 的 Word 文档解析主链路是：

```text
tfile_* / direct_urls
  -> DocumentParseTool
  -> DocumentParseService
  -> CommonDocumentParser
  -> DoclingParser
  -> docling.DocumentConverter
  -> docling MsWordDocumentBackend
  -> python-docx 读取 DOCX OPC/OOXML 包
  -> docling_core DoclingDocument
  -> Markdown
  -> [平台外壳] ToolOutputCache / tool_content_read
```

这个链路已经有较完整的工具平台治理骨架：工具超时、批量上限、解析并发参数、直链下载大小上限、短期文件引用 TTL、内容寻址文件存储、解析结果缓存、长文本存仓、Markdown 分块索引、按需读取窗口。但这些能力大多是附件工具平台需要的外壳，不是本次自研 Word 解析器本体要实现的功能。

本次自研 parser 的目标链路应收敛为：

```text
raw .docx path / bytes / file-like stream
  -> DocxPreflight
  -> OOXML package reader
  -> styles / numbering / relationships indexes
  -> body + supplemental extractors
  -> structured intermediate document
  -> LLM XML renderer
  -> full / outline / window XML
```

但 Word 主解析路径里也存在一个关键优化机会：`DoclingParser.parse()` 是 `async` 方法，但内部直接调用同步的 `DocumentConverter.convert()`。在 `asyncio.gather()` 的并发解析中，这段同步 CPU/I/O 工作会阻塞事件循环。也就是说，当前 `DOCUMENT_PARSE_CONCURRENCY` 能限制任务数量，却不能真正让 Word 的 Docling 转换在事件循环中并行推进。自研解析器建议明确拆成同步核心和受控执行器，把阻塞解析放到线程池或进程池中，并按文件类型设置不同 worker 策略。

如果目标是把文档解析为 LLM 可读取的结构化 XML，同时尽量省 token，又保留完成任务所需的原文信息，最值得抽取的是：

- 解析器本体的输入安全：DOCX ZIP preflight、XML part 限额、表格/图片/嵌套结构预算、路径穿越和 zip bomb 防护。
- 解析器本体的执行模型：同步核心清晰、可选 async wrapper、线程池/进程池调度、阶段级超时和资源预算。
- Docling 的结构化中间模型思想：先构建节点树，再序列化成目标格式，而不是边解析边拼字符串。
- Docling / python-docx 的 Word XML 处理细节：段落、run、hyperlink、style、numbering、table、image、textbox、OMML 公式分别处理。
- Docling 的批量转换、pipeline 缓存、输入限制、profiling 和 unload 生命周期。
- MarkItDown 原始库中值得借鉴的工程设计：converter registry、stream 位置恢复、失败诊断聚合、输出规范化、序列化降级。暂不建议把 MarkItDown 作为 DOCX 兜底链路接入解析器。

## 2. 版本与源码位置

项目代码：

- `services/wisepen-chat-service/src/chat/application/tools/document_tools/document_parse_tool.py`
- `services/wisepen-chat-service/src/chat/application/tools/document_tools/document_parse/service.py`
- `services/wisepen-chat-service/src/chat/application/tools/document_tools/document_parse/parsers/common_document/docling.py`
- `services/wisepen-chat-service/src/chat/application/utils/chunking_engine/`

以下文件属于工具平台外壳，只作为边界参考，不建议抽进干净解析器：

- `services/wisepen-chat-service/src/chat/application/tools/tool_output_cache.py`
- `services/wisepen-chat-service/src/chat/application/tools/common/tool_content_store/store.py`
- `services/wisepen-chat-service/src/chat/application/tools/common/tool_run_file_store/store.py`

本地依赖版本：

| 依赖              | 版本                       | 作用                                          |
| --------------- | ------------------------ | ------------------------------------------- |
| `docling`       | `2.107.0`                | 多格式文档转换入口                                   |
| `docling-core`  | `2.85.0`                 | `DoclingDocument` 数据模型与 Markdown serializer |
| `docling-parse` | `7.0.0`                  | PDF 相关解析后端，Word 主链路不直接依赖                    |
| `python-docx`   | `1.2.0`                  | DOCX OPC/OOXML 读取，Docling Word 后端的基础库       |
| `markitdown`    | `0.1.6`                  | CommonDocumentParser 的第二兜底链路；本文只借鉴其工程设计，不建议接入为 DOCX 兜底 |
| `mammoth`       | lock 中存在，但当前 `.venv` 未安装 | MarkItDown DOCX 转 HTML 需要它；当前 parser 规划暂不依赖 |

## 3. 当前项目 Word 解析工作流

### 3.1 工具入口

`DocumentParseTool` 暴露给模型的工具名是 `document_parse`。它支持两类输入：

- `file_refs`: 由上游工具、上传或文件中转产生的 `tfile_*`。
- `direct_urls`: 明显的 Office/PDF/表格文件直链。

这些入口能力用于 WisePenCloud-AI 的附件平台。对本次自研 parser 来说，输入边界应收窄为“已经存在且已授权读取的 `.docx` 文件路径、bytes 或 file-like stream”。因此本节只保留批量、并发、单项失败隔离这些通用思想，不把 `tfile_*`、URL 下载和工具输出持久化纳入 parser 设计。

入口代码中已经包含几个可复用的非功能性设计：

| 技术点    | 当前实现                                                | 可抽取价值          |
| ------ | --------------------------------------------------- | -------------- |
| 参数互斥   | `ToolExactlyOneOf(file_refs, direct_urls)`          | 仅作为“输入类型要明确”的参考，parser 本体不支持 URL |
| 最大输入数  | `MAX_DOCUMENT_PARSE_FILE_REFS = 64`                 | 批量 API 可参考，单文件 parser 不需要 |
| 服务批量   | `SERVICE_BATCH_SIZE = DOCUMENT_PARSE_MAX_FILE_REFS` | 把模型层批量和服务层批量解耦 |
| 并发限制   | `asyncio.Semaphore(DOCUMENT_PARSE_CONCURRENCY)`     | 防止解析器同时打开过多文件  |
| 单项失败隔离 | 每个文件返回 `success/failed` item                        | 批量任务中局部失败不拖垮整批 |
| 输出持久化  | `persist_output=True`, `cache_chunked=True`         | 属于平台能力，parser 只需产出可分块 XML 或结构化结果 |
| 建议后续动作 | `suggested_action=tool_content_read`                | 属于工具交互能力，parser 可提供 locator，读取策略由上层决定 |

### 3.2 文件引用解析是边界外能力

`ToolRunFileStore` 管理 `tfile_*` 的生命周期。它不是简单保存路径，而是做了完整的文件治理：

- 按 `user_id/session_id` 创建隔离目录。
- 发布文件时计算 SHA-256。
- 用内容寻址路径保存 object：`objects/{sha256前两位}/{sha256}{suffix}`。
- 相同内容只存一份，已存在时刷新 mtime。
- 写文件使用临时文件再 `replace()`，避免读到半写文件。
- Redis 中保存 `ref_id/user_id/session_id/sha256/size/expires_at/metadata`。
- 解析引用时校验 `ref_id` 前缀、作用域、TTL、路径边界、文件大小。
- 文件 I/O 和哈希计算通过 `asyncio.to_thread()` 下沉到线程，避免阻塞事件循环。

这部分不应进入自研 Word parser。parser 应假设调用方已经提供了一个可读、已授权、已落盘或可读取的 DOCX 输入。可裁剪借鉴的只有两个底层习惯：

- 对所有写出的结果文件使用临时文件 + 原子替换，避免半写文件。
- 对读取的 ZIP entry 做路径穿越和大小校验，防止恶意 DOCX 包。

内容寻址、TTL、作用域、临时文件清理、URL 下载、ref_id 校验都属于上层平台，不属于干净解析器。

### 3.3 格式路由

`DocumentParseService.parse()` 先用 `Magika` 检测文件类型，失败时用扩展名和 `mimetypes.guess_type()` 兜底。

路由策略：

- PDF 走专用 `PdfParseStrategy`。
- Excel XML / CSV / TSV 走 `PandasSpreadsheetParser`。
- 其他普通文档，包括 DOCX，走 `CommonDocumentParser`。

`CommonDocumentParser` 的顺序是：

1. `DoclingParser`
2. `MarkItDownParser`

因此当前项目的 Word 主链路是 Docling，MarkItDown 是项目里的兜底。对本次自研 parser，暂不考虑接入 MarkItDown 作为 DOCX 兜底；后文只抽取 MarkItDown 原始库中有价值的工程模式。

### 3.4 DoclingParser 的当前实现

`DoclingParser` 使用 `@lru_cache(maxsize=1)` 复用一个 `DocumentConverter` 实例，然后调用：

```python
result = _get_converter().convert(str(request.file_path))
markdown = result.document.export_to_markdown(
    image_mode=ImageRefMode.EMBEDDED,
    traverse_pictures=True,
)
```

可复用的设计：

- Converter 单例缓存：降低构造、pipeline 初始化和模型加载成本。
- 输出参数固定：不给模型暴露 image mode 开关，减少输出不稳定性。
- 当前项目在 Docling 失败后交给 MarkItDown 兜底；自研 parser 暂不沿用这条兜底，只保留“失败诊断要可聚合、可解释”的思想。

需要注意的风险：

- `DocumentConverter.convert()` 是同步阻塞调用，目前没有放到 executor。
- `DocumentConverter` 内部有 pipeline 缓存和可变状态。如果将来放入多线程并发，建议验证线程安全，或采用“每个 worker 一个 converter”的模型。
- 项目没有给 Docling 传 `max_file_size`，依赖上游文件入口限制兜底。自研 parser 应在自身 preflight 中完成 DOCX 文件大小、解压体积、XML part 和媒体体积限制，不能依赖附件平台。

## 4. 当前项目可抽取的非功能性技术代码

### 4.1 配置集中化

`ToolSettings` 将高频运维参数集中在一个 Pydantic 模型中，并 `extra="forbid"`，避免环境变量或配置拼错后静默生效失败。

关键参数：

| 参数                                    | 默认值          | 意义             |
| ------------------------------------- | ------------ | -------------- |
| `DOCUMENT_PARSE_TOOL_TIMEOUT_SECONDS` | `300s`       | 单次文档解析工具总超时    |
| `DOCUMENT_PARSE_CONCURRENCY`          | `16`         | 解析并发上限         |
| `DOCUMENT_PARSE_MAX_FILE_REFS`        | `16`         | 服务内部批量大小       |
| `TOOL_CONTENT_MAX_CHARS`              | `20,000,000` | 平台长文本最大字符数，可转化为 parser 输出上限参考 |
| `TOOL_RUN_FILE_MAX_BYTES`             | `50 MiB`     | 平台单文件最大资产大小，可转化为 parser 输入上限参考 |
| `TOOL_CONTENT_READ_MAX_WINDOW_CHARS`  | `100,000`    | 平台读取窗口硬上限，可转化为 XML view/window 上限参考 |

建议抽取为自研解析器的 `ParserSettings`：

```python
class ParserSettings(BaseModel):
    parse_timeout_seconds: float
    max_input_bytes: int
    max_uncompressed_zip_bytes: int
    max_xml_part_bytes: int
    max_media_bytes: int
    max_body_blocks: int
    max_table_cells: int
    max_nesting_depth: int
    max_output_chars: int
    xml_view_budget_chars: int
    debug: bool
```

如果 parser 暴露批量 API，可以另设 `BatchParseSettings(parse_concurrency, parse_batch_size, worker_kind)`；不要把下载、TTL、内容缓存等平台参数混进单文件解析配置。

### 4.2 批量和并发控制

项目中 `DocumentParseTool` 使用两层控制：

- `batched(inputs, batch_size)`
- `asyncio.Semaphore(DOCUMENT_PARSE_CONCURRENCY)`

这个结构适合保留，但 Word 解析需要修正阻塞问题。推荐模式：

```python
parse_executor = ThreadPoolExecutor(max_workers=settings.docx_workers)

async def parse_docx_async(path):
    async with docx_semaphore:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(parse_executor, parse_docx_sync, path)
```

线程池适合 I/O 密集、Zip 解压和 C 扩展释放 GIL 的场景。`python-docx` 有大量 Python 对象构造和 lxml 包装，若 CPU 占比高，进程池通常更稳定。Docling 自己的 settings 中也提醒：普通 CPython 下文档级线程并发不一定有收益。

建议分层并发：

| 层级    | 建议                               |
| ----- | -------------------------------- |
| API 层 | 限制一次请求文件数                        |
| 调度层   | `Semaphore` 限制同时解析文件数            |
| 格式层   | DOCX/PDF/OCR/LibreOffice 分别设置并发池 |
| 进程层   | CPU-heavy XML/表格/图片处理可走进程池       |
| 全局层   | 设置队列长度，超限快速失败或排队                 |

### 4.3 超时治理

当前工具执行器用 `asyncio.wait_for()` 包裹工具调用，实现工具级超时。底层 URL fetch、OCR polling、PDF sanitize 也有独立超时。

自研解析器建议至少有三种超时：

- 总超时：单个文档整体解析上限。
- 阶段超时：解压、XML 解析、图片解码、外部命令、输出序列化。
- 外部进程超时：LibreOffice、OCR、PDF renderer 等必须可杀。

注意：`asyncio.wait_for()` 只能取消协程，不会强制停止已经在线程池里运行的同步函数。若使用线程池，超时后只能放弃结果，线程仍可能跑完。若需要强杀，使用进程池或外部 worker 进程。

### 4.4 版本化和可复现性，不是 parser 内缓存

当前项目有两层缓存：

1. URL 内容缓存：Redis entry + Mongo value。
2. 解析结果缓存：`DocumentParseCache` 通过 `parser_version="document_parse:v1"` 读取/回写 Markdown。

这些缓存属于服务平台，不建议放入干净 Word parser。parser 本体不应关心 Redis、Mongo、URL cache、TTL 或跨请求复用。但是缓存设计里有两个信息对 parser 仍然重要：

- 输出必须带 `parser_version` 和 `schema_version`，否则上层无法判断旧 XML 是否还能被新提示词或新 reader 正确理解。
- 解析选项必须可序列化、可 hash，方便上层需要时自行做缓存，而不是由 parser 隐式缓存。

自研 XML 输出建议在 metadata 中稳定写入：

```text
parser_name = "wisepen_docx_xml"
parser_version = "docx_xml:v3"
structure_schema_version = "llm_document_xml:v2"
token_budget_profile = "compact-lossless:v1"
options_hash = sha256(canonical_json(parse_options))
```

这样当抽取算法、XML schema、压缩策略任一变化时，上层如果要做缓存，可以精准失效；parser 本体仍然保持无状态、可测试、可嵌入。

### 4.5 XML 输出预算，而不是内容仓库管理

当前项目的工具平台不是把解析结果无条件塞给模型，而是把“首屏摘要”和“完整内容”分开。这个思想值得保留，但实现形式要从平台能力裁剪成 parser 能力。

对干净 parser 来说，不应实现 `ToolContentStore`、`content_id`、receipt、TTL 或按需读取服务；parser 应输出足够稳定的 locator、分块边界和多种 XML view，让上层如果需要，可以很容易构建自己的存储或读取能力。

建议 parser 本体提供这些输出形态：

| 输出形态 | 内容 | 用途 |
| --- | --- | --- |
| `full` | 原文信息尽量完整的 XML | 离线保存、测试、上层自建索引 |
| `outline` | 标题树、表格/图片/批注/脚注清单、locator | 低 token 让模型规划读取路径 |
| `window` | 给定 locator 范围的 XML 片段 | 上层按需精读 |
| `stats` | 字符数、节点数、表格数、图片数、warnings | 调度、预算和质量评估 |

不要把“省 token”理解为删除原文。更稳的设计是 parser 能同时生成完整 XML 和紧凑 XML；是否存仓、是否给 LLM 首屏、是否按 locator 回读，由调用方决定。

### 4.6 Markdown 分块索引

当前 `chunking_engine` 的 Markdown pipeline：

1. `MarkdownSectionPathInjector` 给正文块注入 `Section: A > B`。
2. `MarkdownBlockSplitter` 拆成 `HEADING/PARAGRAPH/TABLE/CODE/FORMULA/IMAGE/LIST/QUOTE/PAGE_MARKER/UNKNOWN`。
3. `SizeBoundedUnitPacker` 按约 4000 字符合并相邻 unit。
4. `PAGE_MARKER` 是硬边界，避免跨页窗口。
5. `MarkdownLocatorIndexBuilder` 建 section/page/anchor 索引。

对 XML 输出的启发：

- XML 节点也应先变成逻辑 unit，而不是直接按字符切。
- chunk 不应跨越强语义边界，如页、章节、表格、批注块、脚注块。
- 每个 chunk 记录 `start_offset/end_offset`，保证可回到原文。
- selector 不只按 chunk id，还应支持 `section/page/table/figure/comment/footnote/bookmark/style`。

## 5. Docling 中可抽取的非功能性技术点

### 5.1 DocumentConverter 的 pipeline 缓存

`DocumentConverter` 持有：

```text
initialized_pipelines: dict[(pipeline_class, options_hash), BasePipeline]
```

`options_hash` 来自 `pipeline_options.model_dump()` 的 MD5。初始化 pipeline 时使用模块级锁 `_PIPELINE_CACHE_LOCK`。

可抽取价值：

- 大模型、OCR、表格识别、图片描述等重型组件不应每个文件重复初始化。
- pipeline 缓存 key 应包含配置 hash，而不是只按格式缓存。
- 初始化应加锁，避免并发下重复加载大模型。

建议自研解析器：

```text
ParserPipelineCache key =
  format
  + parser_version
  + output_schema_version
  + feature_flags
  + model_config_hash
```

### 5.2 输入限制

Docling 的 `DocumentLimits` 支持：

- `max_num_pages`
- `max_file_size`
- `page_range`

`InputDocument` 会在打开 backend 前检查文件大小，paginated backend 还会检查页数和 page range。

对 DOCX 的补充建议：

Docling 的 `max_file_size` 是压缩包文件大小，不等于解压后的 XML 和媒体总大小。自研 DOCX 解析器应增加：

- ZIP entry 数量上限。
- 单 entry 解压后大小上限。
- 全部 entry 解压后大小上限。
- 压缩比上限，防 zip bomb。
- `word/media/*` 总大小上限。
- XML 节点数量上限。
- 最大段落数、最大表格数、最大单表格单元格数。
- 最大嵌套深度，如表格套表格、文本框套图形。

### 5.3 批量转换和线程池

Docling 的 `convert_all()` 会按 `settings.perf.doc_batch_size` 把输入分批。若 `doc_batch_concurrency > 1` 且 batch size > 1，则使用 `ThreadPoolExecutor(max_workers=doc_batch_concurrency)`。

默认设置：

- `doc_batch_size = 1`
- `doc_batch_concurrency = 1`
- 注释说明普通 CPython 下没有 free-threaded Python 时未必有收益。

可抽取价值：

- 文档级并发是配置项，不硬编码。
- 同步解析器可以用 executor 包装成批处理接口。
- 默认保守，避免用户机器上内存被大批文档打爆。

建议：

- 默认 DOCX worker 数小于 Web fetch worker 数。
- 以文件大小、表格数量、图片数量估算任务权重，不只按文件数并发。
- 对 LibreOffice 渲染类兜底路径单独限流到 1-2。

### 5.4 Pipeline 生命周期和 profiling

`BasePipeline.execute()` 用 `TimeRecorder` 记录：

- `pipeline_total`
- `doc_build`
- `doc_enrich`

异常时根据 `raises_on_error` 决定抛错或记录 `ErrorItem`。`finally` 中调用 `_unload(conv_res)`。

可抽取价值：

- 每个解析阶段都应有 duration。
- 失败时保留组件名、错误类型、错误阶段。
- 生命周期末尾提供 unload hook，用于释放页面图、图片、临时 backend。

建议指标：

```text
parse_total_ms
zip_open_ms
xml_parse_ms
paragraph_extract_ms
table_extract_ms
image_extract_ms
formula_extract_ms
xml_serialize_ms
output_chars
inline_chars
stored_chars
chunk_count
cache_hit
fallback_used
worker_queue_ms
peak_rss_mb
```

## 6. python-docx 中可抽取的非功能性技术点

### 6.1 OPC 包读取模型

`python-docx` 的 `Document(path_or_stream)` 会：

1. `Package.open(docx)`
2. `PackageReader.from_file(pkg_file)`
3. `PhysPkgReader` 判断路径是目录还是 zip。
4. `_ZipPkgReader` 用 `ZipFile(pkg_file, "r")`。
5. 通过关系图遍历可达 part。
6. `blob_for()` 对每个 part 调用 `ZipFile.read()`，把 part 完整读入内存。
7. 关闭 zip。
8. 通过 Unmarshaller 组装 package/part/relationship 对象。

这说明 `python-docx` 不是流式解析器。它会把关系图可达的 XML、图片等 part 读成 blob。对大 DOCX 或媒体很多的 DOCX，要依赖你自己的前置大小和解压限制。

可抽取价值：

- 使用 OPC relationship graph，只遍历从 package root 可达的 part。
- 外链 relationship 跳过，不下载外部资源。
- 包读取后立即关闭 zip，后续操作在内存对象上完成。
- 支持 file-like object，便于内存预处理或沙箱下载文件。

### 6.2 lazyproperty 与对象包装

`python-docx` 使用 `lazyproperty` 延迟构建部分集合，例如 package relationships、image parts、body、styles 等。

可抽取价值：

- 自研解析器的样式表、编号表、关系表可懒加载。
- 段落只在需要时包装成对象，避免一开始构建全量高层对象。

但需要注意：

- 当前 Docling Word 后端在 `_walk_linear()` 中对每个 `<w:p>` 构造 `Paragraph(element, docx_obj)`，对每个 run/hyperlink 构造代理对象。
- 这会产生大量 Python 对象，对 CPU 和 GC 压力明显。

自研优化方向：

- 对热路径直接使用 lxml/ElementTree XPath 和轻量 dataclass，而不是为每个 run 创建完整代理对象。
- 样式、编号、relationship 建索引 dict，段落处理只做 O(1) 查询。
- 对 `w:t` 文本、hyperlink、formatting 分离为一次 XML scan，减少重复 XPath。

### 6.3 表格文本读取

`python-docx` 的 `_Cell.text` 是把 cell 内所有 paragraph 的 `text` 用换行拼接。Docling 对简单 cell 使用它，对 rich cell 再递归 `_walk_linear()`。

自研优化方向：

- 表格先判断是否 rich cell。简单 cell 走快速文本路径。
- rich cell 只在存在多段落、嵌套表、图片、列表、公式、文本框时进入递归。
- 大表格输出时提供多种模式：
  - `compact`: XML 属性 + 行列文本，省 token。
  - `faithful`: 保留合并单元格、标题、嵌套块。
  - `indexed`: 只给表格摘要和 `table_id`，按需读取整表。

### 6.4 图片处理

`python-docx` 能通过 relationship 找到 image part blob。Docling 再用 Pillow 打开、过滤 spacer，并把图片转成 `ImageRef`。

自研优化方向：

- 默认不要把图片 base64 内联给 LLM，除非用户任务需要视觉细节。
- 图片先输出轻量占位：

```xml
<image id="img_12" alt="" rel="rId9" bytes="134220" media_type="image/png"/>
```

- 图片二进制进资产仓库，LLM 需要时再 OCR 或视觉模型读取。
- 对 spacer、纯白、透明、极小图片做过滤，减少无意义 token。
- 对 EMF/WMF/DrawingML/SmartArt 渲染兜底单独限流，因为可能调用 LibreOffice。

## 7. Docling Word 后端中可抽取的功能边界和性能启发

虽然本文重点是非功能性，但 Word 的结构处理决定性能边界，需要拆清楚。

### 7.1 线性遍历

`MsWordDocumentBackend._walk_linear()` 按 body 子元素顺序处理：

- `tbl`: 表格。
- 带 drawing blip 的段落：图片，然后可继续处理段落文本。
- VML image：旧格式图片。
- DrawingML：可尝试 LibreOffice 渲染。
- `sdt`: 内容控件，递归处理 `sdtContent`。
- `p`: 普通段落。
- textbox 和 shape text 使用 XPath 额外检测。

可抽取价值：

- 以 Word XML 顺序为主线，保证文本流顺序稳定。
- 浮动文本框、shape text 单独收集，否则原文信息会丢。
- 图片和段落文字可共存于同一 paragraph，不能二选一。
- 内容控件递归进入，而不是忽略。

### 7.2 段落元素分组

Docling 会把段落内 run 按 formatting/hyperlink 分组，避免每个 run 都输出一个节点，同时保留格式变化。

自研 XML 输出建议：

```xml
<p id="p_23" style="Normal">
  <t>普通文本</t>
  <t fmt="b">加粗</t>
  <a href="https://...">链接文本</a>
</p>
```

省 token 版本可以把常见标签缩短：

```xml
<p s="Normal"><t>普通文本</t><t f="b">加粗</t><a h="https://...">链接文本</a></p>
```

保留完整原文的关键不是标签长短，而是每个节点的 locator：

```xml
<p id="p_23" off="1204:1368" s="Normal">...</p>
```

### 7.3 标题和列表

Docling 标题识别使用：

- style id
- style name
- base_style
- OOXML `outlineLvl`

列表识别使用：

- 段落或样式中的 `numPr/numId/ilvl`
- numbering XML 的 `abstractNum/lvl/numFmt/lvlText`
- 计数器维护多级编号

自研优化：

- 启动时预解析 styles 和 numbering，建立 cache：

```text
style_id -> heading_level / num_id / default_format
num_id + ilvl -> num_format / lvl_text / start
```

- 段落热路径只做 dict 查询。
- 多级编号 marker 生成应可关闭。若只为 LLM 结构理解，可保留 `numId/ilvl` 和实际文本中已有编号，避免重复 token。

### 7.4 公式处理

Docling 和 MarkItDown 都把 OMML 公式转换为 LaTeX。公式转换属于 CPU 细粒度热路径，建议：

- 对 OMML XML string 做 hash cache。
- 公式节点数量设上限。
- 转换失败时保留原始 OMML locator 和占位，避免整段失败。

输出建议：

```xml
<eq id="eq_7" tex="E=mc^2"/>
```

长公式可改为内容仓库引用。

## 8. MarkItDown 原始库中可抽取的工程设计

本次 parser 暂不考虑接入 MarkItDown 作为 DOCX 兜底链路，也不依赖 Mammoth。这里保留 MarkItDown 调研，是为了抽取它在“多转换器框架、输入流处理、失败诊断和序列化降级”上的优秀工程设计。

MarkItDown 的 DOCX 转换路径是：

```text
DOCX stream
  -> pre_process_docx
  -> mammoth.convert_to_html
  -> HtmlConverter
  -> BeautifulSoup
  -> markdownify
  -> Markdown
```

这条路径不建议作为当前自研 Word parser 的运行时兜底。原因是：它先把 DOCX 转 HTML/Markdown，结构信息会被压扁；并且当前本地 `.venv` 缺 `mammoth`，实际不可作为稳定保障。

### 8.1 Converter registry

MarkItDown 注册多个 converter，并按 priority 排序尝试。具体转换时：

- 先生成多个 `StreamInfo` guess。
- 每个 converter 先 `accepts()`。
- 若接受，则调用 `convert()`。
- 不管成功失败，最后都 `file_stream.seek(cur_pos)`。
- 成功后统一规范化换行，压缩 3 个以上连续换行为 2 个。
- 所有失败会汇总成 `FileConversionException(attempts=...)`。

可抽取价值：

- 即使当前 parser 只支持 DOCX，也可以把读取器、预处理器、渲染器做成 registry，避免主流程被大量 if/else 塞满。
- 每个 converter 尝试后必须恢复 stream 位置。
- 输出后做统一 newline normalization。
- 选择逻辑和具体解析逻辑分离。
- 失败诊断要聚合成结构化 attempts，而不是只暴露最后一个异常。

### 8.2 DOCX 预处理

`pre_process_docx()` 会：

- 在内存中用 `zipfile.ZipFile` 解压整个 DOCX。
- 对 `word/document.xml`、`word/footnotes.xml`、`word/endnotes.xml` 做 OMML -> LaTeX。
- 再重新写成一个 BytesIO DOCX。

可抽取价值：

- 对局部 XML part 做预处理比在高层模型里补救更简单。
- footnotes/endnotes 需要纳入公式处理。

风险：

- 当前实现把 zip 所有 entry 读入 dict，内存压力大。
- 没有 zip bomb 防护。
- 依赖 Mammoth 把 DOCX 转 HTML，容易丢失部分 Word 原始结构。

自研建议：

- 预处理阶段不要一次性把所有 entry 放入内存。
- 对每个 entry 边读边写，只有目标 XML part 进入转换。
- 增加 entry size、entry count、compression ratio 限制。

### 8.3 HTML 转 Markdown 降级

MarkItDown 的 `HtmlConverter` 用 BeautifulSoup 解析 HTML，移除 `script/style`，优先转换 `<body>`。如果 markdownify 遇到 `RecursionError`，降级为 BeautifulSoup 的 `get_text("\n", strip=True)`。

可抽取价值：

- 序列化阶段也需要降级策略。
- 对异常深层结构，宁可返回带 warning 的可用简化 XML 或纯文本片段，也不要整体失败。
- 降级应该发生在 parser 自己的 XML renderer 内，而不是把 DOCX 交给 MarkItDown 重跑一遍。

## 9. 面向 XML 文本流的设计建议

### 9.1 结构化输出不要只靠 Markdown

Markdown 对 LLM 友好，但对 Word 原始结构有损：

- 样式层级、编号定义、run formatting 的边界会压扁。
- 表格合并、rich cell、嵌套表难以无损表达。
- 批注、脚注、页眉页脚、书签、交叉引用等容易丢失。
- 图片、shape、textbox 的阅读顺序不够显式。

建议内部中间模型使用节点树，外部给 LLM 的格式用 XML。示例：

```xml
<doc id="d1" fmt="docx" schema="llm_doc_xml:v2">
  <meta name="example.docx" bytes="123456"/>
  <body>
    <h id="h1" lvl="1" off="0:12">标题</h>
    <p id="p1" off="13:80">正文<t f="b">加粗片段</t></p>
    <tbl id="tbl1" rows="8" cols="4" off="81:520" mode="indexed"/>
  </body>
</doc>
```

### 9.2 省 token 的 XML 原则

建议使用“稳定短标签 + schema 文档解释”的方式，而不是在每个节点写长字段名。

| 语义         | 详细标签                      | 紧凑标签          |
| ---------- | ------------------------- | ------------- |
| paragraph  | `<paragraph>`             | `<p>`         |
| heading    | `<heading level="1">`     | `<h l="1">`   |
| table      | `<table>`                 | `<tbl>`       |
| row        | `<row>`                   | `<r>`         |
| cell       | `<cell row_span="2">`     | `<c rs="2">`  |
| formatting | `<text bold="true">`      | `<t f="b">`   |
| hyperlink  | `<link href="...">`       | `<a h="...">` |
| offset     | `start_offset/end_offset` | `off="12:34"` |

但不要为了省 token 牺牲可回读性。每个可检索单元至少保留：

- `id`
- `off` 或 XML part locator
- section path
- page/anchor/table locator，如果可得
- 稳定 node path；可选输出 node hash，便于上层自行索引

### 9.3 输出分层

推荐三层输出：

1. `manifest`: 文档级元数据、解析器版本、schema 版本、warnings、统计信息。
2. `outline`: 章节树、表格/图片/脚注/批注索引、重要 locator。
3. `content`: 完整 XML 或按 locator 生成的局部 XML window。

首屏给 LLM：

```xml
<doc_manifest doc="example.docx" schema="llm_doc_xml:v2" nodes="1840">
  <outline>...</outline>
  <views available="outline,window,full"/>
</doc_manifest>
```

精读时再返回：

```xml
<content_window section="A > B" loc="body.12:body.18" off="12000:14500">
  ...
</content_window>
```

### 9.4 原文完整性策略

如果目标是“尽可能省 token，同时保留 LLM 完成任务所需的原文所有信息”，建议定义两种完整性：

| 类型    | 含义                | 实现                                                 |
| ----- | ----------------- | -------------------------------------------------- |
| 解析完整  | parser 输出可恢复原文文本和结构 | full XML / offsets / raw part refs / warnings      |
| 上下文充分 | 当前对话轮只给模型完成任务所需窗口 | outline + locator-based window                     |

不要承诺每次调用都把所有信息放进一个 XML 片段。应承诺 parser 能给出完整 XML，同时能按 locator 生成更小的 XML view；是否持久化和如何回读由上层决定。

## 10. 当前实现中的可优化点

### 10.1 Word 解析阻塞事件循环

现状：

- `DocumentParseTool` 使用 `asyncio.gather()` 和 semaphore。
- `DoclingParser.parse()` 内部直接同步调用 Docling。

影响：

- 多个 Word 文件解析时，事件循环可能被单个 Docling 转换长时间占用。
- 并发参数对真正的 Word 转换吞吐帮助有限。

建议：

- 将 `DoclingParser` 改为同步核心 + async executor wrapper。
- 对 DOCX 使用独立 executor。
- 如果多文档吞吐目标很高，优先评估 `ProcessPoolExecutor`。

### 10.2 Converter 单例与线程安全

现状：

- `_get_converter()` 使用 `lru_cache(maxsize=1)` 全局复用 `DocumentConverter`。
- Docling 内部 pipeline 初始化有锁。

风险：

- 如果未来把 parse 放到线程池，同一个 converter 会被多线程调用。
- SimplePipeline 和 MsWordDocumentBackend大体是每输入新建 backend，但 converter 自身有可变 pipeline cache。

建议：

- 保守方案：每个 worker thread/process 持有自己的 converter。
- 或给 converter 调用加 per-format lock，牺牲并发换稳定。
- 对 PDF/图片等模型管线可用进程级 warm worker，避免线程共享复杂模型状态。

### 10.3 DOCX zip bomb 防护不足

现状：

- 项目限制上传/下载文件大小 50 MiB。
- `python-docx` 打开后会读取 zip part blob。

缺口：

- 压缩包 50 MiB 可能解压成数百 MB 甚至 GB。
- Word 媒体文件、嵌套 XML、恶意压缩比可能导致内存峰值过高。

建议增加 DOCX 预检：

```text
zip_entries <= N
sum(file_size) <= max_uncompressed_bytes
max(entry.file_size) <= max_entry_bytes
max(file_size / compress_size) <= max_ratio
allowed prefixes: word/, docProps/, _rels/, [Content_Types].xml
media_total_bytes <= max_media_bytes
xml_total_bytes <= max_xml_bytes
```

### 10.4 MarkItDown 不作为当前 DOCX 兜底

当前 `.venv` 没有 `mammoth`，而 MarkItDown 的 `DocxConverter` import mammoth 失败后会在转换时抛缺依赖异常。

建议：

- 当前自研 parser 不接入 MarkItDown/Mammoth 作为运行时兜底。
- 继续保留 MarkItDown 的 registry、stream reset、attempts 聚合、newline normalization、序列化降级这些工程设计。
- 如果未来扩展到非 DOCX 普通文档，再独立评估 MarkItDown，而不是把它混进 Word 解析核心。

### 10.5 Header/Footer/Comments 的导出层

Docling Word 后端会把 header/footer 放到 `ContentLayer.FURNITURE`，comments 放到 `ContentLayer.NOTES`。`export_to_markdown()` 默认只导出 `BODY`。

这不是性能问题，但会影响“保留原文所有信息”的目标。

建议 XML schema 显式分层：

```xml
<body>...</body>
<furniture>
  <header>...</header>
  <footer>...</footer>
</furniture>
<notes>
  <comment target="p_12">...</comment>
  <footnote id="fn1">...</footnote>
</notes>
```

模型首屏可只显示 `body` 和 notes 索引，但完整内容必须可读取。

## 11. 建议的自研解析器非功能性蓝图

### 11.1 模块拆分

```text
DocxPreflight
  - zip safety check
  - content type check
  - relationship graph scan
  - file-like/path input normalize

DocxParserCore
  - styles/numbering/rels indexes
  - body linear walker
  - table/textbox/image/formula/comment handlers

StructuredDocument
  - neutral node tree
  - offsets and locators

LLMXmlSerializer
  - compact XML
  - full XML
  - manifest/outline/window modes

ParserExecutor
  - bounded thread/process workers
  - timeout/cancel/fallback
  - metrics
```

### 11.2 执行模型

推荐：

```text
caller
  -> optional queue parse job
  -> optional semaphore by format
  -> executor worker
  -> sync parser core
  -> structured document
  -> XML serializer
```

不要让 XML 解压、lxml 遍历、图片解码、LibreOffice 调用直接跑在事件循环线程。

### 11.3 版本化和上层缓存友好

parser 本体建议保持无状态，不内置跨请求缓存。为了让上层需要时能安全缓存，parser 应输出或暴露：

| 字段 | 用途 |
| --- | --- |
| `parser_name` / `parser_version` | 解析算法版本 |
| `schema_version` | XML 契约版本 |
| `options_hash` | 调用选项稳定 hash |
| `input_fingerprint` | 可选，由调用方传入或 parser 计算文件 sha256 |
| `feature_flags` | revision、runs、raw hints、assets、supplemental 等开关 |

如果上层要做缓存，推荐 key 是：

```text
input_fingerprint + parser_version + schema_version + options_hash
```

但这不是 parser 必须管理的功能。parser 的职责是让结果可复现、可比较、可安全缓存。

### 11.4 降级策略

建议降级等级：

1. 完整结构化解析。
2. 跳过图片二进制，仅保留 image locator。
3. 跳过复杂 DrawingML 渲染，仅保留 shape/text fallback。
4. 表格 rich cell 降级为 plain cell text。
5. 公式转换失败时保留原始 OMML 占位和 locator。
6. 全结构失败时，用 `python-docx` 快速文本路径抽取段落和表格纯文本。
7. 最后再使用 parser 内部的纯 XML `w:t` 拼接兜底，并显式标记结构已降级。

每次降级都应记录 warning：

```xml
<warn code="formula_decode_failed" target="eq_12"/>
```

### 11.5 测试和压测建议

功能测试之外，应加入非功能性样本：

- 1000 页等价大文档，实际 DOCX 可用大量段落模拟。
- 10,000 行大表格。
- 多级列表 9 层。
- 大量图片和极小 spacer 图片混合。
- 文本框、shape text、SmartArt、VML。
- 大量公式。
- footnotes/endnotes/comments/header/footer。
- zip bomb 模拟包。
- 并发 1/4/8/16 文件解析。
- 同文件重复解析的可复现性：输出 XML、warnings、metrics 应稳定。

压测指标：

```text
p50/p95/p99 parse duration
peak RSS
event loop lag
executor queue wait
fallback rate
bytes read/uncompressed
output chars/token estimate
chunk count
window generation latency
```

## 12. 可直接提取的代码模式清单

| 来源                          | 技术模式                                 | 建议动作                              |
| --------------------------- | ------------------------------------ | --------------------------------- |
| `DocumentParseTool`         | batch + semaphore + per-item failure | 只用于可选批量 wrapper，单文件 parser 保持干净 |
| `ToolExecutor`              | `asyncio.wait_for` 工具级超时             | 用于 async wrapper；硬超时需进程/worker 支持 |
| `ToolSettings`              | 运维参数集中化                              | 抽成 parser-only `ParseLimits/RenderOptions/ExecutionOptions` |
| `ToolRunFileStore`          | 原子写入、路径边界意识                          | 只借鉴原子写和路径校验；内容寻址/TTL/作用域不进 parser |
| `DocumentParseCache`        | parser version 思想                    | 只借鉴版本字段和 `options_hash`；parser 不管理缓存 |
| `ToolOutputCache`           | 短输出和长输出分层                            | 只借鉴多视图输出思想；不实现 receipt |
| `ToolContentStore`          | chunk/index/selector 思想              | parser 生成 locator/window；不实现内容仓库 |
| `chunking_engine`           | unit/chunk/index 分层                  | 复用思想，替换为 XML-aware locator/window |
| Docling `DocumentConverter` | pipeline cache by options hash       | 用于重型解析 pipeline                   |
| Docling `DocumentLimits`    | 文件/页范围限制                             | 扩展为 DOCX zip 安全限制                 |
| Docling `convert_all`       | batch + optional ThreadPoolExecutor  | 作为批处理参考，但默认保守                     |
| Docling `BasePipeline`      | profiling + unload                   | 抽取阶段指标和资源释放 hook                  |
| python-docx OPC reader      | relationship graph 遍历                | 用于只处理可达 part                      |
| python-docx `lazyproperty`  | 懒加载集合                                | 用于 styles/numbering/media indexes |
| MarkItDown registry         | converter registry + stream reset    | 用于插件化预处理/渲染阶段；不作为 DOCX 兜底 |
| MarkItDown HTML fallback    | RecursionError 降级纯文本                 | 用于 XML 序列化异常降级                    |

## 13. 最小落地优先级

建议按这个顺序做：

1. 给现有同步 DOCX 解析核心套受控 executor，避免阻塞事件循环。
2. 加 DOCX zip 预检，防解压炸弹和媒体内存峰值。
3. 在输出 metadata 中暴露 `parser_version + schema_version + options_hash`，让上层可自行缓存。
4. 把 XML 输出分成 `manifest/outline/window/full` 四种视图。
5. 建 XML-aware locator/window generator，而不是复用 Markdown block splitter。
6. 加阶段级 metrics 和 event loop lag 监控。
7. 对图片、DrawingML、公式、rich table 设独立降级和并发限流。
8. 明确 BODY/FURNITURE/NOTES 分层，避免“保留所有信息”目标被默认导出层破坏。

## 14. 关键判断

当前项目最有价值的不是 Docling 某个单独函数，而是可以裁剪成 parser-core 的组合架构：

```text
DOCX 输入安全预检
  + 可复现版本 metadata
  + 受控并发和超时
  + 结构化中间模型
  + token-aware XML 视图
  + locator/window 读取接口
```

如果你的目标是自研“原始 Word 文件 -> LLM 可读取 XML 文本流”，建议不要只抽 python-docx 的文本读取能力，也不要把附件平台的 `tfile_*`、下载、缓存、内容仓库搬进 parser。更合适的边界是：parser 负责安全读取 DOCX、构建结构化中间模型、输出完整或紧凑 XML，并提供稳定 locator；上层服务如果需要缓存、文件生命周期和对话式按需读取，再围绕这个干净 parser 组合。

## 15. `reference-code/docx_llm_parser` demo 对照评估

本节对照前文调研结论，评估 `D:\Wisepen\reference-code\docx_llm_parser` 当前 demo 的非功能性成熟度，以及下一步最值得优化的地方。

### 15.1 demo 当前架构摘要

demo 的主链路是：

```text
DocxParser.parse(docx_path, options)
  -> PackageReader 打开和校验 DOCX ZIP 包
  -> read_entry_index / content types / relationships
  -> StylesParser
  -> NumberingParser
  -> AssetExtractor
  -> DocumentBodyParser
  -> AncillaryParser
  -> ParsedDocument
  -> renderers.xml.to_llm_xml
  -> parsed.xml
```

批量链路是：

```text
parse_many(docx_paths, output_base)
  -> ThreadPoolExecutor
  -> 每个 worker 调 _parse_one
  -> DocxParser().parse
  -> write_outputs
  -> BatchParseResult
```

源码关键位置：

| 模块                        | 当前职责                  | 观察                                                |
| ------------------------- | --------------------- | ------------------------------------------------- |
| `parser.py`               | 单文档解析编排               | 上下文独立，适合并发；但缺少阶段计时、超时、版本化 metadata 和资源预算            |
| `concurrency.py`          | 多文档线程池解析              | 已保持返回顺序和单文件失败隔离；但 worker 数只按 CPU/文件数，不按内存和输入大小    |
| `core/package.py`         | DOCX ZIP / OPC 读取     | 已有 entry 数量、单 entry 大小、总解压大小、路径穿越校验               |
| `core/relationships.py`   | relationship 多路索引     | 一次构建只读索引，查询效率好                                    |
| `ooxml/styles.py`         | 样式索引和标题识别             | 有继承链和循环 warning；但解析结果未 memoize                    |
| `ooxml/numbering.py`      | 自动编号定义和运行时计数          | 编号状态与文档隔离，方向正确                                    |
| `extractors/body.py`      | body 段落、表格、run、图片引用解析 | `word/document.xml` 顶层使用 `iterparse`，内存策略优于直接 DOM |
| `extractors/assets.py`    | 图片导出和资源索引             | 使用 1 MiB chunk 流式复制，避免把二进制写入 XML                  |
| `extractors/ancillary.py` | 页眉页脚、脚注尾注、批注          | 结构较轻，但多处使用 `ET.parse` 全量 DOM                      |
| `renderers/xml.py`        | LLM XML 输出            | 已做 run 合并、格式降噪、属性转义；但输出是全量字符串，不支持 token 预算和分块     |

整体判断：demo 已经比直接使用 `python-docx.Document(...).paragraphs` 更接近“可生产化解析器”的方向。它已经具备自研解析器最关键的几个底座：ZIP 安全预检、按需读取 entry、关系索引、结构化中间模型、XML 转义、图片不内嵌、并发上下文隔离、批量单文件失败不拖垮全局。

但如果目标是一个干净的“原始 DOCX -> XML”解析器，demo 仍需要补几类 parser-core 能力：更完整的 DOCX preflight、阶段级超时和 metrics、版本化 metadata、资源预算、异步 wrapper、XML 输出预算、稳定 locator、window 生成接口和序列化降级。内容寻址、TTL、跨请求缓存、receipt、对话式读取工具都不属于 parser 本体。

### 15.2 已经做得好的非功能性点

**1. ZIP 包安全有初步防线**

`PackageReader.read_entry_index()` 已经检查：

- ZIP entry 数量：`max_zip_entries`
- 单个 entry 解压后大小：`max_entry_uncompressed_bytes`
- 总解压后大小：`max_total_uncompressed_bytes`
- entry 名称的绝对路径、盘符路径、`..` 路径穿越

这比 `python-docx` 默认的 `ZipFile.read()` 全量读取模式更安全。对自研解析器而言，这部分应继续保留，并扩展成更细的 DOCX preflight。

**2. 正文主 XML 使用 `iterparse`**

`DocumentBodyParser.parse()` 对 `word/document.xml` 使用 `ET.iterparse(stream, events=("start", "end"))`，只在 body 的直接子节点结束时解析段落或表格，并在处理后 `elem.clear()`。

这避免了把整篇 `document.xml` 一次性构造成 DOM。对大量段落的 DOCX，这是 demo 里最重要的内存优化。

**3. 关系索引是只读多路索引**

`RelationshipIndex.from_records()` 同时构建：

- `(source_part, rel_id)` 索引
- `source_part` 索引
- `rel_type` 索引
- `(source_part, rel_type)` 索引

正文解析和资源解析不需要重复扫描所有 relationship，这个设计值得保留。

**4. 并发上下文基本隔离**

`DocxParser.parse()` 每次调用都创建新的 `warnings`、`PackageReader`、`RelationshipIndex`、`StylesParser`、`NumberingState`、`DocumentBodyParser`。`NumberingState` 也明确是单篇文档状态。

这避免了多文档并发时最容易出现的编号串扰、warning 串扰和 ID 串扰。

**5. 输出 XML 有降噪意识**

`renderers/xml.py` 已经做了：

- 相邻同语义 run 合并，减少 XML 碎片。
- 默认超链接蓝色和下划线过滤，避免重复输出视觉默认样式。
- 图片通过 `<image ref="...">` 和 `<assets>` 引用，不把二进制或 data URI 放进文本流。
- 正文、资源、supplemental 分层。
- 文本和属性使用 `html.escape` 转义，基本避免非法 XML 字符串。

这些都符合“尽量省 token，但保留 LLM 需要的信息”的方向。

### 15.3 输入安全还可以补强的地方

当前 `ParseOptions` 只有三个 ZIP 维度限制：

```python
max_zip_entries
max_entry_uncompressed_bytes
max_total_uncompressed_bytes
```

建议扩展为完整的 DOCX preflight 配置：

| 建议配置                                 | 目的                           |
| ------------------------------------ | ---------------------------- |
| `max_input_file_bytes`               | 读取 ZIP 之前先限制原始文件大小           |
| `max_compression_ratio`              | 防止极高压缩比 entry 造成 CPU/内存炸弹    |
| `max_xml_total_uncompressed_bytes`   | XML part 与媒体 part 分开计预算      |
| `max_media_total_uncompressed_bytes` | 防止大量图片导出拖垮磁盘                 |
| `max_media_count`                    | 防止海量图片 relationship 造成输出目录爆炸 |
| `max_relationship_count`             | 防止关系图异常大                     |
| `max_styles_count`                   | 防止样式表异常大                     |
| `max_numbering_levels`               | 防止编号定义异常大                    |
| `max_body_blocks`                    | 防止超长正文一次性进入内存                |
| `max_table_rows` / `max_table_cells` | 防止超大表格递归解析和 XML 输出爆炸         |
| `max_table_nesting_depth`            | 防止嵌套表格递归过深                   |
| `max_run_count_per_paragraph`        | 防止碎 run 文档造成对象数量爆炸           |
| `max_warning_count`                  | 防止异常文档生成海量 warning           |
| `max_output_chars`                   | 防止最终 XML 在内存和 token 上失控      |

还建议在 `PackageReader.read_entry_index()` 增加这些检查：

1. **重复 entry 名称拒绝**

当前用 `names: set[str]` 收集名称，但没有显式检测重复 entry。ZIP 允许重复文件名，不同库打开重复 entry 的行为可能不一致。建议发现重复名称直接拒绝，避免 relationship 指向的 part 出现歧义。

2. **压缩方法白名单**

只允许 `ZIP_STORED` 和 `ZIP_DEFLATED`，或至少拒绝当前运行环境不希望处理的 BZIP2/LZMA。否则某些压缩方法可能带来明显 CPU 开销。

3. **加密 entry 拒绝**

检查 `ZipInfo.flag_bits & 0x1`。加密 DOCX 对服务端解析没有意义，晚到读取阶段才失败会浪费调度资源。

4. **压缩比限制**

对每个 entry 计算近似比值：

```text
ratio = uncompressedSize / max(compressedSize, 1)
```

超过阈值的 entry 可以拒绝，或进入更严格的低并发队列。

5. **Content Types 校验**

当前只检查 `[Content_Types].xml` 和 `word/document.xml` 存在。建议进一步确认 `word/document.xml` 的 content type 是 Word 主文档类型，避免“像 DOCX 的 ZIP”混入。

6. **XML 解析库加固**

当前使用标准库 `xml.etree.ElementTree`。建议在服务端版本切换为 `defusedxml.ElementTree`，或封装一个统一的 `safe_parse_xml_part()`，集中处理实体扩展、超大树、解析错误和耗时指标。

### 15.4 并发模型还可以优化的地方

`parse_many()` 使用：

```python
worker_count = max_workers or min(32, (os.cpu_count() or 1) + 4, len(paths))
ThreadPoolExecutor(max_workers=worker_count)
```

这适合 I/O 偏重任务，但 DOCX 解析包含大量 Python XML 对象构造、递归遍历、字符串拼接和 JSON/XML 序列化。这些工作受 GIL 影响明显，线程池不一定能提升吞吐。

建议改成两层执行策略：

```text
API / async 调用层
  -> asyncio.Semaphore 控制全局解析并发
  -> run_in_executor
     -> 小文件 / I/O 型：ThreadPoolExecutor
     -> 大文件 / CPU 型：ProcessPoolExecutor
```

文件可先按 preflight 分类：

| 输入特征                        | 推荐执行器                |
| --------------------------- | -------------------- |
| 小 DOCX、少图片、少表格              | thread pool          |
| 大 `document.xml`、大表格、大量 run | process pool         |
| 大量图片导出                      | thread pool，但限制磁盘写并发 |
| 可疑高压缩比                      | 低并发隔离队列              |

同时需要补：

1. **按内存预算计算 worker 数**

当前 worker 数只看 CPU 和文件数量。更安全的策略是：

```text
worker_count = min(
  configured_max_workers,
  cpu_based_workers,
  floor(available_memory / per_document_memory_budget),
  len(paths)
)
```

其中 `per_document_memory_budget` 可以由 preflight 的 XML 总大小、媒体大小、预计 block 数估算。

2. **有界提交，避免一次性提交所有 futures**

当前会把所有路径一次性 submit 到 executor。大批量任务可以改成 bounded queue 或按批提交，避免上万个 Future 和输出目录同时进入调度。

3. **单文档超时**

`future.result()` 没有 timeout。线程池中的 Python 任务超时后无法强杀，所以真正的“硬超时”更适合放在进程池或子进程模型里。

建议提供：

```text
soft_timeout_seconds: 记录 warning，停止后续昂贵阶段
hard_timeout_seconds: process worker 终止
```

4. **服务端异步入口**

如果接入 WisePenCloud-AI 这类 async tool，demo 的同步 `parse()` 不应直接在 event loop 内调用。应提供：

```python
async def parse_async(path, options, executor, semaphore):
    async with semaphore:
        return await loop.run_in_executor(executor, parse_sync, path, options)
```

这正好补齐前文指出的 `DoclingParser.parse()` 阻塞事件循环问题。

5. **输出目录并发冲突**

`_parse_one()` 使用：

```python
output_dir = output_base / docx_path.stem
```

如果两个输入文件同名不同路径，或同一个文件被重复提交，多个 worker 会写同一个目录。`write_outputs()` 还会删除旧的 `parsed.json` / `readable.md`，存在并发互相覆盖的风险。

建议输出目录改为：

```text
{output_base}/{safe_stem}-{sha256[:12]}-{run_id}/
```

或先写到 temp dir，成功后原子 rename 到最终目录。

### 15.5 版本化和可复现性缺口

demo 每次解析都会重新读取 ZIP、解析 styles、numbering、relationships、body、assets，然后重新生成 XML。对一个干净 parser 来说，这不是必须由 parser 自己缓存解决的问题；它首先要保证同样输入和同样 options 产生稳定、可复现、可由上层安全缓存的结果。

建议补三类 metadata：

**1. 输入指纹**

parser 可以接受调用方传入 `input_fingerprint`，也可以可选计算 DOCX 文件 sha256：

```text
inputFingerprint = sha256(original docx bytes)
```

这不是内容寻址存储，只是为了让输出和 metrics 可追踪、可比较。

**2. parser/schema/options 版本**

输出 metadata 建议包含：

```text
parserName
parserVersion
schemaVersion
optionsHash
dependencyVersions
```

`optionsHash` 至少包含：

- `revision_mode`
- `include_runs`
- `include_raw_hints`
- supplemental 是否输出
- asset 输出模式
- XML schema 版本
- chunk/token 预算参数

**3. 结构统计和质量摘要**

```text
blockCount
runCount
tableCount
assetCount
warningCount
outputChars
estimatedTokens
parseMetrics
```

上层如果要做缓存，可以用：

```text
inputFingerprint + parserVersion + schemaVersion + optionsHash
```

但 parser 本体只负责暴露这些字段，不负责 Redis/Mongo/TTL/cache invalidation。

这样上层可以先给 LLM 低 token 的 manifest/outline，后续再调用 parser 的 window 生成能力取得局部 XML。

### 15.6 XML 输出和 token 预算优化

当前 `to_llm_xml()` 会把完整 XML 全部拼成 list，再 `"\n".join(lines)`，最后 `write_text()` 一次性写出。这有三个问题：

1. 大文档会同时持有 `ParsedDocument`、`lines`、完整 XML 字符串、写文件缓冲。
2. 没有 `max_output_chars` 或 token 预算。
3. 首轮返回给 LLM 的内容和完整归档内容没有分层。

建议把输出拆成四类视图：

```text
manifest.xml
  文档元信息、统计、warnings 摘要、可用 selectors

outline.xml
  标题树、表格摘要、图片清单、supplemental 摘要

window.xml
  按 block/table/note/image selector 读取的局部窗口

full.xml
  完整结构，通常用于文件输出、测试或上层持久化，不直接塞进 prompt
```

渲染器也建议改成 generator / writer 模型：

```python
def iter_llm_xml(parsed, view, budget) -> Iterator[str]:
    yield "<?xml ..."
    ...
```

这样可以边生成边计数、边截断、边写入，避免完整 XML 字符串常驻内存。

token 降噪方面，demo 已经合并 run，但还可以继续优化：

| 当前输出                | 可优化方向                                      |
| ------------------- | ------------------------------------------ |
| 每个段落都输出 `page`      | 页码只是 hint，可在连续相同页时省略或放进 page marker        |
| 每个 block 重新编号为 `b1` | 保留稳定 locator，避免 debug/warning 和最终 XML 对不上  |
| 大表格完整输出             | 超阈值表格输出 schema + header + sample + locator，完整内容放 full view |
| 嵌套表格压成纯文本           | 小嵌套表格保留结构，大嵌套表格输出 preview + loc，可用 window/full 取完整结构 |
| supplemental 全量输出   | 默认输出摘要，按 note/comment/header selector 读取全文 |
| run 格式逐段输出          | 对长连续格式区域做 span 合并，或只保留任务相关格式               |
| 图片资产全量清单            | 默认只输出正文引用到的图片，未引用资产放 manifest              |

### 15.7 中间模型和定位能力优化

`ParsedDocument` 已经有结构化中间模型，但当前内部 block id 和最终 XML id 存在不一致风险：

- `DocumentBodyParser` 内部会为正文段落、表格、单元格内段落、嵌套表格都分配 `bN`。
- `renderers.xml.block_to_xml()` 输出顶层 body 时重新按 `enumerate(parsed.blocks, start=1)` 分配 `b1`、`b2`。
- warnings、raw hints、debug blocks 引用的是内部 id，最终 XML 引用的是渲染 id。

建议把定位字段拆清楚：

```text
internalId: 解析器内部稳定 id
xmlId: 当前视图内 id
locator: part + block order + table path + paragraph path
sourcePart: word/document.xml / word/header1.xml / ...
sourcePath: 可选 XPath-like 路径
```

对 LLM 最有用的是短 locator，例如：

```xml
<p id="b12" loc="body.12">...</p>
<cell loc="body.15.r2.c3">...</cell>
<note id="3" loc="footnotes.3">...</note>
```

这样后续自研的窗口生成器可以稳定定位，不依赖 debug 文件，也不绑定 WisePenCloud-AI 的 `tool_content_read`。

### 15.8 样式和编号的性能优化

`StyleMap.resolve_heading_level()`、`resolve_numbering()`、`resolve_run_format()` 当前每次调用都会递归 basedOn 链，并用 `visited=set()` 做循环保护。大量 run、同一样式重复出现时，这会形成可避免的重复计算。

建议在 `StyleMap` 内加入只读 memoization：

```text
_heading_level_cache: dict[str, int | None]
_numbering_cache: dict[str, tuple[str, int] | None]
_run_format_cache: dict[str, dict]
```

构建后一次性 freeze，后续解析只读查询。注意不要把 warning 在缓存命中时重复追加。

编号方面，`NumberingState` 已经正确把运行时计数和定义表分离。后续可以补：

- 对极深 `ilvl` 做上限。
- 对异常大的编号值做输出长度上限。
- 对 unsupported format 的 warning 做总量限制。
- 把编号 label 作为独立 XML 属性或 `<num>` 子节点，而不是只拼成 run，便于 LLM 区分原文文本和解析器合成文本。

### 15.9 表格和嵌套结构优化

demo 现在保留表格行、列、横向合并、纵向合并标记，但 `rowSpan` 暂时固定为 1，`vMerge` 只记录 `restart/continue`。这会影响复杂表格的结构还原。

建议分三层处理：

1. **轻量表格**

行列数低于阈值时完整输出：

```xml
<table rows="8" cols="4">
  ...
</table>
```

2. **大表格**

超过阈值时输出：

```xml
<table id="b20" rows="12000" cols="8" overflow="window" loc="body.20">
  <header>...</header>
  <sample rows="1-5">...</sample>
</table>
```

3. **复杂嵌套表格**

不要只放到 debug。debug 是开发辅助，不应作为信息完整性的唯一承载。建议最终 XML 中保留：

```xml
<nested-table loc="body.20.r3.c2.tbl1" text-preview="..." overflow="window" />
```

这样既节省 token，又不丢结构。

还应加入解析期上限：

- `max_table_rows`
- `max_table_cells`
- `max_cell_text_chars`
- `max_nested_table_depth`
- `max_table_output_chars`

### 15.10 图片和资产输出优化

`AssetExtractor` 已经做到流式复制图片，并在 XML 中使用资源引用。下一步建议：

1. **图片去重**

多个 relationship 可能指向同一 `word/media/image1.png`，或不同 entry 内容相同。建议以 `packagePath` 或 `sha256(blob)` 去重，避免重复写磁盘和重复 XML asset。

2. **资产预算**

加入：

```text
max_asset_count
max_asset_bytes
max_single_asset_bytes
export_assets: none | referenced | all
```

对 LLM 文本流来说，默认可以是 `referenced`，只导出正文或 supplemental 中实际引用到的资产。

3. **原子写入**

当前直接写 `assets/imgN.ext`。如果中途失败，可能留下半文件。建议写到 temp 文件，成功后 replace。

4. **图片元信息轻量化**

大多数 LLM 任务更需要：

```text
id, contentType, sizeBytes, alt/title/name, width/height, sourcePart, locator
```

图片本体可以交给后续视觉模型或文件读取工具，不应进入 XML 文本流。

### 15.11 supplemental 信息优化

demo 已经把 header、footer、footnote、endnote、comment 放在 `<supplemental>`，这比 Docling 默认只导出 BODY 更接近“保留所有信息”。

但当前 `AncillaryParser` 有几个可优化点：

1. **页眉页脚需要 section-aware**

现在按文件名扫描 `word/header*.xml` 和 `word/footer*.xml`，会解析所有存在的 header/footer part。Word 实际上通过 `sectPr` 和 relationship 引用决定每个 section 使用哪个 header/footer，且有 first/even/default 类型。

建议输出：

```xml
<header id="header1" section="1" kind="default">...</header>
<footer id="footer2" section="2" kind="first">...</footer>
```

这样 LLM 能知道它们出现在哪些页面区间，而不是把未使用的页眉页脚混在一起。

2. **supplemental 解析应复用正文 inline parser**

当前 `_paragraph_text()` 只取纯文本，链接、图片、脚注引用、格式、字段会丢失。建议把 `DocumentBodyParser` 抽出一个可复用的 `InlineParser`，body、cell、header/footer、notes/comments 共用。

3. **supplemental 默认摘要化**

脚注、尾注、批注很多时，全量输出会非常费 token。建议默认输出 id、作者、日期、preview 和 locator；完整内容由 `full` view 或 `window(loc=...)` 输出。

### 15.12 Debug 和观测优化

当前 `ParseOptions.debug` 默认是 `True`，`parse_many()` 里也强制 `debug=True`。这适合 demo 阶段，但不适合批量或线上解析。

主要风险：

- `internal_blocks.json` 可能比最终 XML 更大。
- `styles.json`、`numbering.json`、`relationships.json` 在大文档里会放大磁盘写。
- 多 worker 同时写 debug 会让磁盘 I/O 成为瓶颈。
- debug 写失败只追加 warning，但没有阶段 metrics，很难知道慢在哪里。

建议改成：

```text
debug: false by default
debug_level: off | summary | sampled | full
debug_max_bytes_per_file
debug_sample_blocks
```

同时加入阶段级 metrics：

```text
preflight_ms
content_types_ms
relationships_ms
styles_ms
numbering_ms
assets_ms
body_ms
ancillary_ms
render_ms
write_ms
total_ms
peak_rss_mb
input_bytes
zip_uncompressed_bytes
xml_bytes
asset_bytes
block_count
run_count
table_count
warning_count
output_chars
estimated_tokens
```

这可以借鉴 Docling `BasePipeline` 的 profiling 思路，也能接到 WisePenCloud-AI 的 tool 日志和 metrics。

### 15.13 错误和降级策略优化

demo 已经有 warning 机制和批量单文件异常收敛，但还需要更细的降级层级：

| 阶段                      | 当前行为                       | 建议                                      |
| ----------------------- | -------------------------- | --------------------------------------- |
| package validate        | 严重错误直接抛出                   | 保留，但错误类型结构化                             |
| styles/numbering XML 解析 | 多数会直接抛出                    | 解析失败时 fallback 到空样式/空编号并 warning        |
| relationship 缺失         | `require()` 可能抛 `KeyError` | 改成 `get()` + warning，正文继续               |
| body 解析                 | 异常会中断整篇                    | block 级 try/catch，坏 block 输出 `<unsupported>` + debug/warning |
| asset 导出                | 单图失败可能中断 assets 阶段         | 单 asset warning，继续解析正文                  |
| XML render              | unsupported block 会抛出      | 未知 block 输出 `<unsupported>` 或转 preview  |
| debug write             | 已收敛成 warning               | 保留，但限额                                  |

输出给调用方的错误建议结构化：

```text
severity: fatal | partial | warning
code
stage
part
locator
message
recoverable
```

这样上层可以区分“完全不可读”“部分可读”“只是少量对象降级”。

### 15.14 工程化接口优化

demo 当前 API 简洁，但还没有和服务端工具链对齐。建议补这些接口：

```python
class DocxParser:
    def preflight(self, path, options) -> PreflightResult: ...
    def parse(self, path, options) -> ParsedDocument: ...
    def render(self, parsed, view, budget) -> RenderResult: ...

async def parse_async(path, options, executor, semaphore) -> ParsedDocument: ...
```

`ParseOptions` 建议拆成：

```text
ParseLimits       输入和结构上限
ParseFeatures     revision、runs、raw hints、assets、supplemental
RenderOptions     XML view、budget、schema version
ExecutionOptions  timeout、executor、debug、metrics
```

这样调用方配置、可复现性 metadata 和测试矩阵都会更清晰；上层若需要缓存，也可以基于这些字段自行构造 key。

另外建议补 CLI 或服务端返回对象：

```text
ok
status: success | partial | failed
xml_path
manifest_path
asset_manifest
metrics
warnings_summary
errors
```

这保持 parser 输出干净：返回文件路径、XML 字符串或结构化对象即可，不直接耦合 WisePenCloud-AI 的 `ToolReturn`、`cacheable_texts` 或 `content_receipt`。

### 15.15 demo 优化优先级

建议按下面顺序推进：

1. **加输出目录隔离和原子写入**

先解决 `output_base / docx_path.stem` 的并发覆盖问题。这个问题最容易在批量解析中造成错误结果，而且改动相对小。

2. **把 debug 默认改为关闭或 summary**

保留 full debug 能力，但线上和批量默认不写大 JSON，减少磁盘 I/O 和峰值时间。

3. **补完整 DOCX preflight**

在现有 entry 数量和大小限制上，加重复 entry、压缩比、加密、压缩方法、媒体预算、XML 预算、表格/块/run 上限。

4. **补版本化 metadata 和输入指纹**

输出 `inputFingerprint/parserVersion/schemaVersion/optionsHash/dependencyVersions`，让上层可自行判断是否复用旧结果。

5. **把 XML 渲染改成流式和预算感知**

不要一次性构造完整 XML 字符串。先支持 `manifest/outline/full` 三种 view，再补 selector window。

6. **建立 XML-aware locator/window**

按 heading、paragraph、table、note、comment、asset 建 locator。长文档默认返回 outline，精读时由 parser 生成局部 window。

7. **并发从固定线程池升级为资源预算调度**

按 preflight 估算大小，选择 thread/process pool，并加单文档超时。

8. **给 StyleMap 加 memoization**

降低大量 run 和重复 style 的递归成本，同时避免循环 warning 重复放大。

9. **supplemental 复用正文 inline parser**

保证页眉页脚、脚注尾注、批注中的链接、字段和图片引用不会在“完整保留信息”目标下被悄悄降级成纯文本。

10. **补 metrics 和压测**

用前文 `11.5` 的样本跑 p50/p95、峰值 RSS、输出字符数、estimated tokens、window generation latency 和 fallback rate。

### 15.16 demo 与前文架构的差距总结

| 能力       | 当前 WisePenCloud-AI / 外部库启发                           | demo 当前状态            | 建议                                       |
| -------- | ---------------------------------------------------- | -------------------- | ---------------------------------------- |
| 输入边界     | 平台有 `ToolRunFileStore`，但 parser 不需要                  | 直接读路径               | 保持干净路径/bytes/file-like 输入，补输入指纹和 preflight |
| 版本化      | `DocumentParseCache` 强调 parser version              | metadata 较少          | 加 `parserVersion/schemaVersion/optionsHash` |
| 长文本治理    | `ToolOutputCache` / `ToolContentStore` 有分层思想         | 全量 XML 文件输出          | 加 manifest/outline/window/full，不实现 receipt |
| 并发       | tool semaphore + timeout，Docling batch concurrency   | `ThreadPoolExecutor` | 加资源预算、process pool、超时                    |
| ZIP 安全   | 前文建议补 zip bomb 防护                                    | 已有基础限制               | 补压缩比、重复 entry、加密、媒体预算                    |
| 内存       | Docling pipeline 生命周期，body iterparse                 | body 顶层 iterparse    | 其它 XML part 也封装 safe parse，XML render 流式 |
| token 预算 | 短输出/长输出分层思想                                         | run 合并，但无预算          | manifest/outline/window/full             |
| 输出完整性    | BODY/FURNITURE/NOTES 分层                              | 有 supplemental       | section-aware，supplemental inline 化      |
| 观测       | Docling profiling                                    | debug JSON           | metrics + debug levels                   |
| 降级       | MarkItDown 的 attempts/registry 思想                    | warning 和批量异常        | 阶段级 fallback，错误结构化；不接入 MarkItDown 兜底      |

一句话总结：demo 的“解析核心”已经有很好的雏形，尤其是直接读 OOXML、保留结构、面向 XML 降噪这些方向是对的。下一阶段不应把附件平台能力搬进来，而应把 parser-core 打磨干净：安全预算、版本化 metadata、流式输出、locator/window、资源调度、观测和降级。做到这些后，它才会从 demo 变成可嵌入任意上层服务的 Word -> XML 解析组件。
