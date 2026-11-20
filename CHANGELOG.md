# Changelog

## 1.2.0 — 2026-11-20

- **适配 DSH 0.2.x 的 preset 机制**：新版（`dsh-agent-preset-registry` + `dsh-agent-preset`）不再扫描 `$DSH_HOME/.agent-presets/<id>/`，preset 必须是一条 `@deepseek-ai/dsh-agent-preset` 声明行。`cordis.patch.yml` 因此从「往 `agent-presets.roots` 塞目录」改为 `insert` 一条声明；0.1.x 用的旧写法保留在 `cordis.insert.patch.yml`。
- **修复启动报错 `unknown prompt variable "{{cwd}}"`**：0.2.x 只注册 `provider` / `model` 两个插值变量，persona 里出现未注册变量会在组合期直接抛错。persona 首行改用 `{{model}}`，工作目录改由运行时上下文的 `Current working directory` 提供。
- **版本由用户选**：新增 `tool-ask-user` 行，开工第一个动作是用 `ask_user_question`（`multi_select`）让用户勾选本次交付哪几版；`paper_docx` 的 `modes` 参数只编译被勾选的版本，未勾选的不写、不编译、不进 `reports/`。
- **`paper_docx` 插件重写为 `plugins/paper-report-docx-2.js`**：渲染与校验脚本改由技能自带（`skills/paper-analysis-report/tools/`），预设不再留重复副本，技能可独立分发。
- **新增 `tools/extract_pdf.py`**：PyMuPDF 抽正文，自动展开连字（ﬁ→fi）、去断词，输出 UTF-8/LF，供 `check_docx.py` 的英文引文逐字核对；控制台只打印统计，避免 GBK 控制台 `UnicodeEncodeError`。
- **依赖补充**：`extract_pdf.py` 需要 `pip install PyMuPDF`（Windows 纯 wheel，不需要 poppler）。
- 仓库 `package.json` 中损坏成 `??????` 的中文 description / keywords 已修复。

## 1.1.0 — 2026-09-17

- **三版输出**：新增摘录版（只有三节：论文在做什么 / 创新点 / 该论文提供的思路），**不含任何评级与判断**；校验器在摘录版出现评级用语时报 FAIL。
- **每篇文献独立文件夹**：PaperAnalysis/<日期>_<短标题>/ 自带 reports + analysis + assets + sources.md，可整包拷走。
- **工具脚本随技能分发**：skills/paper-analysis-report/tools/（docx_core / make_docx / check_docx），技能可独立给别人用；--auto 按文档头推断版本。

## 1.0.0 — 2026-09-17

首个可分发的版本。

**预设与技能**
- Agent 预设 `paper-analysis`（选择器显示「论文分析模式」），由 `standard` 预设派生；persona 换成论文分析助手（四条铁律：零编造 / 证据优先 / 判断分级 / 版本由用户定）。
- 学科口径按集成电路工程：功耗、时序、面积、精度必须带全条件（工艺节点、Vdd、频率、工艺角、是否 post-layout）；绝不把 RTL/算法级结果说成实测。
- 技能 `paper-analysis-report`：P0 立项 → P8 出稿的阶段流水线，10 个参考文件按需加载。
- 创新点评估口径：三条基线（自报最近邻 / 同期同类 / 经典母题）+ A/B/C/D 分级 + 降级触发器。
- 对抗验证用 `workflow` 扇出复现者 / 历史学家 / 审稿人三个角色。

**报告交付**
- 两版 Word 同目录交付：`reports/<slug>_详细版.docx`（完整证据链）与 `reports/<slug>_简略版.docx`（2–3 页整段文字，手打报告风格，无标题、无表格）。
- 中间件与最终报告分离：过程档案全部在 `analysis/`，`reports/` 只放报告文件。
- 排版：中文宋体小四、英文 Times New Roman、1.5 倍行距、全文黑色。

**出稿工具**
- `paper_docx` 工具（预设自带插件）：一次调用完成版本编译 + 交付前校验。
- `check_docx.py` 校验：残留未解决标记、紧凑版章节与篇幅、**两版数字一致性**、**英文引文能否在论文原文中逐字找到**（去空白、去换行连字符、BOM 容错）、图片引用存在性。
- 便携性：Python 解释器按 `PAPER_ANALYSIS_PYTHON` → PATH → 常见安装位置（含 conda）依次探测。

**安装**
- `npx dsh-paper-analysis`：定位预设根、备份同名旧预设、复制、体检 Python 与 python-docx。
- 同时声明 `dsh.bundle`，供 DSH 插件机制装载（bundle 补丁见 `cordis.patch.yml`）。

**已知限制**
- 页数统计不可靠：`--pages` 读 Windows 缓存的文档属性，刚生成的文件读不到；篇幅以正文字数为准（简略版舒适区 2000–2200 字）。
- 该版本仅在 Windows + Python 3.13 + python-docx 1.2.0 上实测过；其他平台的 Word 生成路径未实测。
