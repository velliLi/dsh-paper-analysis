# paper-analysis preset — 维护说明

本 preset 由 `standard` 复制而来，是**本地 authored preset**（`trust: user`），
位于 `${DSH_HOME}/.agent-presets/paper-analysis/`。
部署升级不会覆盖它，但也不会替你修它——改完必须自己验证。

## 目录

```
paper-analysis/
├── agent.cordis.yml                    # 组合本体（改动只在这一个文件）
├── preset.yml                          # 选择器里显示的元数据
├── skills/
│   └── paper-analysis-report/          # 随 preset 分发的技能
│       ├── SKILL.md                    # 路由器：铁律 + 9 阶段流水线 + 两版交付 + 产物约定
│       └── reference/                  # 操作层（按需加载，不占常驻上下文）
│           ├── workflow.md             # P0–P8 逐步动作、判据与 Gate
│           ├── report-template.md      # 详细版模板（含 docx meta 头）
│           ├── brief-template.md       # 简略版模板（2–3 页）
│           ├── docx-export.md          # Word 出稿与校验规则、常见错误
│           ├── novelty-rubric.md       # 三条基线 + A/B/C/D 分级与触发器
│           ├── ic-domain-notes.md      # 集成电路指标口径与子方向重点
│           ├── subagent-prompts.md     # 子代理/对抗验证提示词模板
│           ├── compare-template.md     # 多篇对比矩阵模板
│           └── checklist.md            # 交付前自检清单
├── plugins/
│   ├── docx-tool.js                    # preset 自带的 Cordis 插件行：注册 paper_docx 工具
│   ├── package.json                    # 标记该目录为 ESM 包
│   └── tools/
│       ├── docx_export.py              # markdown → docx 渲染器（详细版 / 简略版）
│       └── docx_check.py               # 交付前校验器
└── source/                             # 本 preset 的可读副本（便于对照与重建）
    ├── agent.cordis.yml
    ├── preset.yml
    └── README.md
```

## 与 `standard` 的差异（只有四处）

1. `persona` 换成论文分析助手：三条铁律（零编造 / 证据优先 / 判断分级）、
   学科口径要求、必须落盘中间件再组装两版报告。
2. 删除 `planning`（plan mode）与 `command-goal` / `tool-goal` 两族行；
   `tool-ralph` 保留但 `disabled: true`。
3. `skill-filesystem` 增加 `customSkillDirs`，用 preset 自身目录解析 `skills/`
   （`baseUrl`），使技能随 preset 一起复制/移动/删除。
4. 新增一行 `preset-plugins`（`name: './plugins/docx-tool.js'`），把 preset 目录里的
   ESM 模块挂进来，注册 `paper_docx` 工具（Word 出稿 + 校验）。

另外把 `tool-result-pruner` 的阈值从 `thresholdChars: 8192` 收紧到 `6144`
（head 3072 / tail 1024），因为论文分析的单条工具结果（整节正文、大表格）更长。

## 两个必须知道的限制

- **preset 自带的插件模块不能 `import` harness 包**：用户 preset 根目录向上走不到部署的
  `node_modules`，`import '@deepseek-ai/dsh-tools'` 会以
  `Cannot find package ... imported from ...` 让整个 preset 挂载失败。
  因此 `plugins/docx-tool.js` 直接按 `ctx.tools.register` 的契约手写工具定义
  （`parameters` 用原始 JSON Schema，registry 原样接受），不经过 `defineTool`。
  同理，`harness` 这个符号只在动态插件沙箱里存在，preset 模块里用不到。
- **preset 加载器按 URL 缓存模块**：改完 `plugins/*.js` 后，同名的文件可能仍执行旧代码
  （报错信息会指向旧内容，令人困惑）。验证时要**换文件名**再挂载一次
  （例：`paper-docx.js` → `docx-tool.js`），并同步改 `agent.cordis.yml` 里的行。
  行里的路径必须是**文件**而不是目录：`./plugins` 会报
  `names a plugin that cannot be resolved: ./plugins`。

## 改动后的验证（三步）

1. **组合必须能挂载**（缺包、配置非法、某行永不激活、把服务发布进 root realm，
   这四类错误都会在这一步暴露）。用 `cordis` 预设开一个会话，挂一个临时 Host 插件
   注入 `agentPresets`，注册一个工具调用：

   ```
   await ctx.agentPresets.standingKeyFor('paper-analysis')   // 正常返回 = 挂载成功
   ```

2. **技能 frontmatter 必须合法**（加载器要求 `name` + `description`，
   `name` 形如 `lower-case-words`，且**拒绝**旧字段 `disableModelInvocation` /
   `modelInvocable` / `userInvocable`），且 SKILL.md 正文引用到的 `reference/*.md`
   必须真的存在。可用一次性 node 脚本遍历 `skills/` 校验（先读 frontmatter，再逐个
   `statSync` 引用文件）。

3. **出稿链路要真跑一次**（改过 `tools/*.py` 之后尤其必要）：

   ```
   python plugins/tools/docx_export.py --input <某个.md> --kind brief  --out <dir> --pages
   python plugins/tools/docx_export.py --input <某个.md> --kind detail --out <dir> --pages
   python plugins/tools/docx_check.py  --md <详细.md> <简略.md> --detail-docx <详细.docx> --brief-docx <简略.docx> --source <paper.txt>
   ```

   期望：两个 docx 生成成功、`--pages` 报出页数（简略版应 ≤3 页）、校验以
   `{"ok": true, ...}` 结束。**故意写一条不存在的引文**，校验必须报 FAIL——那才是它在工作。

4. **真实会话确认**：只有用这个 preset 真开一个会话，才能看到最终工具表
   （应包含 `paper_docx`、`skill`、`subagent`、`workflow`、`pwsh`）与技能目录。

## 注意

- 行会**发布服务**时必须待在带 `isolate` realm 的 group 里；只消费宿主服务的行
  必须留在 realm 外。改行之前先确认该行是提供者还是消费者。
- 绝不要为了"顺手修一下"去改部署自带的 `agent-presets` 目录。
- `plugins/tools/*.py` 依赖 `python-docx`（`pip install python-docx`）。
  页数统计走 Windows 文档属性；**不要**改用 Word COM 统计页数——本 preset 生成的文件带
  `w:updateFields`，Word COM 打开会抛 "Word 未能引发事件"。

## 变更记录

### 1.1.0
- **三版输出**：新增摘录版（`_摘录版.docx`）——只有"论文在做什么 / 创新点 / 该论文提供的思路"三节，
  **不含任何评级与判断**；校验器会在摘录版出现 `A/B/C/D 级`、`值得跟进`、`我的结论`、`局限` 等用语时报 FAIL。
- **每篇文献独立文件夹**：`PaperAnalysis/<日期>_<短标题>/` 自带 `reports/` + `analysis/` + `assets/` + `sources.md`，
  可整包拷走；`reports/` 现在放六份文件（三版 md + 三版 docx）。
- **脚本随技能分发**：渲染核心与 CLI 迁到 `skills/paper-analysis-report/tools/`
  （`docx_core.py` / `make_docx.py` / `check_docx.py`），预设只负责调用，技能可独立给别人用。
- 出稿 CLI 支持 `--auto`（按文档头 `version_label` 自动推断版本）与 `--kind detail|brief|notes`。

### 1.0.0
- 首个版本：详细版 + 简略版两版 Word、`paper_docx` 工具、交付前校验、可移植 Python 探测。
