from __future__ import annotations

import argparse
from pathlib import Path

from docx_llm_parser import DocxParser, ParseOptions
from docx_llm_parser.renderers.html5 import write_outputs as write_html5
from docx_llm_parser.renderers.xml import write_outputs as write_xml


def main() -> int:
    """命令行入口：解析单个 DOCX 并输出语义标记。"""
    parser = argparse.ArgumentParser(
        description="Parse DOCX into LLM-readable semantic markup."
    )
    parser.add_argument("docx", type=Path, help="Input .docx file")
    parser.add_argument("--out", type=Path, default=Path("out"), help="Output base directory")
    parser.add_argument(
        "--format",
        choices=["html5", "xml"],
        default="html5",
        help="Output format: html5 (HTML5 implicit close, ~51%% token savings) or xml (current XML)",
    )
    parser.add_argument("--keep-empty-paragraphs", action="store_true")
    parser.add_argument("--no-runs", action="store_true")
    parser.add_argument("--no-raw-hints", action="store_true")
    parser.add_argument(
        "--revision-mode",
        choices=["final", "original", "review"],
        default="final",
        help="How to handle tracked revisions in visible text",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    output_dir = args.out / args.docx.stem
    # 当前开发阶段 debug 常开，不提供 --no-debug。
    options = ParseOptions(
        preserve_empty_paragraphs=args.keep_empty_paragraphs,
        include_runs=not args.no_runs,
        include_raw_hints=not args.no_raw_hints,
        debug=True,
        revision_mode=args.revision_mode,
        output_dir=output_dir,
    )

    parsed = DocxParser().parse(args.docx, options)
    # 根据 --format 选择渲染器
    if args.format == "html5":
        paths = write_html5(parsed, output_dir)
        output_key = "html"
    else:
        paths = write_xml(parsed, output_dir)
        output_key = "xml"

    if not args.quiet:
        # 控制台只打印摘要，详细中间结果在 debug 目录。
        print(f"[OK] Parsed {args.docx}")
        print(f"[OK] Output ({args.format}): {paths[output_key]}")
        print(f"[OK] Debug: {parsed.debug_dir}")
        print(
            "[OK] Summary: "
            f"blocks={len(parsed.blocks)}, "
            f"assets={len(parsed.assets)}, "
            f"styles={len(parsed.styles)}, "
            f"relationships={len(parsed.relationships)}, "
            f"warnings={len(parsed.warnings)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
