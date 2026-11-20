// Preset-local Cordis plugin row for the `paper-analysis` agent preset.
//
// Loaded by the row `./plugins/paper-report-docx-2.js` in agent.cordis.yml — straight out
// of the preset's own directory, so it travels with a copy of the preset and
// needs no npm install. Two consequences of living here, both load-bearing:
//   * it publishes no service (it only registers a model-facing tool and
//     consumes the host `subprocess` service), so it needs no `isolate` realm;
//   * it cannot `import` a harness package — nothing resolves upward from the
//     user's preset root into the deployment's node_modules. So the tool
//     definition is written directly against `ctx.tools.register`'s contract
//     (`parameters` is raw JSON Schema, which the registry accepts verbatim)
//     instead of going through `@deepseek-ai/dsh-tools`'s `defineTool`.
//
// It gives the agent one tool: `paper_docx`, which compiles the analysis report
// markdown into Word (.docx) for **only the versions the user selected at kickoff**
// (`modes`: detail / brief / notes), all into the same reports/ directory — a
// version that was not selected is neither written nor compiled — and then runs
// the delivery check over those versions plus an optional un-exported detail
// baseline: leftover markers, compact-version structure and length, cross-version
// number agreement, quote traceability against the paper text, and image
// references.

import { dirname, isAbsolute, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { existsSync } from 'node:fs'

const here = dirname(fileURLToPath(import.meta.url))
// 渲染与校验脚本由**技能**自带（skills/paper-analysis-report/tools/），预设只负责调用：
// 技能因此可以独立分发给别人，而预设里不必留一份重复副本。
const presetRoot = dirname(here)
const EXPORT_SCRIPT = join(presetRoot, 'skills', 'paper-analysis-report', 'tools', 'make_docx.py')
const CHECK_SCRIPT = join(EXPORT_SCRIPT, '..', 'check_docx.py')

/** Python 解释器候选：先环境变量，再 PATH，再常见安装位置。
 *  分发给他人的机器上版本与安装路径都不同，所以这里不许只认某几个版本号——
 *  实在找不到时也要让使用者能用环境变量 PAPER_ANALYSIS_PYTHON 指定。 */
const PYTHON_VERSIONS = ['313', '312', '311', '310', '39', '38']

function pythonCandidates() {
  const list = [process.env.PAPER_ANALYSIS_PYTHON, process.env.PYTHON]
  const home = process.env.USERPROFILE || process.env.HOME || ''
  const local = process.env.LOCALAPPDATA || ''
  const pyRoot = process.env.PYTHONHOME || ''
  if (pyRoot) list.push(join(pyRoot, 'python.exe'), join(pyRoot, 'bin', 'python3'))
  for (const v of PYTHON_VERSIONS) {
    if (local) list.push(join(local, 'Programs', 'Python', `Python${v}`, 'python.exe'))
    list.push(`C:\\Python${v}\\python.exe`)
    list.push(join(home, 'miniconda3', 'python.exe'), join(home, 'anaconda3', 'python.exe'))
    list.push(join(home, 'miniconda3', 'envs', 'base', 'python.exe'))
  }
  // PATH 兜底：Windows 用 python / py，类 Unix 用 python3
  list.push('python', 'python3', 'py')
  return list.filter((value) => typeof value === 'string' && value.length > 0)
}

const PYTHON_HINT =
  '找不到 Python 解释器。请安装 Python 3 并执行 pip install python-docx，' +
  '或把解释器绝对路径写进环境变量 PAPER_ANALYSIS_PYTHON 后重启 DSH；' +
  '也可以直接用 shell 工具运行 paper_docx 返回的等价命令。'

function resolvePython() {
  for (const candidate of pythonCandidates()) {
    if (candidate === 'python' || candidate === 'python3' || candidate === 'py') return candidate
    if (existsSync(candidate)) return candidate
  }
  return 'python'
}

function docxName(mdPath) {
  const base = String(mdPath).replace(/\\/g, '/').split('/').pop() || 'report.md'
  return base.replace(/\.md$/i, '') + '.docx'
}

function quoteArg(value) {
  const text = String(value)
  return /[\s"&^|<>]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/** 三个候选版本；本次真正编译哪几个，由 modes（= 用户开工时勾选的版本）决定。 */
const MODES = ['detail', 'brief', 'notes']

/** 本次要编译的版本：显式 modes 优先；否则按实际给了哪些 markdown 推断；都没有则报错。 */
function resolveModes(args) {
  const provided = { detail: args.detailMd, brief: args.briefMd, notes: args.notesMd }
  if (Array.isArray(args.modes) && args.modes.length > 0) {
    const picked = []
    for (const mode of args.modes) {
      if (!MODES.includes(mode)) throw new Error(`未知版本：${mode}（可选 ${MODES.join(' / ')}）`)
      if (!provided[mode]) throw new Error(`缺少 ${mode}Md：勾选了 ${mode} 版就必须给出该版 markdown 的绝对路径`)
      if (!picked.includes(mode)) picked.push(mode)
    }
    return picked
  }
  const inferred = MODES.filter((mode) => Boolean(provided[mode]))
  if (inferred.length === 0) {
    throw new Error('至少要给一版的 markdown：detailMd / briefMd / notesMd（未勾选的版本不要传）')
  }
  return inferred
}

/** The exact argv list for each step, so the shell fallback is faithful. */
function planCommands(args, modes) {
  if (!args.outDir) throw new Error('缺少 outDir：reports 目录')
  const inputs = { detail: args.detailMd, brief: args.briefMd, notes: args.notesMd }
  const python = resolvePython()
  const commands = []
  for (const mode of modes) {
    const argv = [python, EXPORT_SCRIPT, '--kind', mode, '--input', inputs[mode], '--out', args.outDir]
    if (args.pages !== false) argv.push('--pages')
    commands.push({ label: `make_docx (${mode})`, argv })
  }
  if (args.check !== false) {
    // 校验只覆盖**本次交付的版本**；baselineMd 是没导出 docx 的详细版底稿
    // （只勾了简略版/摘录版时的数字唯一来源），只参与"数字一致性"基线核对。
    const checkMds = modes.map((mode) => inputs[mode])
    if (args.baselineMd && !checkMds.includes(args.baselineMd)) checkMds.unshift(args.baselineMd)
    const argv = [python, CHECK_SCRIPT, '--md', ...checkMds,
                  '--source', args.source || join(args.outDir, '..', 'analysis', 'source', 'paper.txt')]
    for (const mode of modes) {
      if (inputs[mode]) argv.push(`--${mode}-docx`, join(args.outDir, docxName(inputs[mode])))
    }
    const jsonOut = args.jsonOut === undefined || args.jsonOut === null
      ? join(args.outDir, '..', 'analysis', 'check.json')
      : args.jsonOut
    // 目录不存在时不要传 --json-out：check_docx.py 不会替我们建目录。
    if (jsonOut && existsSync(dirname(jsonOut))) argv.push('--json-out', jsonOut)
    commands.push({ label: 'check_docx', argv })
  }
  return commands
}

async function readAll(stream) {
  let text = ''
  for await (const chunk of stream) text += typeof chunk === 'string' ? chunk : chunk.toString('utf8')
  return text
}

function exitCodeOf(settled) {
  if (typeof settled === 'number') return settled
  if (settled && typeof settled === 'object') {
    if (typeof settled.exitCode === 'number') return settled.exitCode
    if (typeof settled.code === 'number') return settled.code
  }
  return 0
}

const name = 'paper-docx-tool'
const inject = ['tools', 'subprocess']

function makeDefinition(ctx) {
  return {
  name: 'paper_docx',
  description:
    '把论文分析报告的 markdown 编译成 Word（.docx）——**只编译本次选定的版本**：' +
    'modes 里给哪几版（detail 详细版 / brief 简略版 / notes 摘录版）就只出哪几版，都放在同一个 reports 目录；' +
    '用户没勾选的版本不要传 md、也不要放进 modes。' +
    '随后只针对选定版本运行交付前校验——残留未解决标记、紧凑版必备章节与长度（2–3 页 / ≤2000 汉字）、' +
    '紧凑版数字能否在详细版里找到（没交付详细版时用 baselineMd 底稿作基线）、' +
    '英文引文能否在论文源文本中逐字找到、图片引用是否存在。' +
    '摘录版只含三节且不含任何评级（校验器会在出现评级用语时报 FAIL）。' +
    '任一版超篇幅或校验失败会返回非零退出码与具体原因。' +
    '若本会话没有 subprocess 服务，则返回等价的 shell 命令，改用 pwsh 执行即可。',
  parameters: {
    type: 'object',
    properties: {
      outDir: { type: 'string', description: 'reports 目录（选定版本的 docx 都放这里）' },
      modes: {
        type: 'array',
        items: { type: 'string', enum: ['detail', 'brief', 'notes'] },
        description: '本次要编译的版本 = 用户开工时勾选的版本；省略时按实际给了哪些 md 推断',
      },
      detailMd: { type: 'string', description: '详细版 markdown 的绝对路径（勾选了详细版时必填）' },
      briefMd: { type: 'string', description: '简略版 markdown 的绝对路径（勾选了简略版时必填）' },
      notesMd: { type: 'string', description: '摘录版 markdown 的绝对路径（勾选了摘录版时必填；只有"论文在做什么/创新点/该论文提供的思路"三节，不含任何评级）' },
      baselineMd: { type: 'string', description: '未交付但作为数字一致性基线的详细版底稿（例：analysis/70-detail-draft.md）；只参与校验，不导出 docx' },
      source: { type: 'string', description: '论文源文本路径（analysis/source/paper.txt），用于引文逐字核对' },
      jsonOut: { type: 'string', description: '校验明细 json 的路径；默认写到 <outDir>/../analysis/check.json（该目录不存在时不写）' },
      pages: { type: 'boolean', description: '统计页数（读取 Windows 文档属性），默认开启' },
      check: { type: 'boolean', description: '是否运行交付前校验，默认 true' },
    },
    required: ['outDir'],
  },
  timeoutMs: 900000,
  output: {
    schema: { type: 'string' },
    render(_args, value) {
      return [{ type: 'text', text: String(value) }]
    },
  },
  isConcurrencySafe() {
    return false
  },
  async execute(args) {
    const modes = resolveModes(args)
    const commands = planCommands(args, modes)
    const lines = []
    let failed = false

    for (const step of commands) {
      try {
        const executable = await ctx.subprocess.resolveExecutable(step.argv[0])
        const cwd = args.outDir && isAbsolute(args.outDir) ? args.outDir : process.cwd()
        const handle = ctx.subprocess.spawn({
          argv: [executable, ...step.argv.slice(1)],
          cwd,
          stdio: { stdin: 'ignore', stdout: 'pipe', stderr: 'pipe' },
          graceMs: 5000,
        })
        const [stdout, stderr, outcome] = await Promise.all([
          handle.stdout ? readAll(handle.stdout) : Promise.resolve(''),
          handle.stderr ? readAll(handle.stderr) : Promise.resolve(''),
          handle.done,
        ])
        const code = exitCodeOf(outcome)
        lines.push(`--- ${step.label} (exit ${code}) ---`)
        if (stdout.trim()) lines.push(stdout.trim())
        if (stderr.trim()) lines.push('[stderr] ' + stderr.trim())
        if (code !== 0) failed = true
      } catch (error) {
        failed = true
        const message = String(error && error.message ? error.message : error)
        lines.push(`--- ${step.label} 无法通过 subprocess 启动：${message}`)
        if (/python/i.test(message + step.argv[0])) lines.push(PYTHON_HINT)
        lines.push('也可直接用 shell 工具执行下面这条等价命令：')
        lines.push(step.argv.map(quoteArg).join(' '))
      }
    }

    lines.push(
      failed
        ? '结果：存在失败项。按提示修正 markdown 后重跑；超篇幅时删段落而不是改字号。'
        : `结果：全部通过。本次交付的 ${modes.join(' / ')} 版 docx 都在 reports 目录，校验明细见输出。`,
    )
    return lines.join('\n')
    },
  }
}

function apply(ctx) {
  ctx.tools.register(makeDefinition(ctx))
}

export { apply, inject, name }
