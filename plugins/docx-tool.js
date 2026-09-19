// Preset-local Cordis plugin row for the `paper-analysis` agent preset.
//
// Loaded by the row `./plugins/paper-docx.js` in agent.cordis.yml — straight out
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
// markdown into Word (.docx) — 详细版 + 简略版, both into the same reports/
// directory — and then runs the delivery check: leftover markers, brief-version
// structure and length (2–3 pages), cross-version number agreement, quote
// traceability against the paper text, and image references.

import { dirname, join } from 'node:path'
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

/** The exact argv list for each step, so the shell fallback is faithful. */
function planCommands(args) {
  const modes = Array.isArray(args.modes) && args.modes.length > 0 ? args.modes : ['detail', 'brief', 'notes']
  const inputs = { detail: args.detailMd, brief: args.briefMd, notes: args.notesMd }
  for (const mode of modes) {
    if (!inputs[mode]) throw new Error(`缺少 ${mode}Md：${mode} 版 markdown 的绝对路径`)
  }
  if (!args.outDir) throw new Error('缺少 outDir：reports 目录')
  const python = resolvePython()
  const commands = []
  for (const mode of modes) {
    const argv = [python, EXPORT_SCRIPT, '--kind', mode, '--input', inputs[mode], '--out', args.outDir]
    if (args.pages === true) argv.push('--pages')
    commands.push({ label: `make_docx (${mode})`, argv })
  }
  if (args.check !== false) {
    const argv = [python, CHECK_SCRIPT, '--md', args.detailMd, args.briefMd, args.notesMd,
                  '--source', args.source || join(args.outDir, '..', 'analysis', 'source', 'paper.txt'),
                  '--detail-docx', join(args.outDir, docxName(args.detailMd)),
                  '--brief-docx', join(args.outDir, docxName(args.briefMd)),
                  '--notes-docx', join(args.outDir, docxName(args.notesMd))]
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

const definition = {
  name: 'paper_docx',
  description:
    '把论文分析报告的 markdown 编译成 Word（.docx）：默认同时生成三版——详细版、简略版、摘录版，都放在同一个 reports 目录。' +
    '随后运行交付前校验——残留未解决标记、简略版必备章节与长度（2–3 页）、两版数字一致性、' +
    '英文引文能否在论文源文本中逐字找到、图片引用是否存在。' +
    '摘录版只含三节且不含任何评级（校验器会在出现评级用语时报 FAIL）。' +
    '任一版超篇幅或校验失败会返回非零退出码与具体原因。' +
    '若本会话没有 subprocess 服务，则返回等价的 shell 命令，改用 pwsh 执行即可。',
  parameters: {
    type: 'object',
    properties: {
      detailMd: { type: 'string', description: '详细版 markdown 的绝对路径' },
      briefMd: { type: 'string', description: '简略版 markdown 的绝对路径' },
      notesMd: { type: 'string', description: '摘录版 markdown 的绝对路径（只有"论文在做什么/创新点/该论文提供的思路"三节，不含任何评级）' },
      outDir: { type: 'string', description: 'reports 目录（详细版与简略版都放这里）' },
      source: { type: 'string', description: '论文源文本路径（analysis/source/paper.txt），用于引文逐字核对' },
      modes: {
        type: 'array',
        items: { type: 'string', enum: ['detail', 'brief'] },
        description: '要生成的版本，默认两者都生成',
      },
      pages: { type: 'boolean', description: '统计页数（读取 Windows 文档属性），默认 true' },
      check: { type: 'boolean', description: '是否运行交付前校验，默认 true' },
    },
    required: ['detailMd', 'briefMd', 'notesMd', 'outDir'],
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
    const commands = planCommands(args)
    const lines = []
    let failed = false

    for (const step of commands) {
      try {
        const handle = await ctx.subprocess.spawn({
          command: await ctx.subprocess.resolveExecutable(step.argv[0]),
          args: step.argv.slice(1),
        })
        const [stdout, stderr, settled] = await Promise.all([
          handle.stdout ? readAll(handle.stdout) : Promise.resolve(''),
          handle.stderr ? readAll(handle.stderr) : Promise.resolve(''),
          handle.wait ? handle.wait() : Promise.resolve(0),
        ])
        const code = exitCodeOf(settled)
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
        : '结果：全部通过。详细版、简略版、摘录版 docx 都在 reports 目录，校验明细见输出。',
    )
    return lines.join('\n')
  },
}

function apply(ctx) {
  ctx.tools.register(definition)
}

export { apply, inject, name }
