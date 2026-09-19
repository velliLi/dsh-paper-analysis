# 重打包脚本（维护者用）：把仓库内容打成可分发 zip
# 用法：powershell -ExecutionPolicy Bypass -File .\pack.ps1
[CmdletBinding()]
param([string]$Version = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Version) { Set-Content (Join-Path $root 'VERSION') $Version -Encoding ascii -NoNewline }
$ver = (Get-Content (Join-Path $root 'VERSION') -Raw).Trim()
$stage = Join-Path $root '.stage\paper-analysis'
if (Test-Path (Join-Path $root '.stage')) { Remove-Item (Join-Path $root '.stage') -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
# 只打预设运行需要的部分（技能含 tools，预设靠它出稿）
foreach ($item in @('agent.cordis.yml','preset.yml','VERSION','LICENSE','plugins','skills','source')) {
  if (Test-Path (Join-Path $root $item)) { Copy-Item (Join-Path $root $item) $stage -Recurse -Force }
}
# 泄漏检查：分发件里不得出现本机绝对路径
$leak = Get-ChildItem $stage -Recurse -File |
  Select-String -Pattern 'C:\\Users\\[^\\]+','C:/Users/','AppData\\Local\\Temp',"$env:USERNAME" -ErrorAction SilentlyContinue
if ($leak) { $leak | ForEach-Object { Write-Host "  泄漏 $($_.Path):$($_.LineNumber)" -ForegroundColor Yellow } }
else { Write-Host '  未发现本机路径泄漏 OK' -ForegroundColor Green }
$zip = Join-Path $root ("paper-analysis-$ver.zip")
Compress-Archive -Path $stage -DestinationPath $zip -Force
Remove-Item (Join-Path $root '.stage') -Recurse -Force
Write-Host "已生成 $zip ($([int]((Get-Item $zip).Length/1KB)) KB)" -ForegroundColor Green
