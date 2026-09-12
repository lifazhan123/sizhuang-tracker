# 注册 Windows 计划任务：每天 12:00 在本机运行观察报告
#
# 用法（以管理员身份运行 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File scripts/register_windows_task.ps1
#
# 取消：
#   powershell -ExecutionPolicy Bypass -File scripts/register_windows_task.ps1 -Remove

param(
    [string]$TaskName = "合众思壮每日观察报告",
    [string]$Time = "12:00",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

if ($Remove) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "已删除计划任务：$TaskName" -ForegroundColor Yellow
    } else {
        Write-Host "计划任务不存在：$TaskName" -ForegroundColor Gray
    }
    return
}

$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot "run_local.ps1"
if (-not (Test-Path $script)) { throw "找不到 $script" }

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At $Time

# 只在交易日（周一至周五）触发由脚本内部再判断，这里先每日触发
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "每天 $Time 抓取合众思壮(002383)资讯并发送邮件" `
    -Force | Out-Null

Write-Host "✓ 已注册计划任务：$TaskName（每天 $Time）" -ForegroundColor Green
Write-Host "  可通过『任务计划程序』查看或手动运行。" -ForegroundColor Gray
