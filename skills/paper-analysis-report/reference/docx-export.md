# Word 出稿与交付前校验（P8）

本 preset 自带一个工具 **`paper_docx`**（由 preset 目录里的 `plugins/docx-tool.js` 注册），
把 `reports/` 下的 markdown 编译成 Word 并跑校验。**优先用它**；它不可用时用等价的 shell 命令。渲染核心与 CLI 由**技能自带**（`skills/paper-analysis-report/tools/`：
`docx_core.py` + `make_docx.py` + `check_docx.py`），所以技能可以脱离预设单独分发。

工具与脚本都在 preset 目录里（`<preset>/plugins/tools/`），不需要安装任何东西。

---

## 1. 一次调用做完全部（三版）

```
paper_docx(
  detailMd = "<OUT>/reports/<slug>_详细版.md",
  briefMd  = "<OUT>/reports/<slug>_简略版.md",
  notesMd  = "<OUT>/reports/<slug>_摘录版.md",
  outDir   = "<OUT>/reports",
  source   = "<OUT>/analysis/source/paper.txt"
)
```

它会依次执行：

1. `make_docx --kind detail` —— 详细版：封面、自动目录域、页脚页码、表格样式、引文块、图题编号；
2. `make_docx --kind brief` —— 简略版：**无封面、无标题行、无目录**，只留页脚左侧"简略版"标签；
3. `make_docx --kind notes` —— 摘录版：同上但更紧凑，只有三节、无评级；
4. `check_docx` —— 交付前校验（见 §3）。

两版 docx 与它们的 markdown 同源、同目录，文件名只差"详细版/简略版"四个字。

### 排印规范（两版一致，改样式请改 `docx_export.py` 的 `DocStyle`）

| 项 | 规定 |
|---|---|
| 中文 | **宋体**，正文**小四（12 pt）** |
| 英文与数字 | **Times New Roman**（`w:ascii`/`w:hAnsi`），与中文同字号 |
| 行距 | **1.5 倍**（含表格单元格内文字） |
| 标题 | 黑体加粗（英文数字仍 Times New Roman），一级四号 14 pt、二级小四 12 pt，颜色深蓝 |
| 表格 | 五号 10.5 pt，表头底色 DCE3F0 |
| 代码块/引文 | 10–11.5 pt，等宽效果改用 Times New Roman（简略版不出现代码块） |
| 颜色 | **全文黑色**（含标题、加粗行内文字、引文标签、表题）：不使用主题蓝或灰。表格表头保留浅色底纹 `DCE3F0`（背景色，非文字色），引文块 `F2F4F8` |
| 页边距 | 详细版 2.5 cm，简略版 2.2 cm |

中英混排靠 `w:rFonts` 同时写 `w:eastAsia=宋体` 与 `w:ascii=Times New Roman`，Word 按字符脚本自动取字体，
不需要把中英文拆成不同 run。**注意**：`document.add_heading()` 会写入直接格式（Calibri Light + 主题色），
覆盖样式里的字体绑定——标题必须手工建段落并逐 run 绑字体（渲染器已这么做）。

## 2. 没有 subprocess 服务时的等价命令

工具会直接把命令打印出来，形如：

```powershell
python "<preset>\plugins\tools\docx_export.py" --input "<OUT>\reports\<slug>_详细版.md" --kind detail --out "<OUT>\reports" --pages
python "<preset>\plugins\tools\docx_export.py" --input "<OUT>\reports\<slug>_简略版.md" --kind brief  --out "<OUT>\reports" --pages
python "<preset>\plugins\tools\docx_check.py" --md "<OUT>\reports\<slug>_详细版.md" "<OUT>\reports\<slug>_简略版.md" --detail-docx "<OUT>\reports\<slug>_详细版.docx" --brief-docx "<OUT>\reports\<slug>_简略版.docx" --source "<OUT>\analysis\source\paper.txt"
```

注意：中文路径要用引号包住。`--pages` 只是尽力而为：它读 Windows 文档属性里缓存过的页数，
而刚生成的文档从未被 Word 打开过，因此**通常返回 null 或 1**，不要据此下结论。
（另一条路是让 Word 重排后导出 PDF 数页，但本机 Word 自动化对这种带自动域更新的文档会抛
"Word 未能引发事件"，自动化不可靠——所以**篇幅以汉字数为准**，见下表。）

## 3. 校验检查什么
| 检查 | 判据 | 不通过时怎么办 |
|---|---|---|
| **残留未解决标记** | `TODO` / `TBD` / `FIXME` / `???` 出现即 FAIL | 回 P2/P3 把该论断补完或删掉 |
| **证据链标记** | 详细版保留 `[待核实]`/`[推断]`/`[论文未给出]` 属正常（warn）；**简略版出现即 FAIL** | 从简略版删掉标记，整句改写成结论 |
| **简略版章节** | 需覆盖四个概念（各接受多种标题写法）：一句话结论 / 实验方法与结果 / 创新点 / 结论 | 按 `brief-template.md` 的六节补齐 |
| **简略版篇幅** | 正文汉字 ≤ 3400（2–3 页的经验上限；2000–3200 为舒适区） | 删段落，不要改字号：先砍"主要问题"里次要条目 |
| **简略版表格** | **纯文字为正常**（0 张表 PASS）；> 3 张表 warn | 把表格改写成段落——简略版要像手打报告 |
| **两版数字一致** | 简略版每个"数字+单位"（忽略空白与连字符差异）都必须出现在**详细版原始 markdown**里（含 Mermaid/代码块）。**单向检查**：详细版多出来的数字（如只写在工艺参数表里的 30 nm / 50 nm）不会被报错 | 改正数字，或把该结论补进详细版 |
| **引文可溯源** | **独立引文行**（`> ...`，无论有无引号）与纯英文行文里的 ≥40 字符引文，必须能在 `analysis/source/paper.txt` 中逐字找到 | 引文抄错就改；确实来自他文就改成转述 |
| **图片引用** | markdown 里的 `![](path)` 必须存在（相对 markdown 所在目录解析） | 补齐 `assets/` 里的截图，或删掉该图 |

