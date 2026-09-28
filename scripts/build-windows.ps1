$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
py -3 -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw 'Python venv creation failed' }
& .\.venv-build\Scripts\python.exe -m pip install 'pyinstaller==6.16.0'
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
& .\.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --name CompControl --paths . --collect-submodules tkinter --add-data 'compcontrol/web;compcontrol/web' scripts/packaged_entry.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed' }
Write-Host 'Unsigned executable: dist\CompControl\CompControl.exe. Keep the full folder together.'
