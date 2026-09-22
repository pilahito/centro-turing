# Arranca la pantalla con main.py (silencioso, idempotente).
# El centro grafico es Centro-Turing.cmd — no lo abras desde aqui.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$py = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "No hay venv. Ejecuta Instalar.ps1"; exit 1 }

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -match [regex]::Escape((Join-Path $Root "main.py")) -or
        ($_.CommandLine -match "centro-turing" -and $_.CommandLine -match "main\.py")
    )
}
if ($running) {
    Write-Host "Pantalla ya en marcha (main.py). Centro: Centro-Turing.cmd"
    exit 0
}

Start-Process -FilePath $py -ArgumentList "main.py" -WorkingDirectory $Root -WindowStyle Hidden
Write-Host "Pantalla en marcha con main.py. Centro: Centro-Turing.cmd"
