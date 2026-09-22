# Crea venv e instala dependencias para Windows.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$py = "python"
Write-Host "Python:" (& $py --version)
if (Test-Path ".\venv") {
    Write-Host "venv ya existe, actualizando paquetes..."
} else {
    & $py -m venv venv
}

$pip = ".\venv\Scripts\python.exe"
& $pip -m pip install --upgrade pip
& $pip -m pip install `
    "pyserial~=3.5" `
    "PyYAML~=6.0.3" `
    "psutil~=7.2.2" `
    "pystray~=0.19.5" `
    "babel~=2.18.0" `
    "ruamel.yaml~=0.19.1" `
    "sv-ttk~=2.6.1" `
    "tkinter-tooltip~=3.1.2" `
    "uptime~=3.0.1" `
    "ping3~=5.1.5" `
    "pyusb~=1.3.1" `
    "pycryptodome~=3.23.0" `
    "requests~=2.34.2" `
    "Pillow~=12.2.0" `
    "numpy~=2.4.4" `
    "GPUtil~=1.4.0" `
    "pyadl~=0.1" `
    "pythonnet~=3.0.5" `
    "pywin32>=311"

Write-Host ""
Write-Host "Listo. Ejecuta Iniciar.ps1 (acepta el aviso de administrador)."
