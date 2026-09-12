# 本地运行脚本（Windows PowerShell）
# 用法：  powershell -ExecutionPolicy Bypass -File scripts/run_local.ps1
# 可选：  -Preview 打印报告   -NoMail 不发邮件

param(
    [switch]$Preview,
    [switch]$NoMail
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root "src"
$env:PYTHONIOENCODING = "utf-8"

# 避免中文输出在 Windows 控制台/重定向时乱码
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

# 优先使用工程内虚拟环境，其次使用系统 python
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$py = if (Test-Path $venvPy) { $venvPy } else { "python" }

$args = @("-m", "sizhuang.cli", "run", "--json")
if ($Preview) { $args += "--preview" }
if ($NoMail)  { $args += "--no-mail" }

Write-Host "使用解释器: $py" -ForegroundColor Cyan
& $py @args
exit $LASTEXITCODE
