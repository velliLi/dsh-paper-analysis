# dsh-paper-analysis

**DSH（DeepSeek Harness）的「论文分析」Agent 预设 + 技能**：把一篇论文变成两版可直接交给导师的
Word 报告——**详细版**（完整证据链）与 **简略版**（2–3 页整段文字，手打报告风格）。

> **发布前请替换占位符**：本仓库里的 REPLACE_WITH_YOUR_GITHUB_USER、REPLACE_WITH_YOUR_NAME、REPLACE_WITH_ABSOLUTE_PATH_TO_THIS_PACKAGE 需要换成你自己的值（分别在 README.md、package.json、cordis.patch.yml）。发布后请删除本提示。

面向集成电路 / 微电子 / EDA 方向，但流程与学科无关：换掉一份参考文件即可用于其它方向。

---

## 装法一：一条命令（不需要 DSH 插件机制）

```bash
npx dsh-paper-analysis
```

它会：定位预设根（读 `DSH_HOME`，否则 `~/.dsh`）→ 备份同名旧预设 → 把预设装进去 →
体检 Python 与 python-docx → 打印验证步骤。

```bash
npx dsh-paper-analysis --check    # 只体检，不写文件
npx dsh-paper-analysis --force    # 覆盖（不备份旧目录）
```

也可以手动装：把本包目录整体复制成 `~/.dsh/.agent-presets/paper-analysis/`（root 本身就是预设目录）。

## 装法二：作为 DSH 插件（bundle）

```bash
dsh plugin --profile web add dsh-paper-analysis
```

这条命令是 pnpm 转发器，会把本包装进该 profile 并写进 `dsh.profile.bundles`。
本包已声明 `dsh.bundle.patch`，指向随包的 `cordis.patch.yml`——它把本包目录注册成
agent-presets roster 的一个根，于是「论文分析模式」直接出现在预设选择器里。

**装之前**：打开 `cordis.patch.yml`，把 `REPLACE_WITH_ABSOLUTE_PATH_TO_THIS_PACKAGE`
换成本包的实际安装路径（例如
`C:/Users/<你>/AppData/Roaming/npm/node_modules/dsh-paper-analysis`），路径里不要有中文或空格。

| profile 里有没有 `agent-presets` 行 | 用哪个文件 |
|---|---|
| 有（如 `web`，该行由 `@deepseek-ai/dsh-web-app` 提供） | `cordis.patch.yml`（默认） |
| 没有（如内置 `default`） | 把 `cordis.insert.patch.yml` 复制成 `cordis.patch.yml` 再用 |

> **行为变化（重要）**：补丁会替换 `agent-presets` 的整段 config，因此 `default` 被设为
> `paper-analysis`——装完后**新会话默认进入「论文分析模式」**。要改回去：编辑该补丁的 `default`
> 字段为别的预设 id，或在设置文档的 agent-preset 段里覆盖（该段的 base 就是这里的 `default`）。

**两个可回退的替代做法**（不想动 profile 时）：

```bash
# ① 只跑 npx 安装（推荐先用这条）
npx dsh-paper-analysis
# ② 或用一个 --patch 覆盖层，完全不改 profile：
dsh --profile web --patch ./cordis.patch.yml
```

卸载：`dsh plugin --profile web remove dsh-paper-analysis`，然后删掉
`~/.dsh/.agent-presets/paper-analysis`（若用过 npx 安装）。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| DSH | 已安装并能启动 `dsh` |
| Python 3.8+ | 生成 Word |
| `python-docx` | `pip install python-docx` |
| Word / WPS | 可选，仅看目录与页码时需要 |

不需要 pandoc、不需要 LibreOffice。找不到 Python 时设
`PAPER_ANALYSIS_PYTHON=<python.exe 绝对路径>` 后重开 DSH。

---

## 用法

1. 新开一个 DSH 会话，预设选择器选 **论文分析模式**；
2. 说一句：`分析这篇论文：<PDF 路径 或 arXiv 链接>`；
3. 产物落在你的工作区：

```
<工作区>/PaperAnalysis/<日期>_<短标题>/
├── reports/     两版 docx + 同源 md（拷给导师的就是这里）
├── analysis/    过程档案 00-context…60-method、check.json、source/paper.txt
├── assets/      你从论文里截的图
└── sources.md
```

报告排印：中文宋体小四、英文 Times New Roman、1.5 倍行距、全文黑色。
出稿时自动校验：章节完整、篇幅（简略版 2–3 页）、**两版数字一致**、
**英文引文能否在论文原文中逐字找到**、图片引用是否存在。

---

## 常见问题

| 现象 | 处理 |
|---|---|
| 选择器里没有「论文分析模式」 | 层级错了：必须是 `<预设根>\paper-analysis\agent.cordis.yml` |
| 会话里没有 `paper_docx` 工具 | 预设挂载失败；用「创造模式」会话执行 `await ctx.agentPresets.standingKeyFor('paper-analysis')` 看报错 |
| 提示找不到 Python / python-docx | 按上面「依赖」一节处理 |
| 引文核对全报失败 | `--source` 指的不是论文原文，或 PDF 无文本层（扫描件） |
| 简略版超 3 页 | 删段落，不要改字号（上限按汉字数约 3400 字判定） |

## 卸载

```bash
rm -rf ~/.dsh/.agent-presets/paper-analysis     # Windows: Remove-Item -Recurse -Force
```

---

## 给发布者（维护本包）

- 包根即预设目录：`agent.cordis.yml` / `preset.yml` / `plugins/` / `skills/` / `source/`
- 改完预设后重新同步：把 `~/.dsh/.agent-presets/paper-analysis/` 的内容覆盖到本包根，
  保留 `bin/`、`package.json`、`README.md`
- 发布前自测：
  ```bash
  node bin/install.js --check        # 体检模式
  npm pack --dry-run                 # 看打包清单（files 白名单）
  ```
- 发布：`npm publish --access public`（非 scope 包默认就是 public）
- 若要同时支持 `dsh plugin add`，补一个 bundle 声明：让包导出一个 Cordis 插件，
  并声明把 `agent-presets/` 供给 roster 的 config 树（`scanRoster: true`）。
  参考你本机已装插件在 `~/.dsh/profiles/web/package.json` 里的 `dsh.profile.bundles` 写法。

MIT License.
