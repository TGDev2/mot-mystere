@echo off
setlocal

set "ROOT_DIR=%~dp0"

if exist "%ROOT_DIR%dist\MotMystere.exe" (
    start "" "%ROOT_DIR%dist\MotMystere.exe"
    exit /b 0
)

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "%ROOT_DIR%main.py"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%ROOT_DIR%main.py"
    exit /b 0
)

echo MotMystere n'a pas pu etre lance.
echo.
echo Option 1: construisez dist\MotMystere.exe avec build_windows.ps1
echo Option 2: installez Python puis relancez ce fichier
pause
