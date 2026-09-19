#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_env —— 技能自带的依赖体检。让别人拿到这个技能后先跑它。

  python check_env.py

检查：Python 版本、python-docx 是否可用、技能目录是否完整（SKILL.md 与 10 个参考文件）、
脚本目录是否可写（出稿要写 docx）。退出码 0 = 可用；1 = 缺依赖。
"""
from __future__ import annotations

import io
import os
import sys

# 强制 UTF-8 输出，避免 Windows 控制台编码把中文打成乱码
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
REFERENCE_DIR = os.path.join(SKILL_DIR, "reference")
EXPECTED_REFS = [
    "workflow.md", "report-template.md", "brief-template.md", "notes-template.md",
    "docx-export.md", "novelty-rubric.md", "ic-domain-notes.md",
    "subagent-prompts.md", "compare-template.md", "checklist.md",
]
EXPECTED_TOOLS = ["docx_core.py", "make_docx.py", "check_docx.py"]

problems: list[str] = []
warns: list[str] = []


def line(ok: bool, text: str) -> None:
    print(f"  [{'OK' if ok else 'X '}] {text}")


print("paper-analysis-report 技能 · 环境体检")
print(f"技能目录: {SKILL_DIR}")
print("")

# 1) Python 版本
major, minor = sys.version_info[:2]
line((major, minor) >= (3, 8), f"Python {sys.version.split()[0]}（需要 3.8+）")
if (major, minor) < (3, 8):
    problems.append("Python 版本过低：请用 3.8 及以上")

# 2) python-docx
try:
    import docx  # noqa: F401

    line(True, "python-docx 已安装（生成 Word 必要依赖）")
except ModuleNotFoundError:
    line(False, "python-docx 未安装 → 执行：pip install python-docx")
    problems.append("缺 python-docx：pip install python-docx")

# 3) 技能文件完整性
missing_refs = [f for f in EXPECTED_REFS if not os.path.exists(os.path.join(REFERENCE_DIR, f))]
line(not missing_refs, f"参考文件 {len(EXPECTED_REFS) - len(missing_refs)}/{len(EXPECTED_REFS)} 齐全"
     + (f"（缺：{', '.join(missing_refs)}）" if missing_refs else ""))
if missing_refs:
    problems.append(f"参考文件缺失：{', '.join(missing_refs)}")

missing_tools = [f for f in EXPECTED_TOOLS if not os.path.exists(os.path.join(HERE, f))]
line(not missing_tools, f"工具脚本 {len(EXPECTED_TOOLS) - len(missing_tools)}/{len(EXPECTED_TOOLS)} 齐全"
     + (f"（缺：{', '.join(missing_tools)}）" if missing_tools else ""))
if missing_tools:
    problems.append(f"工具脚本缺失：{', '.join(missing_tools)}")

line(os.path.exists(os.path.join(SKILL_DIR, "SKILL.md")), "SKILL.md 存在")

# 4) 出稿目录可写（写到临时文件再删）
try:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=True):
        pass
    line(True, "可写临时目录（出稿需要）")
except Exception as exc:
    line(False, f"临时目录不可写：{exc}")
    problems.append(f"临时目录不可写：{exc}")

# 5) 可选：抽取 PDF 正文用的库（缺失只影响引文核对，不影响出稿）
has_pypdf = False
for mod in ("pypdf", "PyPDF2", "fitz", "pdfplumber"):
    try:
        __import__(mod)
        has_pypdf = True
        line(True, f"可选：{mod} 已安装（用于抽取 PDF 正文做引文核对）")
        break
    except ModuleNotFoundError:
        continue
if not has_pypdf:
    warns.append("未安装 PDF 文本抽取库（pypdf 等）：引文逐字核对需要自己提供正文文本")

print("")
if problems:
    print("结论：不可用，请先处理上面标 X 的项。")
    for p in problems:
        print(f"  - {p}")
    raise SystemExit(1)
print("结论：可用。下一步：" )
print("  python make_docx.py --auto --input <各版.md> --out <reports>")
print("  python check_docx.py --md <详细版.md> <简略版.md> <摘录版.md> --source <paper.txt>")
for w in warns:
    print(f"  提示：{w}")
