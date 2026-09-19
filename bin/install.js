#!/usr/bin/env node
/**
 * dsh-paper-analysis 安装器
 *
 *   npx dsh-paper-analysis            # 安装到本机用户预设根
 *   npx dsh-paper-analysis --force    # 覆盖已存在的同名预设（先备份）
 *   npx dsh-paper-analysis --check    # 只体检，不写文件
 *
 * 只做三件事：定位预设根 → 备份并复制 preset → 检查 Python / python-docx 并打印验证步骤。
 * 不碰 DSH 的 profile、不装依赖、不联网。
 */
import { existsSync, mkdirSync, cpSync, rmSync, renameSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const here = dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = resolve(here, '..')
const PRESET_ID = 'paper-analysis'
const argv = process.argv.slice(2)
const force = argv.includes('--force') || argv.includes('-f')
const checkOnly = argv.includes('--check') || argv.includes('-c')

function version() {
  try {
    const pkg = JSON.parse(readFileSync(join(PACKAGE_ROOT, 'package.json'), 'utf8'))
    return pkg.version || '0.0.0'
  } catch {
    return '0.0.0'
  }
}

/** 预设根：优先 DSH_HOME，否则 %USERPROFILE%\\.dsh */
function presetRoot() {
  const home = process.env.DSH_HOME || join(homedir(), '.dsh')
  return join(home, '.agent-presets')
}

/** 找一个可用的 Python：环境变量 → 常见安装位置 → PATH */
function findPython() {
  const versions = ['313', '312', '311', '310', '39', '38']
  const candidates = [process.env.PAPER_ANALYSIS_PYTHON, process.env.PYTHON]
  for (const v of versions) {
    if (process.env.LOCALAPPDATA) candidates.push(join(process.env.LOCALAPPDATA, 'Programs', 'Python', `Python${v}`, 'python.exe'))
    candidates.push(`C:\\Python${v}\\python.exe`)
  }
  candidates.push('python', 'python3')
  for (const candidate of candidates.filter(Boolean)) {
    if (candidate === 'python' || candidate === 'python3') return candidate
    if (existsSync(candidate)) return candidate
  }
  return 'python'
}

function probePython() {
  const python = findPython()
  const ver = spawnSync(python, ['-c', 'import sys;print(sys.version.split()[0])'], {
    encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
  })
  if (ver.status !== 0) return { python, version: null, docx: false }
  const docx = spawnSync(python, ['-c', 'import docx;print("ok")'], {
    encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
  })
  return { python, version: (ver.stdout || '').trim(), docx: docx.status === 0 && (docx.stdout || '').trim() === 'ok' }
}

function main() {
  const root = presetRoot()
  const dest = join(root, PRESET_ID)
  console.log(`dsh-paper-analysis ${version()}`)
  console.log(`预设根: ${root}`)

  if (!existsSync(join(PACKAGE_ROOT, 'agent.cordis.yml'))) {
    console.error('包内容不完整：缺少 agent.cordis.yml。请重新安装本包。')
    process.exit(2)
  }

  const py = probePython()
  console.log('')
  console.log('依赖体检:')
  if (!py.version) {
    console.log('  [X] 找不到可用的 Python → 生成 Word 会失败')
    console.log('      处理：安装 Python 3 后执行 pip install python-docx，')
    console.log('            或设置 PAPER_ANALYSIS_PYTHON=<python.exe 绝对路径> 后重开 DSH')
  } else {
    console.log(`  [OK] Python ${py.version}  (${py.python})`)
    console.log(py.docx ? '  [OK] python-docx 已安装' : '  [X] python-docx 未安装 → 请执行: pip install python-docx')
  }

  if (checkOnly) {
    console.log('')
    console.log(`--check 模式：未写入任何文件。目标位置为 ${dest}`)
    console.log(existsSync(dest) ? '（该位置已存在同名预设，安装时会先备份）' : '（该位置当前没有同名预设）')
    return
  }

  if (existsSync(dest) && !force) {
    const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15).replace(/\.$/, '')
    const bak = `${dest}.bak-${stamp}`
    renameSync(dest, bak)
    console.log('')
    console.log(`已备份旧预设 → ${bak}`)
  } else if (existsSync(dest)) {
    rmSync(dest, { recursive: true, force: true })
  }

  mkdirSync(root, { recursive: true })
  cpSync(PACKAGE_ROOT, dest, {
    recursive: true,
    filter: (src) => !src.includes('node_modules') && !src.includes('.git'),
  })

  console.log('')
  console.log(`安装完成：${dest}`)
  console.log('')
  console.log('接下来：')
  console.log('  1. 重开一个 DSH 会话（预设是会话启动时挂载的）')
  console.log('  2. 预设选择器里选「论文分析模式」')
  console.log('  3. 确认工具表里有 paper_docx / skill / subagent / workflow')
  console.log('  4. 直接说：分析这篇论文：<PDF 路径>')
  console.log('')
  console.log('预设没出现时，用「创造模式」开会话并执行：')
  console.log(`  await ctx.agentPresets.standingKeyFor('${PRESET_ID}')   // 正常返回即挂载通过`)
  console.log('')
  console.log('卸载：删除上面那个目录即可（预设不会往别处写文件）。')
}

main()
