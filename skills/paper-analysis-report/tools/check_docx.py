#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前校验器：检查生成的 docx / markdown 报告是否合格。

检查项：
  1. 残留标记  —— [待核实] / [论文未给出] / [推断] / [假设] 出现次数（交付版应尽量为 0）
  2. 两版一致  —— 简略版里的每个"带单位数字"都必须能在详细版里找到
  3. 简略版结构 —— 必备章节、长度上限（汉字数）与表格数量
  4. 引文出处  —— 报告里的英文引文必须能在 paper 源文本中逐字找到（规范化空白后）
  5. 图片引用  —— markdown 里的 ![](path) 与 docx 内的图片数量能否对上

用法：
  python docx_check.py --md reports/A_详细版.md reports/B_简略版.md \
                       --detail reports/A_详细版.docx --brief reports/B_简略版.docx \
                       --source analysis/source/paper.txt

  python docx_check.py --md reports/B_简略版.md --source analysis/source/paper.txt

退出码：0 全部通过（可含 warn）；1 存在 FAIL。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from docx_export import parse_markdown  # 复用同一个 markdown 解析器，保证表数一致
except Exception:  # pragma: no cover
    parse_markdown = None  # type: ignore[assignment]

# ── helpers ─────────────────────────────────────────────────────────────────
# 两类标记的严重度不同：
#   未解决标记 —— 交付版里出现就是 FAIL（说明流水线没跑完）
#   留痕标记   —— 详细版按证据链要求保留（warn）；简略版出现即 FAIL（摘要卡不该带）
# 注意 [待核实] 属**留痕**：它标记的是"证据不在手上（如 SI 未随材料提供）"这类
# 已记录在案的核查状态，是报告诚实性的一部分；`TODO`/`TBD` 才是流水线没跑完。
UNRESOLVED_MARKERS = ["TODO", "TBD", "FIXME", "???"]
TRACE_MARKERS = ["[待核实]", "[论文未给出]", "[推断]", "[假设]", "[单点证据]"]
ALL_MARKERS = UNRESOLVED_MARKERS + TRACE_MARKERS
BRIEF_MAX_CJK = 3400  # 2–3 页简略版的汉字上限（A4 + 12pt + 1.5 行距 + 2.2cm 页边距的经验值）
# 简略版是"手打报告"式整段文字，标题因人而异，因此每个必备概念都接受若干写法。
# 注意：简略版**不带标题**（文件名即标题）也**不写"一句话结论"**（结论直接落在正文段落里），
# 因此这两项都不列为必备章节。
BRIEF_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("实验方法与结果", ("实验方法与结果", "实验做到了什么程度", "实验与结果", "核心结果", "结果与讨论")),
    ("创新点", ("创新点", "技术创新", "主要贡献")),
    ("结论", ("结论", "结论与建议", "复现与建议", "评价与建议")),
)

# ── 摘录版（notes）的校验口径 ───────────────────────────────────────────────
# 摘录版只写三节，且**刻意不含任何评级与编辑判断**（用户要求）：它给读者的是
# "这篇论文做了什么、新在哪、能借什么思路"，不是"值不值得跟"。
NOTES_MAX_CJK = 2000
NOTES_REQUIRED: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("论文在做什么", ("论文在做什么", "论文做了什么", "研究内容", "论文概要")),
    ("创新点", ("创新点", "技术创新", "主要贡献")),
    ("该论文提供的思路", ("该论文提供的思路", "可供借鉴的思路", "可借鉴的思路", "思路借鉴", "启示")),
)
# 出现即 FAIL：摘录版里不得出现分级、评分与编辑判断用语
NOTES_FORBIDDEN: tuple[str, ...] = (
    "A 级", "B 级", "C 级", "D 级", "A级", "B级", "C级", "D级",
    "评级", "分级", "评分", "打分", "值得跟进", "不值得", "不推荐", "建议跟进",
    "证据强度", "可证伪", "我的结论", "我的判断", "我认为", "价值判断",
    "局限", "风险", "复现难度",
)

