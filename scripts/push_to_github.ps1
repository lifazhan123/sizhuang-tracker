# 一键把本项目推送到 GitHub
#
# 用法（在项目目录下，或用绝对路径调用）：
#   powershell -ExecutionPolicy Bypass -File scripts/push_to_github.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/push_to_github.ps1 -Repo sizhuang-tracker
#
# 首次运行会弹出浏览器让你登录 GitHub（授权后凭据会被系统记住，之后不再询问）。

param(
    [string]$Owner = "lifazhan123",
    [string]$Repo  = "gupiao",
    [string]$Branch = "main",
    [string]$Proxy = "http://127.0.0.1:9674"   # 系统代理；直连可用时传空字符串
)

$ErrorActionPreference = "Stop"

# ---- 定位工程根目录 ----
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ---- 定位便携版 git（若系统已有 git 则优先使用系统 git）----
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if ($gitCmd) {
    $git = $gitCmd.Source
} else {
    $base = "C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0"
    $git  = Join-Path $base "cmd\git.exe"
    if (-not (Test-Path $git)) { throw "找不到 git，请先安装 Git for Windows。" }
    # 便携版需要显式指定执行目录，否则找不到 remote helper
    $env:GIT_EXEC_PATH = Join-Path $base "mingw64\libexec\git-core"
    $env:PATH = "$(Join-Path $base 'mingw64\libexec\git-core');$(Join-Path $base 'cmd');$(Join-Path $base 'mingw64\bin');$(Join-Path $base 'usr\bin');$env:PATH"
}

Write-Host "使用 git：$git" -ForegroundColor Cyan

# ---- 代理 ----
if ($Proxy) {
    & $git config --global http.proxy  $Proxy
    & $git config --global https.proxy $Proxy
    Write-Host "已设置代理：$Proxy" -ForegroundColor Gray
}

# ---- 初始化 / 提交 ----
if (-not (Test-Path ".git")) {
    Write-Host "初始化本地仓库…" -ForegroundColor Gray
    & $git init -q
    & $git symbolic-ref HEAD "refs/heads/$Branch"
}
& $git add -A
& $git -c user.name="$Owner" -c user.email="$Owner@users.noreply.github.com" `
    commit -q -m "feat: 合众思壮(002383) 个股观察与每日邮件推送工程" 2>$null

# ---- 关联远端并推送 ----
$url = "https://github.com/$Owner/$Repo.git"
& $git remote remove origin 2>$null
& $git remote add origin $url

Write-Host "推送至 $url …" -ForegroundColor Cyan
& $git push -u origin $Branch

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ 推送成功：https://github.com/$Owner/$Repo" -ForegroundColor Green
    Write-Host "  下一步：在仓库 Settings → Secrets and variables → Actions 配置邮箱授权码，" -ForegroundColor Yellow
    Write-Host "  详见 README.md 的「配置每日 12:00 邮件推送」章节。" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "✗ 推送失败。常见原因：" -ForegroundColor Red
    Write-Host "  1) 远端仓库不存在 —— 请先在 GitHub 网页上创建 $Repo" -ForegroundColor Red
    Write-Host "  2) 未登录 —— 重新运行本脚本并在浏览器完成授权" -ForegroundColor Red
    Write-Host "  3) 网络不通 —— 确认代理端口（-Proxy 参数）" -ForegroundColor Red
}
exit $LASTEXITCODE
