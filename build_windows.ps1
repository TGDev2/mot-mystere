$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python est introuvable. Installez Python avant de lancer ce build."
}

cmd.exe /c 'python -c "import tkinter; tkinter.Tcl()" >nul 2>nul'
if ($LASTEXITCODE -ne 0) {
    throw "Tkinter/Tcl est indisponible. Reinstallez Python avec Tcl/Tk avant de builder."
}

& python -m PyInstaller --noconfirm --clean "motmystere.spec"
if ($LASTEXITCODE -ne 0) {
    throw "Le build Windows a echoue : PyInstaller n'a pas pu generer l'executable."
}

Write-Host ""
Write-Host "Build termine : dist\\MotMystere.exe"
