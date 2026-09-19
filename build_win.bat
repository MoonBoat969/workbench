@echo off
rem ============================================================
rem Build a portable no-install folder (Windows 7, 64/32-bit)
rem Requires Python 3.8 on THIS machine (run install_win7.bat first).
rem Output: dist\专属工作台\  - copy the whole folder anywhere.
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

set PY=python
py -3.8 -c "import sys" >nul 2>&1
if not errorlevel 1 set PY=py -3.8

if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set BW=packaging\build_wheels_win
) else (
    set BW=packaging\build_wheels_win32
)

echo Installing PyInstaller 5.13.2 from offline wheels ...
%PY% -m pip install --no-index --find-links="%BW%" "pyinstaller==5.13.2"
if errorlevel 1 goto :err

echo Building ...
%PY% -m PyInstaller --noconfirm --clean --windowed ^
  --name 专属工作台 ^
  --add-data "assets;assets" ^
  --hidden-import matplotlib.backends.backend_tkagg ^
  --hidden-import matplotlib.backends.backend_agg ^
  --hidden-import rapidocr_onnxruntime ^
  --collect-submodules rapidocr_onnxruntime ^
  --collect-data rapidocr_onnxruntime ^
  --collect-binaries onnxruntime ^
  main.py
if errorlevel 1 goto :err

echo.
echo Build finished: dist\专属工作台\
echo Copy the whole folder to the target machine and run 专属工作台.exe
echo Data is stored in data\workbench.db next to the exe (auto-created).
pause
exit /b 0

:err
echo Build FAILED. See messages above.
pause
exit /b 1