**引文核对的前提**：`analysis/source/paper.txt` 必须是从 PDF 抽出的**原文**文本
（不要放自己翻译的版本），否则核对没有意义。抽取方法见 `workflow.md` §1。

### 引文核对的四条约定（踩过的坑，务必遵守）

1. **源文本用"去空白重建版"更好。** PDF 文本重建（pypdf 之类）常在词间丢空格、在换行处插连字符
   （`fur-ther`），有空格版还会把同一句按硬换行切断。核对时程序会把两侧都规范化
   （去空白 + 去换行连字符 + 小写），因此**用去空白重建文本当 `--source` 最稳**
   （本 preset 分析过的那篇就是 `paper.txt` = 去空白版；有空格原版另存为 `paper_spaced_raw.txt` 备查）。
   源目录里放一份 `README-来源说明.txt` 写明两者关系。
2. **英文引文要写在独立引文行里**（markdown 的 `> ...`）。独立引文行**无论有没有写引号都会核对**；
   而**中文行文里**用引号做强调的短语（论文标题、"降 90%" 这类说法）不会被当成引文——
   否则每篇报告都会误报一堆"引文找不到"。
3. **省略号**：`"...in order to ..."` 这种前置省略号表示引文从原句中间开始，按一段长片段核对；
   `"A ... B"` 这种中间省略号会**逐段**核对，每段都必须能逐字找到。
4. **引文必须是逐字照抄**。校验器只接受逐字（允许空白/连字符/大小写差异），
   一旦你把引用改写成自己的话，它会如实报 FAIL——这是它的价值，不要为了过检而删掉引文核对。

## 4. markdown 支持的写法

`docx_export.py` 是轻量渲染器，支持：

- 开头一行元数据：`<!-- meta: {"title": "...", "subtitle": "...", "author": "...", "date": "...", "paper": "...", "source": "..."} -->`
  （必填 `title`；`paper` 里可用 `\n` 换行；`date` 用 `YYYY-MM-DD`）
- 标题 `#`~`####`（1–4 级，映射到 Word 的 Heading 1–4，用于生成目录）
- 段落、`**粗体**`、`*斜体*`、`` `等宽` ``、`~~删除线~~`
- 有序/无序列表（两级缩进）
- 表格（标准 markdown 管道表；表头自动加底色）
- 引文 `> ...`（渲染为带底色的引文块，用于放英文原文）
- 代码块 ```` ``` ```` （等宽小字号，用于参数表）
- 图片 `![题注](assets/xxx.png)`（居中嵌入并自动编号"图 N"）
- 分隔线 `---`

**不支持**：Mermaid 图（Word 里不会渲染成图）、脚注、数学公式排版。
需要图示时：在 markdown 里留一行提示，把 Mermaid 源码放在代码块里（给读者照抄），
或者用工具把图画成 PNG 放进 `assets/` 再按图片嵌入。

## 5. 常见错误

| 现象 | 原因与处理 |
|---|---|
| `无法写入 xxx.docx：文件被占用` | 该 docx 正在 Word/预览窗格里打开；关掉后重跑（脚本已自带重试） |
| 简略版报 FAIL 且说"超出 2–3 页" | 精简内容，不要靠改字号；字号已在 `docx_export.py` 的 `DocStyle.for_kind('brief')` 里定好 |
| 引文全部报 FAIL | `--source` 指向的文件不是原文（例如指向了翻译稿），或路径写错 |
| 目录在 Word 里是空的 | 打开文档时 Word 会自动刷新域；若没刷新，Ctrl+A 再按 F9 |
| 页数显示为 null | 该文件从未被 Word 打开过，Windows 文档属性里还没有缓存页数；不影响交付 |
| 表格太宽溢出页面 | 拆成两张表，或把长文本列改成短标签 + 表下注释 |

## 6. 依赖与降级

- 主路径：Python + `python-docx`（本机 Python 3.13 / python-docx 1.2.0 可用）。
  缺失时会提示 `python-docx 未安装。请先执行：pip install python-docx`。
- 没有 `python-docx` 且无法联网时：把 markdown 交给用户，并说明需要先装依赖；
  **不要**用 Word COM 手搓排版（本 preset 生成的文件带 `w:updateFields`，
  Word COM 打开会抛 "Word 未能引发事件"，页数统计因此走 Windows 文档属性而不是 Word）。
- 脚本路径固定为 `<preset>/plugins/tools/`；不要复制到其它位置后再调用。
