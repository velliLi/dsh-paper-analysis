# 把它发布到 GitHub（三步）

本仓库已经**在本地完成初始化并提交**（`dist/repo/`）。剩下的是"建远端 + 推上去"，这一步需要你的
GitHub 账号授权，我这边无法代办。

---

## 第 0 步：先替换三个占位符（必须）

| 文件 | 占位符 | 换成 |
|---|---|---|
| `README.md` 顶部 | `REPLACE_WITH_YOUR_GITHUB_USER` | 你的 GitHub 用户名（发布后删掉顶部那段提示） |
| `package.json` | `REPLACE_WITH_YOUR_GITHUB_USER` / `REPLACE_WITH_YOUR_NAME` | 用户名 / 你的名字或 ID |
| `cordis.patch.yml` | `REPLACE_WITH_ABSOLUTE_PATH_TO_THIS_PACKAGE` | 本包的实际安装路径（只有走 `dsh plugin add` 那条路才需要填） |

```powershell
cd E:\学习资料\研究生阶段\周报\dist\repo
# 例：把占位符批量替换成自己的用户名（Windows 路径要带引号）
$u = "your-github-name"
(Get-ChildItem -Recurse -File -Include *.md,*.json,*.yml) |
  ForEach-Object { (Get-Content $_ -Raw -Encoding UTF8).Replace('REPLACE_WITH_YOUR_GITHUB_USER', $u) |
    Set-Content $_ -Encoding UTF8 -NoNewline }
```
（`package.json` 里的 `REPLACE_WITH_YOUR_NAME` 与 `cordis.patch.yml` 的路径占位符请手工再改一次。）

---

## 第 1 步：在 GitHub 建一个空仓库

网页操作：<https://github.com/new> → Repository name 填 `dsh-paper-analysis`
→ **不要**勾选 Add a README / .gitignore / license（本仓库已经有了）→ Create repository。

---

## 第 2 步：关联远端并推送

```powershell
cd E:\学习资料\研究生阶段\周报\dist\repo
git remote add origin https://github.com/<你的用户名>/dsh-paper-analysis.git
git branch -M main
git push -u origin main
```

首次推送会弹浏览器让你登录 GitHub（Git Credential Manager）。推送成功后刷新仓库页面即可看到内容。

---

## 第 3 步（可选）：发布到 npm，让 `npx dsh-paper-analysis` 生效

只有发布到 npm，别人才能用 `npx` 一条命令安装；仓库本身用 `git clone` 就能用。

```powershell
cd E:\学习资料\研究生阶段\周报\dist\repo
npm login                 # 登录你的 npm 账号（需要邮箱验证）
npm pack --dry-run        # 先看会打包哪些文件（应为 34 项左右，不含 PaperAnalysis）
npm publish --access public
```

- 包名 `dsh-paper-analysis` 若已被占用，改成带 scope 的形式：
  ```powershell
  # package.json 里 "name": "@你的npm用户名/dsh-paper-analysis"
  npm publish --access public
  ```
  带 scope 后安装命令变成 `npx @你的npm用户名/dsh-paper-analysis`。
- 发布后仓库主页可以加徽章，别人一眼就能看到安装方式：

```markdown
[![npm](https://img.shields.io/npm/v/dsh-paper-analysis)](https://www.npmjs.com/package/dsh-paper-analysis)
```

- 以后改版本：改 `VERSION` 与 `package.json` 的 `version` → `npm publish` → 在 GitHub 上打 tag：
  ```powershell
  git tag v1.1.1 && git push origin v1.1.1
  ```

---

## 别人怎么用（发布后你可以把这段贴到 README 或群里）

```bash
# ① 只要预设（DSH 用户，一条命令）
npx dsh-paper-analysis

# ② 只要技能（任何 Agent / 手动用；只要 Python + python-docx）
git clone https://github.com/<你的用户名>/dsh-paper-analysis.git
pip install python-docx
python dsh-paper-analysis/skills/paper-analysis-report/tools/check_env.py

# ③ 作为 DSH 插件
dsh plugin --profile web add dsh-paper-analysis
```

---

## 顺手要做的两件事

1. **`cordis.patch.yml` 的路径占位符**：不填就不影响 `npx` 安装，只影响 `dsh plugin add` 那条路。
2. **仓库描述与 Topics**（GitHub 仓库页右上 Settings）：
   描述建议 `DSH agent preset + skill: 论文三版 Word 报告（详细/简略/摘录），带证据链与引文校验`；
   Topics 建议 `dsh, deepseek-harness, agent-preset, paper-analysis, docx, research-tools`。

## 维护提示

- **不要把 `PaperAnalysis/` 提交进来**：那里是你的分析产物（可能含未发表的论文内容）。
  `.gitignore` 已经排除了 `PaperAnalysis/`、`**/reports/`、`**/analysis/`、`*.docx`、`dist/`。
- 每次改动后自查一遍：`git status --short` 只应出现你预期的文件。
- 修改预设或技能后，本地生效处是 `~/.dsh/.agent-presets/paper-analysis/`；
  改完记得**同步回本仓库**再提交（仓库根 = 预设根，结构一致）。
