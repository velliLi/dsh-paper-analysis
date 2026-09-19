# dsh-paper-analysis

**给 DSH（DeepSeek Harness）用的「论文分析」Agent 预设 + 可独立运行的技能**：
把一篇论文变成**三份可直接交付的 Word**——详细版、简略版、摘录版。

面向集成电路 / 微电子 / EDA 方向，但流程与学科无关：换掉一份参考文件即可用于其它方向。
技能部分**不依赖 DSH**：任何能跑命令的环境（只要有 Python）都能用。

---

## 三份产出长什么样

| 版本 | 篇幅 | 内容 | 用途 |
|---|---|---|---|
| **详细版** | 不限（8–20 页） | 完整证据链：问题定义矩阵、方法重构（含结构图源码）、创新点逐条论证与可证伪表述、实验全表、局限清单、复现路线、待问作者的问题、参考文献 | 自己吃透、开题铺垫、导师细读 |
| **简略版** | 2–3 页**整段文字** | 手打报告风格，**带判断**：值不值得跟、从哪一点切入、最大风险是什么。不摆表格、不加标题 | 组会汇报、周报、快速筛选 |
| **摘录版** | 最小（≤2000 汉字） | **只有三节**：论文在做什么 / 创新点 / 该论文提供的思路。**不评级、不判断、不建议** | 文献卡片、跨方向交流、快速了解一篇论文 |

摘录版的"不评级"由**校验器强制**：出现 `A/B/C/D 级`、`值得跟进`、`我的结论`、`我认为`、`局限`、`风险`、`复现难度` 等用语即报 FAIL。

**排印**（三版一致）：中文宋体、正文小四（12 pt）；英文与数字 Times New Roman；1.5 倍行距；标题黑体加粗；全文黑色。

**目录约定**（每篇文献一个独立文件夹，可整包拷走）：

```
PaperAnalysis/
└── 2026-09-17_configurable-adder-tree/
    ├── reports/     ← 交付物：三版 md + 三版 docx
    ├── analysis/    ← 过程档案：00-context … 60-method、check.json、source/paper.txt
    ├── assets/      ← 论文图表截图（会内嵌进详细版）
    └── sources.md   ← 引用信息与检索链接
```

---

## 安装

### 方式一：从 GitHub 装成 DSH 插件（推荐，一条命令）

```bash
dsh plugin --profile web add github:velliLi/dsh-paper-analysis
```

`dsh plugin` 会把参数原样转发给 profile 目录里的 pnpm，而 pnpm 原生支持
`github:owner/repo`、`git+https://…`、`owner/repo#tag` 等写法。本包**没有**
`prepare`/`postinstall` 脚本，因此**不需要**在 profile 的 `pnpm-workspace.yaml` 里配 `allowBuilds`。

本包已声明 `dsh.bundle.patch` → `cordis.patch.yml`，它把本包目录注册成 agent-presets roster 的一个根，
于是「论文分析模式」直接出现在预设选择器里。补丁里的路径用**表达式**求值
（`dshHomePath('.agent-presets')` 与 `import.meta.dirname`），**不需要手改任何路径**。

| profile 里有没有 `agent-presets` 行 | 用哪个文件 |
|---|---|
| 有（如 `web`，该行由 `@deepseek-ai/dsh-web-app` 提供） | `cordis.patch.yml`（默认） |
| 没有（如内置 `default`） | 把 `cordis.insert.patch.yml` 复制成 `cordis.patch.yml` 再用 |

> **行为变化（重要）**：补丁替换的是 `agent-presets` 的整段 config，因此 `default` 被设为
> `paper-analysis`——装完后**新会话默认进入「论文分析模式」**。要改回去：编辑该补丁的 `default`
> 字段为别的预设 id，或在设置文档的 agent-preset 段里覆盖（该段的 base 就是这里的 `default`）。

不想动 profile 时，可以只用一次性覆盖层（零副作用，改完即弃）：

```bash
git clone https://github.com/velliLi/dsh-paper-analysis.git
dsh --profile web --patch ./dsh-paper-analysis/cordis.patch.yml
```

卸载：`dsh plugin --profile web remove dsh-paper-analysis`；若用过手动放置，再删掉
`~/.dsh/.agent-presets/paper-analysis` 目录。

### 方式二：手动放置预设（不需要 pnpm 访问 GitHub）

```bash
git clone https://github.com/velliLi/dsh-paper-analysis.git
cp -r dsh-paper-analysis ~/.dsh/.agent-presets/paper-analysis
# 若设过 DSH_HOME：目标改到 $DSH_HOME/.agent-presets/paper-analysis
```

Windows 用资源管理器把仓库内容复制成 `%USERPROFILE%\.dsh\.agent-presets\paper-analysis\` 即可。
**仓库根即预设根**，所以复制后目录里应当直接能看到 `agent.cordis.yml`。

装完**重开一个 DSH 会话**，预设选择器里选「论文分析模式」，然后说：`分析这篇论文：<PDF 路径>`。

### 方式三：只用技能（不需要 DSH）

```bash
git clone https://github.com/velliLi/dsh-paper-analysis.git
pip install python-docx
python dsh-paper-analysis/skills/paper-analysis-report/tools/check_env.py   # 体检：退出码 0 表示可用
```

把 `skills/paper-analysis-report/` 整个目录拷到下面任一位置，DSH 会话就会自动加载它：

| 位置 | 作用范围 |
|---|---|
| `~/.dsh/skills/paper-analysis-report/` | 所有会话（用户级） |
| `<项目>/.dsh/skills/paper-analysis-report/` | 仅该项目 |
| `<预设目录>/skills/paper-analysis-report/` | 仅该预设 |

#### 完全手动使用（不用 Agent）

```bash
# 1) 出稿：三份 markdown → 三份 docx（--auto 按文档头 version_label 自动判断版本）
python skills/paper-analysis-report/tools/make_docx.py --auto \
  --input reports/xxx_详细版.md reports/xxx_简略版.md reports/xxx_摘录版.md \
  --out reports

