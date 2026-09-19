# paper-analysis-report（可迁移技能）

把一篇论文的分析写成 **三份 Word**：详细版 / 简略版 / 摘录版。
本技能**自带全部脚本**，不依赖任何特定 Agent 预设——任何能读文件、能跑命令的 Agent（或你自己手动跑）都能用。

```
paper-analysis-report/
├── SKILL.md                 ← 流程与契约（铁律、9 阶段、三版交付规则、目录约定）
├── reference/               ← 10 个按需加载的参考文件（模板、评分口径、学科口径、自检清单…）
└── tools/
    ├── check_env.py         ← 先跑这个：体检依赖与文件完整性
    ├── docx_core.py         ← 渲染核心（markdown → Word，三版样式）
    ├── make_docx.py         ← 出稿 CLI（--kind detail|brief|notes，或 --auto 自动推断）
    └── check_docx.py        ← 交付前校验（章节/篇幅/评级词/引文溯源/数字一致性）
```

## 依赖

只要 **Python 3.8+** 和 **python-docx**：

```bash
pip install python-docx
python tools/check_env.py     # 体检；退出码 0 表示可用
```

不需要 DSH、不需要 pandoc、不需要 LibreOffice；只有想看目录页码时才需要 Word/WPS。

## 怎么用

```bash
# 1) 出稿：三份 markdown → 三份 docx（--auto 按文档头 version_label 自动判断版本）
python tools/make_docx.py --auto \
  --input reports/xxx_详细版.md reports/xxx_简略版.md reports/xxx_摘录版.md \
  --out reports

# 2) 校验（PASS 才交付）
python tools/check_docx.py \
  --md reports/xxx_详细版.md reports/xxx_简略版.md reports/xxx_摘录版.md \
  --detail-docx reports/xxx_详细版.docx \
  --brief-docx  reports/xxx_简略版.docx \
  --notes-docx  reports/xxx_摘录版.docx \
  --source analysis/source/paper.txt
```

三份 markdown 必须有文档头（`make_docx.py --auto` 靠它判断版本）：

```html
<!-- meta: {"title": "…", "subtitle": "简略版", "author": "…", "date": "YYYY-MM-DD",
           "paper": "标题\n期刊 年份", "source": "简略版 · 论文分析模式", "version_label": "brief"} -->
```
`version_label` 取 `detail` / `brief` / `notes`；也可用 `--kind` 显式指定。

## 三版各自的要求

| 版本 | 要求 |
|---|---|
| 详细版 `detail` | 完整证据链；可放表格、图、引文块；允许保留 `[推断]`/`[论文未给出]` 等留痕标记 |
| 简略版 `brief` | 2–3 页**整段文字**（不摆表格），带判断（值不值得跟、从哪切入、最大风险）；不写标题 |
| 摘录版 `notes` | 只有三节：**论文在做什么 / 创新点 / 该论文提供的思路**；**不评级、不判断、不建议** |

摘录版的"不评级"由校验器强制：出现 `A/B/C/D 级`、`值得跟进`、`我的结论`、`我认为`、`局限`、`风险`、`复现难度` 等用语即 **FAIL**。

## 排印（三版一致，写死在渲染器里）

中文宋体、正文小四（12 pt）；英文与数字 Times New Roman；1.5 倍行距；标题黑体加粗；**全文黑色**。
表格五号、表头浅底纹。要改就改 `docx_core.py` 的 `DocStyle`。

## 校验器检查什么

残留未解决标记（`TODO` 等）· 紧凑版是否混入留痕标记 · 简略/摘录版必备章节与篇幅 ·
**摘录版是否混入评级用语** · **三版数字是否都能在详细版中找到** ·
**英文引文能否在论文原文中逐字找到**（去空白、去换行连字符、BOM 容错；省略号引文分段核对）· 图片引用是否存在。

## 常见问题

| 现象 | 处理 |
|---|---|
| 提示 `python-docx 未安装` | `pip install python-docx` |
| 引文全部报"找不到" | `--source` 指的不是论文原文，或 PDF 无文本层（扫描件）。用 `pypdf` 抽正文，或把正文粘贴成 `.txt` |
| 简略版超篇幅 | 删段落，不要改字号；上限按汉字数判定（简略版 3400、摘录版 2000） |
| 页数为 1 或读不到 | 已知限制：页数取自 Windows 缓存属性，刚生成的文件没有该属性；**篇幅以汉字数为准** |
| `无法写入 xxx.docx` | 该文件正被 Word/预览占用；关闭后重跑（脚本自带重试） |

## 独立分发

本技能目录**自成一体**：把 `paper-analysis-report/` 整个拷给别人即可。
如果对方用 DSH，放到 `<预设目录>/skills/`（会被 preset 的 `customSkillDirs` 自动发现），
或放到 `~/.dsh/skills/` 作为用户级技能。

MIT License.
