#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_docx —— 技能自带的可移植出稿 CLI（不依赖 DSH，只要 python-docx）。

三种版本由调用方指定，也可从 markdown 的文档头自动推断：

  python make_docx.py --kind detail --input <详细版.md> --out <reports>
  python make_docx.py --kind brief  --input <简略版.md> --out <reports> --pages
  python make_docx.py --kind notes  --input <摘录版.md> --out <reports>
  python make_docx.py --auto  --input a.md b.md c.md --out <reports>   # 按文档头 version_label 推断

退出码：0 正常；1 有版本超篇幅（--pages 或汉字数判定）；3 缺 python-docx。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from docx_core import KINDS, build  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover
    sys.stderr.write(f"缺少渲染核心 docx_core.py：{exc}\n")
    raise SystemExit(3)

# 篇幅参考上限（汉字数）：简略版 2–3 页、摘录版尽量压到 1–2 页
MAX_CJK = {"brief": 3400, "notes": 2000}
META_RE = re.compile(r"<!--\s*meta:\s*(\{.*?\})\s*-->", re.DOTALL)


def infer_kind(md_path: str) -> str:
    """从文档头的 version_label 或文件名推断版本类型。"""
    try:
        with open(md_path, "r", encoding="utf-8") as fh:
            head = fh.read(4000)
    except OSError:
        head = ""
    m = META_RE.search(head)
    if m:
        try:
            label = str(json.loads(m.group(1)).get("version_label", "")).strip().lower()
            if label in KINDS:
                return label
        except json.JSONDecodeError:
            pass
    name = os.path.basename(md_path)
    if "摘录" in name or "notes" in name.lower():
        return "notes"
    if "简略" in name or "brief" in name.lower():
        return "brief"
    return "detail"


def count_pages(docx_path: str) -> int | None:
    """尽力而为的页数统计：读 Windows 文档属性里缓存过的页数。

    刚生成的文档从未被 Word 打开过，通常拿不到值——**篇幅以汉字数为准**。
    本函数不用 Word COM：本 preset 生成的文档带 w:updateFields，
    Word 自动化打开它会抛 "Word 未能引发事件"。
    """
    try:
        import subprocess

        quoted_dir = os.path.dirname(os.path.abspath(docx_path)).replace("'", "''")
        quoted_name = os.path.basename(docx_path).replace("'", "''")
        script = (
            "$ErrorActionPreference='Stop';"
            "$sh=New-Object -ComObject Shell.Application;"
            f"$f=$sh.Namespace('{quoted_dir}').ParseName('{quoted_name}');"
            "if($f -eq $null){exit 2};"
            "foreach($p in $f.ExtendedProperties){"
            "  if($p.Name -match 'Pages|页数'){ Write-Output ('PAGES=' + $p.Value); break } }"
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            encoding="utf-8", errors="replace",
            env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=120,
        )
        for line in (out.stdout or "").splitlines():
            if line.strip().startswith("PAGES="):
                value = line.split("=", 1)[1].strip()
                if value.isdigit():
                    return int(value)
        return None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="markdown → docx（详细版 / 简略版 / 摘录版）")
    ap.add_argument("--input", nargs="+", required=True, help="一个或多个 markdown 文件")
    ap.add_argument("--kind", choices=list(KINDS), help="版本类型；与 --auto 二选一")
    ap.add_argument("--auto", action="store_true", help="按文档头 version_label（或文件名）为每个输入推断版本")
    ap.add_argument("--out", required=True, help="输出目录（或 .docx 路径，仅单输入时）")
    ap.add_argument("--out-name", default="", help="输出文件名（不含扩展名），仅单输入时有效")
    ap.add_argument("--no-numbering", action="store_true", help="关闭表/图自动编号")
    ap.add_argument("--pages", action="store_true", help="尝试统计页数（通常拿不到，见函数说明）")
    args = ap.parse_args()

    if not args.kind and not args.auto:
        args.auto = True  # 默认按文档头推断，最省心

    results = []
    for src in args.input:
        kind = args.kind if args.kind else infer_kind(src)
        base = args.out_name or os.path.splitext(os.path.basename(src))[0]
        if args.out.endswith(".docx") and len(args.input) == 1:
            dst = args.out
        else:
            dst = os.path.join(args.out, base + ".docx")
        stats = build(src, dst, kind, number_assets=not args.no_numbering)
        if args.pages:
            stats["pages"] = count_pages(dst)
        results.append(stats)

    exit_code = 0
    for s in results:
        line = (
            f"[ok] {os.path.basename(s['output'])}  kind={s['kind']}"
            f"  标题{s['headings']}  表{s['tables']}  图{s['images']}  引文{s['quotes']}"
            f"  汉字≈{s['cjk_chars']}"
        )
        if s.get("pages") is not None:
            line += f"  页数={s['pages']}"
        print(line)
        if s["missing_images"]:
            print(f"  [warn] 以下插图路径不存在，已写成占位文字：{', '.join(s['missing_images'])}")
        limit = MAX_CJK.get(s["kind"])
        if limit and s["cjk_chars"] > limit:
            print(f"  [warn] {s['kind']} 版正文 {s['cjk_chars']} 汉字，超出参考上限 {limit}："
                  f"删段落而不是改字号")
            exit_code = 1
        if s.get("pages") and s["kind"] == "brief" and s["pages"] > 3:
            print(f"  [warn] 简略版 {s['pages']} 页，超出 2–3 页")
            exit_code = 1
    print(json.dumps({"ok": exit_code == 0, "documents": results}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
