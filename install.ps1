# 安装 paper-analysis 预设到本机用户预设根
# 用法：powershell -ExecutionPolicy Bypass -File .\install.ps1 [-Force]
[CmdletBinding()]
param(
  [switch]$Force
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $scriptDir 'paper-analysis'
if (-not (Test-Path $src)) { throw "找不到 $src —— 请在解压后的 kit 目录里运行本脚本（应能看到 paper-analysis 子目录）。" }

# 预设根：优先 DSH_HOME，否则 %USERPROFILE%\.dsh
$dshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $env:USERPROFILE '.dsh' }
$root = Join-Path $dshHome '.agent-presets'
$dest = Join-Path $root 'paper-analysis'

Write-Host "预设根: $root" -ForegroundColor Cyan

# 1) 依赖检查（不阻断安装，只提示）
$python = $null
foreach ($cand in @($env:PAPER_ANALYSIS_PYTHON, "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
                     'C:\Python313\python.exe', 'C:\Python312\python.exe', 'python')) {
  if (-not $cand) { continue }
  try {
    if ($cand -eq 'python' -or (Test-Path $cand)) {
      $ver = & $cand -c "import sys;print(sys.version.split()[0])" 2>$null
      if ($LASTEXITCODE -eq 0) { $python = $cand; break }
    }
  } catch { }
}
if ($python) {
  Write-Host "Python: $python ($ver)" -ForegroundColor Green
  $docx = & $python -c "import docx;print('ok')" 2>$null
  if ($docx -eq 'ok') {
    Write-Host "python-docx: 已安装" -ForegroundColor Green
  } else {
    Write-Host "python-docx: 未安装 → 请执行 pip install python-docx" -ForegroundColor Yellow
  }
} else {
  Write-Host "未找到 Python → 生成 Word 会失败。请安装 Python 3 并设置 PAPER_ANALYSIS_PYTHON" -ForegroundColor Yellow
}

# 2) 备份已存在的同名预设
if (Test-Path $dest) {
  $bak = "$dest.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
  if ($Force) {
    Remove-Item $dest -Recurse -Force
    Write-Host "已删除旧预设（-Force）" -ForegroundColor Yellow
  } else {
    Move-Item $dest $bak
    Write-Host "已备份旧预设 → $bak" -ForegroundColor Yellow
  }
}

# 3) 复制
New-Item -ItemType Directory -Force -Path $root | Out-Null
Copy-Item $src $dest -Recurse -Force

# 4) 结果与下一步
$ver = if (Test-Path (Join-Path $dest 'VERSION')) { (Get-Content (Join-Path $dest 'VERSION') -Raw).Trim() } else { '未知' }
Write-Host ""
Write-Host "安装完成：$dest（版本 $ver）" -ForegroundColor Green
Write-Host ""
Write-Host "接下来：" -ForegroundColor Cyan
Write-Host "  1. 新建会话，在预设选择器里选「论文分析模式」"
Write-Host "  2. 会话里应能看到工具 paper_docx、skill、subagent、workflow、pwsh"
Write-Host "  3. 直接说：分析这篇论文：<PDF 路径>"
Write-Host ""
Write-Host "若预设没出现，用「创造模式」开会话并执行下面这行做挂载验证：" -ForegroundColor Cyan
Write-Host "  await ctx.agentPresets.standingKeyFor('paper-analysis')   // 正常返回 = 挂载通过"