NUM_UNITS = (
    r"(?:%|％|nm|μm|um|mm2|mm²|pJ|fJ|nJ|mW|μW|uW|W|GHz|MHz|kHz|TOPS|GOPS|FPS|pJ/op|fJ/bit|"
    r"V|mV|dB|×|x|倍|GE|MB|KB|GB|ms|us|μs|ns|ps|bit|Mbps|Gbps|k|K)"
)
NUM_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)?)[\s\u00a0\u3000-]*(" + NUM_UNITS + r")\b", re.UNICODE)
QUOTE_RE = re.compile(r"[“\"]([^“”\"]{20,300})[”\"]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
IMG_MD_RE = re.compile(r"!\[.*?\]\((.+?)\)")


def norm_ws(s: str) -> str:
    s = s.lstrip("\ufeff")  # UTF-8 BOM：若留在首个词前面，该词永远匹配不上
    s = s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-")
    s = s.replace("\u2014", "-").replace("\ufb01", "fi").replace("\ufb02", "fl")
    # 元数据里的 JSON 转义会留下字面量 \n，必须与真实换行一起折叠成空格
    s = s.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
    s = s.replace("-\n", "").replace("-\r", "")
    return re.sub(r"\s+", " ", s).strip().lower()


def match_form(s: str) -> str:
    """引文核对的匹配形式：去空白、去换行连字符、小写。

    PDF 文本重建（pypdf）常在词间丢失空格、把同一句按硬换行切断，并在换行处
    插入连字符（`fur-ther`）。因此核对时两侧都要做同样的规范化，否则真实引文
    也会被误判为"找不到"。
    """
    t = norm_ws(s)
    t = re.sub(r"[\s\u00a0\u3000]+", "", t)
    # 行尾连字符：只在连字符后紧跟小写字母时视为断词连字符。
    # 复合词（full-logic、thirty-two）不受影响：它们本来就该带着连字符匹配。
    t = re.sub(r"-+(?=[a-z])", "", t)
    return t


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def docx_plain(path: str) -> tuple[str, int, int]:
    """Return (all visible text, image count, paragraph count) from a .docx."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        document_xml = zf.read("word/document.xml").decode("utf-8", "replace")
        images = len([n for n in names if n.startswith("word/media/")])
        has_toc = "TOC \\o" in document_xml or "TOC \\" in document_xml
    text = re.sub(r"<w:p[ >]", "\n<w:p ", document_xml)
    text = re.sub(r"<w:tab[^>]*/>", "\t", text)
    text = re.sub(r"<w:br[^>]*/>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    import html

    text = html.unescape(text)
    paragraphs = len(re.findall(r"<w:p[ >]", document_xml))
    return text, images, paragraphs


def md_no_quotes(text: str) -> str:
    """markdown with blockquote lines and fenced code removed (for structural checks)."""
    out = []
    in_fence = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or line.lstrip().startswith(">"):
            continue
        out.append(line)
    return "\n".join(out)


# ── checks ──────────────────────────────────────────────────────────────────
def check_markers(label: str, text: str, is_compact: bool, fails: list, warns: list) -> dict:
    counts = {m: text.count(m) for m in ALL_MARKERS if text.count(m)}
    unresolved = {m: c for m, c in counts.items() if m in UNRESOLVED_MARKERS}
    traced = {m: c for m, c in counts.items() if m in TRACE_MARKERS}
    if unresolved:
        detail = "，".join(f"{k}×{v}" for k, v in unresolved.items())
        fails.append(f"{label} 残留未解决标记：{detail}")
        print(f"  [FAIL] {label} 残留未解决标记：{detail}")
    elif not traced:
        print(f"  [PASS] {label}：无残留标记")
    if traced:
        detail = "，".join(f"{k}×{v}" for k, v in traced.items())
        if is_compact:
            fails.append(f"{label} 紧凑版（简略/摘录）仍带证据链标记（应只留结论）：{detail}")
            print(f"  [FAIL] {label} 紧凑版仍带证据链标记：{detail}")
        else:
            warns.append(f"{label} 保留证据链标记 {detail}（详细版应保留，确认都是必要的）")
            print(f"  [warn] {label} 保留证据链标记 {detail}（详细版允许保留）")
    return counts


def canonical_number_text(text: str) -> str:
    """数字比对用的规范化：去掉全部空白与连字符，统一百分号。

    详细版按表格书写（`2-bit`、`8 bit`、`2.62 ×10⁷`），简略版按行文书写，
    同一个量在两侧的空白/连字符位置不同，必须在这种形式上比对。
    """
    t = re.sub(r"[\s\u00a0\u3000]+", "", text)
    t = t.replace("-", "").replace("‐", "").replace("–", "").replace("—", "")
    return t.replace("％", "%")


def number_tokens(text: str) -> set[str]:
    """归一化后的「数字+单位」集合：去掉数字与单位之间的空白/连字符（2.6× / 2.6 × 同值），
    并统一全角／半角百分号，避免同一测量因书写差异被判成两个数。"""
    found = set()
    for m in NUM_TOKEN_RE.finditer(text):
        unit = m.group(2).replace("％", "%")
        found.add(canonical_number_text(f"{m.group(1)}{unit}"))
    return found


def check_consistency(detail_text: str, brief_text: str, fails: list) -> dict:
    brief_nums = number_tokens(brief_text)
    detail_norm = canonical_number_text(detail_text)
    missing = sorted(n for n in brief_nums if n not in detail_norm)
    if not brief_nums:
        print("  [warn] 该版本里没找到带单位的数字，无法做一致性比对")
    elif not missing:
        print(f"  [PASS] 一致：{len(brief_nums)} 个数字全部出现在详细版")
    else:
        fails.append(f"正文里的数字在详细版中找不到：{', '.join(missing[:12])}")
        print(f"  [FAIL] 数字未在详细版出现（{len(missing)} 个）：{', '.join(missing[:12])}")
    return {"brief_numbers": len(brief_nums), "missing": missing}


def check_brief_structure(label: str, text: str, table_count: int, fails: list, warns: list) -> dict:
    body = md_no_quotes(text)
    cjk = len(CJK_RE.findall(body))
    missing_sections = [
        concept for concept, variants in BRIEF_REQUIRED if not any(v in body for v in variants)
    ]
    if missing_sections:
        fails.append(f"{label} 缺少必备章节：{'、'.join(missing_sections)}")
        print(f"  [FAIL] {label} 缺少必备章节：{'、'.join(missing_sections)}")
    else:
        print(f"  [PASS] {label} 必备章节齐全")
    if cjk > BRIEF_MAX_CJK:
        warns.append(f"{label} 正文汉字 {cjk} 字，可能超过 2–3 页（上限参考 {BRIEF_MAX_CJK}）")
        print(f"  [warn] {label} 正文汉字 {cjk} 字，超出 2–3 页参考上限 {BRIEF_MAX_CJK}")
    else:
        print(f"  [PASS] {label} 长度：正文汉字 {cjk} 字（上限 {BRIEF_MAX_CJK}）")
    if table_count > 3:
        warns.append(f"{label} 含 {table_count} 张表；简略版应当以整段文字为主（手打报告风格），建议不超过 1 张")
        print(f"  [warn] {label} 含 {table_count} 张表；简略版以文字为主，建议 ≤1 张")
    elif table_count > 0:
        print(f"  [PASS] {label} 表格数量 {table_count} 张（简略版以文字为主）")
    else:
        print(f"  [PASS] {label}：纯文字叙述（无表格）")
    return {"cjk": cjk, "tables": table_count, "missing_sections": missing_sections}



def _count_tables(text: str) -> int:
    """统计 markdown 里的表格数量（优先用解析器，退化到表头分隔行计数）。"""
    if parse_markdown is not None:
        try:
            _m, blocks = parse_markdown(text)
            n = sum(1 for t, _ in blocks if t == "table")
            if n:
                return n
        except Exception:
            pass
    return len(re.findall(r"^\|\s*:?-{2,}", text, re.MULTILINE))


def check_notes_structure(label: str, text: str, table_count: int, fails: list, warns: list) -> dict:
    """摘录版：三节齐全 + 不含任何评级/判断用语 + 篇幅最小。"""
    body = md_no_quotes(text)
    cjk = len(CJK_RE.findall(body))
    missing = [concept for concept, variants in NOTES_REQUIRED if not any(v in body for v in variants)]
    if missing:
        fails.append(f"{label} 缺少必备章节：{'、'.join(missing)}")
        print(f"  [FAIL] {label} 缺少必备章节：{'、'.join(missing)}")
    else:
        print(f"  [PASS] {label} 三节齐全（论文在做什么 / 创新点 / 该论文提供的思路）")
    hits = sorted({w for w in NOTES_FORBIDDEN if w in body})
    if hits:
        fails.append(f"{label} 含评级/判断用语（摘录版不应有）：{'、'.join(hits)}")
        print(f"  [FAIL] {label} 含评级/判断用语：{'、'.join(hits)}")
    else:
        print(f"  [PASS] {label}：无评级、无编辑判断用语")
    if cjk > NOTES_MAX_CJK:
        warns.append(f"{label} 正文汉字 {cjk} 字，超出摘录版参考上限 {NOTES_MAX_CJK}")
        print(f"  [warn] {label} 正文 {cjk} 汉字，超出摘录版参考上限 {NOTES_MAX_CJK}")
    else:
        print(f"  [PASS] {label} 长度：正文汉字 {cjk} 字（上限 {NOTES_MAX_CJK}）")
    return {"cjk": cjk, "tables": table_count, "missing_sections": missing, "forbidden_hits": hits}

def collect_quotes(text: str) -> list[tuple[str, bool]]:
    """收集待核对的引文，返回 (引文, 是否独立引文行)。

    只有**独立引文行**（markdown 的 `> ...`）与**英文正文里**的引号内容才当作引文核对；
    中文行文里用引号做强调的短语（如 论文标题、"降 90%" 这类说法）不是引文，
    由 check_quotes 结合上下文（是否为纯英文句）判定。
    """
    # 先切掉文档元数据头：其中的 title/paper 被引号包住，不是引文。
    # （必须用关键字传 count/flags：re.sub 的第三个位置参数是 string。）
    body = re.sub(r"^<!--\s*meta:.*?-->\s*", "", text, count=1, flags=re.DOTALL)
    candidates: list[tuple[str, bool]] = []

    if parse_markdown is not None:
        try:
            _meta, blocks = parse_markdown(body)
            for tag, payload in blocks:
                if tag == "quote":
                    candidates.append((str(payload), True))
        except Exception:
            pass

    for m in QUOTE_RE.finditer(body):
        candidates.append((m.group(1), False))

    # 独立引文行里**没写引号**的英文句子同样要核对：否则把引文从引号里挪出来
    # 就能绕过核对（诊断测试发现的口子）。中文夹注会被 filter_quotes 剥掉。
    for line in body.split("\n"):
        stripped = line.lstrip()
        if not stripped.startswith(">"):
            continue
        text = stripped[1:].strip()
        # 去掉中文出处夹注后再判断是不是英文句子
        text = re.sub(r"[（(][^（()）]*[)）]", " ", text).strip()
        letters = [ch for ch in text if ch.isalpha()]
        if len(text) >= 40 and letters and all(ch.isascii() for ch in letters):
            candidates.append((text, True))
    return candidates


VENUE_RE = re.compile(
    r"(?i)\b(ieee|acm|tcas|tcad|jssc|isscc|vls[iy]|dac|iccad|arxiv|proceedings|conference|symposium|"
    r"journal|transactions|vol\.|no\.|pp\.|doi)\b"
)


def has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _strip_quote_noise(raw: str) -> tuple[str, bool]:
    """剥掉引文两侧的引号、出处标注与中文夹注，返回 (清理后的引文, 是否前置省略号)。"""
    probe = raw.strip().strip('"\'“”「」`').strip()
    leading_ellipsis = bool(re.match(r"^\s*(?:\.\.\.|…)", probe))
    probe = re.sub(r"^\s*(?:\.\.\.|…)+\s*", "", probe)
    for _ in range(6):
        before = probe
        probe = re.sub(r"\s*[（(]\s*(?:§|p\.|pp\.|Table|Fig|Figure|Eq)[^）)]*[）)]\s*$", "", probe)
        probe = re.sub(r"\s*[（(][^（()）]*[)）]\s*$", "", probe)
        probe = probe.strip().strip('"\'“”「」`').strip().rstrip(" .,;:!?…—-、。，；：！？").strip()
        if probe == before:
            break
    return probe, leading_ellipsis


def _latin_ok(cand: str) -> bool:
    if has_cjk(cand):
        return False
    if "\n" in cand or "\\n" in cand or VENUE_RE.search(cand):
        return False
    letters = [ch for ch in cand if ch.isalpha()]
    if not letters:
        return False
    return sum(1 for ch in letters if ch.isascii()) / len(letters) >= 0.75


def _dedup_key(cand: str) -> str:
    # 前/后省略号与包裹引号不参与去重：同一句引文可能同时以 `"..."` 和缩略形式出现
    stripped = re.sub(r"^[\s.…]+", "", cand)
    stripped = re.sub(r"[\s.…]+$", "", stripped)
    stripped = stripped.strip('"\'“”「」')
    return norm_ws(stripped)


def filter_quotes(md_text: str, text: str) -> list[str]:
    """把收集到的候选过滤成"真正需要逐字核对的英文引文"。

    只有两类算引文：**独立引文行**（markdown `> ...`，无论有没有写引号）与
    **纯英文行文里**的引号内容。中文句子里用引号做强调的短语（论文标题、"降 90%"）
    不是引文，一律跳过。前置省略号表示引文从原句中间开始，这类引文可能没有右引号。
    """
    # 独立引文行的判定必须用**同一套清理函数**，否则带中文出处夹注的引文行
    # 会被误判成"行内引号"，再因上下文是中文而被丢弃（这是校验器曾经的漏洞）。
    standalone: set[str] = set()
    for line in md_text.split("\n"):
        stripped = line.lstrip()
        if not stripped.startswith(">"):
            continue
        cleaned, _lead = _strip_quote_noise(stripped[1:].strip())
        if cleaned:
            standalone.add(norm_ws(cleaned))
            standalone.add(_dedup_key(cleaned))

    out: list[str] = []
    seen: set[str] = set()
    for raw, _is_block in collect_quotes(md_text):
        probe, leading_ellipsis = _strip_quote_noise(raw)
        # 从右侧逐字符回退，直到剩下的是纯英文句子
        while probe and not _latin_ok(probe):
            probe = probe[:-1].strip().rstrip('"\'“”「」').strip()
        if not probe:
            continue
        has_ellipsis = bool(re.search(r"\.\.\.|…", probe))
        if len(probe) < 40 and not has_ellipsis:
            continue
        if not _latin_ok(probe) and not leading_ellipsis:
            continue
        if norm_ws(probe) not in standalone and _dedup_key(probe) not in standalone:
            # 行内引号：只有处在一句纯英文行文里才算引文
            ctx = ""
            idx = text.find(raw)
            if idx >= 0:
                ctx = text[max(0, idx - 60) : idx + len(raw) + 60]
            if has_cjk(ctx):
                continue
        key = _dedup_key(probe)
        if key in seen:
            continue
        seen.add(key)
        out.append(probe)
    return out


def check_quotes(label: str, md_text: str, source_text: str | None, fails: list, warns: list) -> dict:
    quotes = filter_quotes(md_text, md_text)
    if not quotes:
        print(f"  [PASS] {label}：无英文引文需要核对")
        return {"quotes": 0, "unverified": []}
    if not source_text:
        warns.append(f"{label} 有 {len(quotes)} 处英文引文，但未提供 --source 源文本，未核对")
        print(f"  [warn] {label} 有 {len(quotes)} 处英文引文，未提供 --source，跳过逐字核对")
        return {"quotes": len(quotes), "unverified": [], "skipped": True}
    hay = match_form(source_text)
    unverified = []
    checked = 0
    for q in quotes:
        needle = match_form(q)
        # 前置省略号 = 引文从原句中间开始：整段当作一个片段核对（不要按省略号拆，
        # 否则会拆出空片段或把首片段裁掉导致误报）
        if re.match(r"^\s*(?:\.\.\.|…)", q):
            fragments = [needle[:60]] if len(needle) >= 16 else []
        else:
            # 中间省略号 = 跳过了一部分："A ... B" 要求各段都能逐字找到
            fragments = [f.strip() for f in re.split(r"\.\.\.|…|\. \. \.", needle) if len(f.strip()) >= 12]
        if not fragments:
            continue
        checked += 1
        bad = []
        for frag in fragments:
            if frag in hay:
                continue
            hit = False
            for cut in (0.9, 0.75, 0.6):
                probe = frag[: max(12, int(len(frag) * cut))]
                if probe in hay:
                    hit = True
                    break
            if not hit:
                bad.append(frag)
        if bad:
            unverified.append(q[:90])
            if len(quotes) <= 12:
                print(f"         [诊断] 未命中片段：{bad[0][:70]!r}  引文段数={len(fragments)} 片段长={len(bad[0])}")
    if unverified:
        fails.append(f"{label} 有 {len(unverified)} 处引文在源文本中找不到：{unverified[0][:60]}…")
        print(f"  [FAIL] {label} 引文无法在源文本中核实（{len(unverified)}/{checked} 处）：")
        for u in unverified[:6]:
            print(f"         - {u}")
        if unverified and checked:
            # 全部对不上通常是"连引文都没抓对"（缺右引号、标题被当成引文等），
            # 把实际送检的段落打出来，避免使用者只看到结果不知道原因。
            print("         [诊断] 实际送检的引文段（前若干）：")
            for probe in quotes[:4]:
                print(f"           · {probe[:70]!r}")
    else:
        print(f"  [PASS] {label}：{checked} 处英文引文全部能在源文本中逐字找到")
    return {"quotes": len(quotes), "checked": checked, "unverified": unverified}


def check_images(label: str, md_text: str, docx_images: int | None, base_dir: str, fails: list, warns: list) -> dict:
    refs = IMG_MD_RE.findall(md_text)
    missing = []
    for ref in refs:
        p = ref if os.path.isabs(ref) else os.path.join(base_dir, ref)
        if not os.path.exists(p):
            missing.append(ref)
    if missing:
        fails.append(f"{label} 图片路径不存在：{', '.join(missing)}")
        print(f"  [FAIL] {label} 图片路径不存在：{', '.join(missing)}")
    elif refs:
        print(f"  [PASS] {label}：{len(refs)} 个图片引用均存在")
    if docx_images is not None and refs and docx_images < len(refs):
        warns.append(f"{label} markdown 引用 {len(refs)} 张图，docx 内仅嵌入 {docx_images} 张")
        print(f"  [warn] {label} markdown 引用 {len(refs)} 张图，docx 内嵌 {docx_images} 张")
    return {"refs": len(refs), "missing": missing, "docx_images": docx_images}


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="论文分析报告交付前校验")
    ap.add_argument("--md", nargs="+", required=True, help="markdown 报告（可含详细版、简略版、摘录版）")
    ap.add_argument("--detail-docx", default="", help="详细版 docx（用于图片数量核对）")
    ap.add_argument("--brief-docx", default="", help="简略版 docx（用于图片数量核对）")
    ap.add_argument("--notes-docx", default="", help="摘录版 docx（用于图片数量核对）")
    ap.add_argument("--brief-md", default="", help="显式指定简略版 markdown（默认按文件名含'简略'自动识别）")
    ap.add_argument("--source", default="", help="论文源文本（paper.txt 或抽取出的正文），用于引文核对")
    ap.add_argument("--json-out", default="", help="把结果写成 json 文件")
    args = ap.parse_args()

    fails: list[str] = []
    warns: list[str] = []
    report: dict = {"files": args.md, "checks": {}}

    source_text = read_text(args.source) if args.source and os.path.exists(args.source) else None
    if args.source and source_text is None:
        warns.append(f"--source 指定的文件不存在：{args.source}")
        print(f"  [warn] --source 文件不存在：{args.source}")

    detail_md = ""
    detail_md_raw = ""
    brief_md = ""
    notes_md = ""
    for path in args.md:
        text = read_text(path)
        name = os.path.basename(path)
        is_notes = ("摘录" in name) or ("notes" in name.lower())
        is_brief = (not is_notes) and (bool(args.brief_md and path == args.brief_md)
                                       or ("简略" in name) or ("brief" in name.lower()))
        is_compact = is_brief or is_notes
        label = ("摘录版 " if is_notes else ("简略版 " if is_brief else "详细版 ")) + name
        base_dir = os.path.dirname(os.path.abspath(path))
        docx_path = ((args.notes_docx if is_notes else args.brief_docx) if is_compact else args.detail_docx) or ""
        docx_images = None
        if docx_path and os.path.exists(docx_path):
            _t, docx_images, _p = docx_plain(docx_path)
        elif docx_path:
            warns.append(f"docx 不存在：{docx_path}")
            print(f"  [warn] docx 不存在：{docx_path}")

        print(f"\n== {label} ==")
        report["checks"][name] = {}
        report["checks"][name]["markers"] = check_markers(label, text, is_compact, fails, warns)
        report["checks"][name]["quotes"] = check_quotes(label, text, source_text, fails, warns)
        report["checks"][name]["images"] = check_images(label, text, docx_images, base_dir, fails, warns)

        if is_notes:
            notes_md = text
            table_count = _count_tables(text)
            report["checks"][name]["structure"] = check_notes_structure(label, text, table_count, fails, warns)
        elif is_brief:
            brief_md = text
            table_count = _count_tables(text)
            if False:
                try:
                    _m, blocks = parse_markdown(text)
                    table_count = sum(1 for t, _ in blocks if t == "table")
                except Exception:
                    table_count = 0
            if table_count == 0:
                table_count = len(re.findall(r"^\|\s*:?-{2,}", text, re.MULTILINE))
            report["checks"][name]["structure"] = check_brief_structure(label, text, table_count, fails, warns)
        else:
            detail_md = text
            # 数字一致性要扫**原始 markdown**（含代码块/Mermaid 源码）：
            # 有些数字只出现在结构图里，只看渲染后的块会误报"详细版没有"。
            detail_md_raw = text

    if detail_md and (brief_md or notes_md):
        print("\n== 版本间数字一致性（以详细版为准）==")
        detail_source = detail_md_raw or detail_md
        for label, doc in (("简略版", brief_md), ("摘录版", notes_md)):
            if not doc:
                continue
            report["checks"]["consistency-" + label] = check_consistency(detail_source, doc, fails)

    print("\n== 汇总 ==")
    for w in warns:
        print(f"  [warn] {w}")
    for f in fails:
        print(f"  [FAIL] {f}")
    verdict = "PASS" if not fails else "FAIL"
    print(f"  结论：{verdict}（FAIL {len(fails)} 项，WARN {len(warns)} 项）")
    report["verdict"] = verdict
    report["fails"] = fails
    report["warns"] = warns

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print(f"  明细已写入 {args.json_out}")
    print(json.dumps({"ok": verdict == "PASS", "fails": len(fails), "warns": len(warns)}, ensure_ascii=False))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
