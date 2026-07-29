from __future__ import annotations

import argparse
from pathlib import Path

from docx_llm_parser import DocxParser, ParseOptions
from docx_llm_parser.renderers.xml import write_outputs


def main() -> int:
    """命令行入口：解析单个 DOCX 并输出语义 XML/debug。"""
    parser = argparse.ArgumentParser(description="Parse DOCX into LLM-readable semantic XML.")
    parser.add_argument("docx", type=Path, help="Input .docx file")
    parser.add_argument("--out", type=Path, default=Path("out"), help="Output base directory")
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
    paths = write_outputs(parsed, output_dir)

    if not args.quiet:
        # 控制台只打印摘要，详细中间结果在 debug 目录。
        print(f"[OK] Parsed {args.docx}")
        print(f"[OK] XML: {paths['xml']}")
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
