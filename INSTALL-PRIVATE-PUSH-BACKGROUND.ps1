# One-time installer: background TEST notifications only. No live trading signals.
$ErrorActionPreference = "Stop"
$taskName = "AI-Daytrade-Private-Push"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$private = Join-Path $HOME ".ai-daytrade-private"
$configPath = Join-Path $private "push-background.json"

Write-Host "AI Daytrade Pro V1.07.2 - Windows background private push" -ForegroundColor Cyan
Write-Host "This installs an at-logon TEST push backend. It will not send trading signals."
$required = @("vapid-private.pem", "pairing-token.txt", "push.sqlite3")
foreach ($name in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $private $name) -PathType Leaf)) {
        throw "Missing existing private file: $name. Stop; do not replace keys."
    }
}
$pythonExe = (& py -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
if (-not $pythonExe) { throw "Python not found. Please install the already-used Python environment." }
$pythonExe = $pythonExe.Trim()
$pythonw = Join-Path (Split-Path -Parent $pythonExe) "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) { throw "pythonw.exe not found beside the active python.exe." }
& $pythonExe -c "import waitress, flask, cryptography, pywebpush" 2>$null
if ($LASTEXITCODE -ne 0) { throw "Missing Python dependencies. Existing v1071 requirements must be installed first." }

$contact = ""
if (Test-Path -LiteralPath $configPath) {
    $saved = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $contact = $saved.vapid_contact_email
}
if (-not $contact) {
    $contact = Read-Host "Enter SAME VAPID contact Email used previously (not API Key)"
}
if ($contact -notmatch "^[^\s@]+@[^\s@]+\.[^\s@]+$") {
    throw "Invalid email; nothing was scheduled."
}

# Config contains ONLY a contact email. The existing VAPID private key and pairing
# token are reused strictly from the local private folder; never copied to GitHub.
$json = @{ vapid_contact_email = $contact } | ConvertTo-Json
[System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))
$who = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonw -Argument "-m v1071.push_background" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $who
$principal = New-ScheduledTaskPrincipal -UserId $who -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "V1.07.2 private TEST Web Push on logon; NO Fugle, NO trading signals" -Force | Out-Null

Write-Host ""
Write-Host "Background push scheduled task installed." -ForegroundColor Green
Write-Host "Task: $taskName"
Write-Host "No trading signal mode has been enabled."
Write-Host "IMPORTANT: existing foreground push server must stop BEFORE starting this task."
Write-Host "After you close only the old push CMD, run: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Then check: curl.exe -H 'Origin: https://lishengchen01.github.io' http://127.0.0.1:8787/api/v1/health"
Write-Host "Tailscale Funnel separately needs persistent mode: tailscale funnel --bg 8787"
Write-Host "Log: $(Join-Path $private 'push-background.log')"
