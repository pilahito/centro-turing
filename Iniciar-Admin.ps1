# Arranca con LibreHardwareMonitor (temperaturas CPU reales). Pide administrador.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`""
    )
    exit
}

$cfgPath = Join-Path $Root "config.yaml"
$cfg = Get-Content $cfgPath -Raw
$cfg = $cfg -replace '(?m)^(\s*HW_SENSORS:\s*).+$', '${1}AUTO'
Set-Content -Path $cfgPath -Value $cfg -Encoding UTF8

$py = Join-Path $Root "venv\Scripts\python.exe"
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match 'centro-turing\\main\.py'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Process -FilePath $py -ArgumentList "main.py" -WorkingDirectory $Root -WindowStyle Hidden
Write-Host "Pantalla Turing en marcha con sensores LHM (admin)."