# 2) 交付前校验（PASS 才交付）
python skills/paper-analysis-report/tools/check_docx.py \
  --md reports/xxx_详细版.md reports/xxx_简略版.md reports/xxx_摘录版.md \
  --detail-docx reports/xxx_详细版.docx \
  --brief-docx  reports/xxx_简略版.docx \
  --notes-docx  reports/xxx_摘录版.docx \
  --source analysis/source/paper.txt
```

三份 markdown 需要文档头（`--auto` 靠它判断版本）：

```html
<!-- meta: {"title": "…", "subtitle": "简略版", "author": "…", "date": "YYYY-MM-DD",
           "paper": "标题\n期刊 年份", "source": "简略版 · 论文分析模式", "version_label": "brief"} -->
```
`version_label` 取 `detail` / `brief` / `notes`。也可以 `--kind detail|brief|notes` 显式指定。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| DSH | 方式一 / 方式二需要；方式三不需要 |
| **Python 3.8+** | 生成 Word |
| **python-docx** | `pip install python-docx` |
| Word / WPS | 可选，仅看目录与页码时需要 |
| pypdf（可选） | 抽取 PDF 正文用于引文逐字核对 |

不需要 pandoc、不需要 LibreOffice。

---

## 仓库结构

```
.
├── agent.cordis.yml              DSH 预设组合（唯一改行为的入口）
├── preset.yml                    选择器里显示的名称与描述
├── cordis.patch.yml              DSH 插件（bundle）补丁：把本包注册成预设根
├── cordis.insert.patch.yml       同上，用于组合树里还没有 agent-presets 行的 profile
├── bin/install.js                本地安装器（把预设复制到预设根，供 fork/二次分发用）
├── plugins/docx-tool.js          注册 paper_docx 工具（调用技能脚本）
├── skills/paper-analysis-report/
│   ├── SKILL.md                  流程与契约（铁律、9 阶段、三版交付规则、目录约定）
│   ├── README.md                 技能独立使用说明
│   ├── reference/                10 个按需加载的参考文件（模板/评分口径/学科口径/自检清单）
│   └── tools/                    docx_core.py / make_docx.py / check_docx.py / check_env.py
├── install.ps1                   手动安装脚本（Windows）
├── pack.ps1                      重打包脚本（维护者用）
└── source/                       组合的可读副本 + 维护说明与变更记录
```

---

## 校验器检查什么

- 残留未解决标记（`TODO` / `TBD` / `FIXME` / `???`）
- 紧凑版（简略/摘录）是否混入 `[推断]` / `[论文未给出]` 等留痕标记
- 简略版与摘录版的必备章节与篇幅（简略版 ≤3400 汉字、摘录版 ≤2000 汉字）
- **摘录版是否混入评级/判断用语**（出现即 FAIL）
- **三版数字是否都能在详细版中找到**
- **英文引文能否在论文原文中逐字找到**（去空白、去换行连字符、BOM 容错；省略号引文分段核对）
- 图片引用是否存在

---

## 常见问题

| 现象 | 处理 |
|---|---|
| 选择器里没有「论文分析模式」 | 目录层级错了：必须是 `<预设根>/paper-analysis/agent.cordis.yml` |
| 会话里没有 `paper_docx` 工具 | 预设挂载失败。用「创造模式」开会话执行 `await ctx.agentPresets.standingKeyFor('paper-analysis')` 看报错 |
| `dsh plugin add` 报找不到包 | 内网无法访问 GitHub；改用方式二手动放置 |
| 启动时报 `import.meta` 相关错误 | `cordis.patch.yml` 里第二条 root 求值失败；把它换成你的实际安装路径，或删掉该条（第一条用户预设根通常已够用） |
| 提示找不到 Python | 设环境变量 `PAPER_ANALYSIS_PYTHON=<python.exe 绝对路径>` 后重开 DSH |
| 提示 `python-docx 未安装` | `pip install python-docx` |
| 引文全部报"找不到" | `--source` 指的不是论文原文，或 PDF 无文本层（扫描件）；换成自备正文文本 |
| 简略版超篇幅 | 删段落，不要改字号；上限按汉字数判定 |
| 页数显示为 1 或读不到 | 已知限制：页数取自 Windows 缓存属性，刚生成的文件没有该属性；**篇幅以汉字数为准** |

---

## 已知限制

- 仅在 Windows + Python 3.13 + python-docx 1.2.0 上实测过；其它平台未经实测。
- 页数统计不可靠（见上），篇幅以汉字数判定。
- 摘录版强制要有第三节（该论文提供的思路），只写两节会校验失败。
- **本包尚未发布到 npm**，所以没有 `npx dsh-paper-analysis` 这条安装方式；
  上面的三种方式都已可直接使用。

## 许可

MIT，见 [LICENSE](LICENSE)。
