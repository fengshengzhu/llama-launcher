@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Building LlamaLauncher.exe ...
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name LlamaLauncher ^
  --icon assets\app_icon.ico ^
  --distpath dist --workpath build --specpath . ^
  main.py

if errorlevel 1 (
  echo Build FAILED.
) else (
  echo Build OK: "%~dp0dist\LlamaLauncher.exe"
)
pause
