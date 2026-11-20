#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 PDF 提取正文文本，供论文分析流水线（`paper-analysis-report`）使用。

用法:
  python extract_pdf.py paper.pdf                    # 正文写到 paper.txt，控制台只打印统计
  python extract_pdf.py paper.pdf -o analysis/source/paper.txt
  python extract_pdf.py paper.pdf --pages 1-5,9 -o out.txt

为什么用它而不是 pdftotext / pypdf:
  * PyMuPDF 是纯 wheel 依赖，Windows 上不用装 poppler；本机已装 1.28.2。
  * 默认**展开连字**（ﬁ → fi、ﬂ → fl）并做**去断词**。否则 `check_docx.py` 的
    "英文引文逐字核对" 会在带连字/换行断词的引文上误报 FAIL。
  * 输出 UTF-8 / LF，便于 grep 回查与 `--source` 逐字核对。
  * 控制台只打印统计，不打印正文（GBK 控制台打印 ﬁ、© 会 UnicodeEncodeError）。
"""
import argparse
import os
import sys

try:
    import pymupdf
except ImportError:  # 旧名 / 新名兼容
    try:
        import fitz as pymupdf
    except ImportError:
        sys.exit(
            "PyMuPDF 未安装。请执行：\n"
            "  python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple PyMuPDF"
        )


def build_flags() -> int:
    """文本提取 flags：展开连字 + 去断词 + 只取页面可见区域。"""
    flags = pymupdf.TEXTFLAGS_TEXT
    flags |= getattr(pymupdf, "TEXT_DEHYPHENATE", 0)
    flags &= ~getattr(pymupdf, "TEXT_PRESERVE_LIGATURES", 0)
    flags |= getattr(pymupdf, "TEXT_MEDIABOX_CLIP", 0)
    return flags


def parse_pages(spec: str, total: int):
    """'1-5,9' → 0 基页码列表；空则全部。"""
    if not spec:
        return list(range(total))
    picked = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, last = part.split("-", 1)
            picked.extend(range(int(first), int(last) + 1))
        else:
            picked.append(int(part))
    return [page - 1 for page in picked if 1 <= page <= total]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PDF → 正文文本（PyMuPDF）")
    ap.add_argument("pdf", help="PDF 路径")
    ap.add_argument("-o", "--out", default="", help="输出 txt（默认与 PDF 同目录同名）")
    ap.add_argument("--pages", default="", help="页码，如 1-5,9（默认全部）")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.pdf):
        sys.exit("找不到 PDF：%s" % args.pdf)

    doc = pymupdf.open(args.pdf)
    flags = build_flags()
    pages = parse_pages(args.pages, len(doc))
    empty = 0
    chunks = []
    for page in pages:
        part = doc[page].get_text("text", flags=flags)
        if not part.strip():
            empty += 1
        chunks.append(part)
    text = "\n".join(chunks)

    out = args.out or (os.path.splitext(args.pdf)[0] + ".txt")
    parent = os.path.dirname(os.path.abspath(out))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    ligs = text.count("\ufb01") + text.count("\ufb02") + text.count("\ufb00")
    print("pages     :", len(pages), "/", len(doc))
    print("empty     :", empty)
    print("chars     :", len(text), "| cjk:", cjk)
    print("ligatures :", ligs, "(应为 0；非 0 说明连字未展开)")
    print("out       :", out)
    if len(doc) == 0:
        print("[warn] 这份 PDF 没有任何页面")
    if empty == len(pages) and pages:
        print("[warn] 全部页面都抽不到文本——大概率是扫描件，需要 OCR 或按页截图")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
