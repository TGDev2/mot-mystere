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

& python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) {
    throw "Les tests unitaires ont echoue : build interrompu."
}

$runtimeRoot = Join-Path $projectRoot ".tmp"
if (-not (Test-Path $runtimeRoot)) {
    New-Item -ItemType Directory -Path $runtimeRoot | Out-Null
}

$sourceSmokeRoot = Join-Path $runtimeRoot "smoke-source"
if (Test-Path $sourceSmokeRoot) {
    Remove-Item -LiteralPath $sourceSmokeRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $sourceSmokeRoot | Out-Null

$env:MOTMYSTERE_DATA_DIR = $sourceSmokeRoot
$env:MOTMYSTERE_DB_PATH = Join-Path $sourceSmokeRoot "hangman.db"

try {
    & python -m motmystere --smoke-test
    if ($LASTEXITCODE -ne 0) {
        throw "Le smoke test source a echoue : build interrompu."
    }
    if (-not (Test-Path $env:MOTMYSTERE_DB_PATH)) {
        throw "Le smoke test source n'a pas cree la base locale attendue."
    }
}
finally {
    Remove-Item Env:\MOTMYSTERE_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:\MOTMYSTERE_DB_PATH -ErrorAction SilentlyContinue
    if (Test-Path $sourceSmokeRoot) {
        Remove-Item -LiteralPath $sourceSmokeRoot -Recurse -Force
    }
}

& python -m PyInstaller --noconfirm --clean "motmystere.spec"
if ($LASTEXITCODE -ne 0) {
    throw "Le build Windows a echoue : PyInstaller n'a pas pu generer l'executable."
}

$smokeRoot = Join-Path $runtimeRoot "smoke-build"
if (Test-Path $smokeRoot) {
    Remove-Item -LiteralPath $smokeRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $smokeRoot | Out-Null

$env:MOTMYSTERE_DATA_DIR = $smokeRoot
$env:MOTMYSTERE_DB_PATH = Join-Path $smokeRoot "hangman.db"

try {
    & (Join-Path $projectRoot "dist\\MotMystere.exe") --smoke-test
    if ($LASTEXITCODE -ne 0) {
        throw "Le smoke test de l'executable Windows a echoue."
    }
    if (-not (Test-Path $env:MOTMYSTERE_DB_PATH)) {
        throw "Le smoke test de l'executable n'a pas cree la base locale attendue."
    }
}
finally {
    Remove-Item Env:\MOTMYSTERE_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:\MOTMYSTERE_DB_PATH -ErrorAction SilentlyContinue
    if (Test-Path $smokeRoot) {
        Remove-Item -LiteralPath $smokeRoot -Recurse -Force
    }
}

Write-Host ""
Write-Host "Build termine et verifie : dist\\MotMystere.exe"
