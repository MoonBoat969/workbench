@echo off
rem ============================================================
rem ZhuanShu Workbench - Win7 Offline One-Click Install
rem Uses bundled Python 3.8.10 installer + offline wheels.
rem No internet connection and no admin rights required
rem (admin rights only needed if Python installer must run).
rem ============================================================
setlocal
cd /d "%~dp0"

rem ---------- 1. detect CPU arch ----------
set ARCH=x86
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" set ARCH=x64
if defined PROCESSOR_ARCHITEW6432 (
    if /i "%PROCESSOR_ARCHITEW6432%"=="AMD64" set ARCH=x64
)
echo CPU architecture: %ARCH%

rem ---------- 2. locate a Python 3.8 ----------
set PY=
py -3.8 -c "import sys" >nul 2>&1
if not errorlevel 1 set PY=py -3.8
if "%PY%"=="" (
    python -c "import sys,os;sys.exit(0 if sys.version_info[:2]==(3,8) else 1)" >nul 2>&1
    if not errorlevel 1 set PY=python
)
if not "%PY%"=="" goto :deps

rem ---------- 3. install bundled Python 3.8.10 silently ----------
echo Installing bundled Python 3.8.10 (%ARCH%) ...
echo This step may need administrator rights.
if "%ARCH%"=="x64" (
    start /wait "" "packaging\offline\win\python-3.8.10-amd64.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1
) else (
    start /wait "" "packaging\offline\win\python-3.8.10.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1
)
if "%ARCH%"=="x64" (
    set "PATH=%ProgramFiles%\Python38;%ProgramFiles%\Python38\Scripts;%PATH%"
) else (
    set "PATH=%ProgramFiles(x86)%\Python38-32;%ProgramFiles(x86)%\Python38-32\Scripts;%PATH%"
)
set PY=python

:deps
echo.
echo Installing offline dependencies ...
if "%ARCH%"=="x64" (
    set WF=packaging\offline\win\wheels_win64
    set RF=packaging\offline\win\requirements_win64.txt
) else (
    set WF=packaging\offline\win\wheels_win32
    set RF=packaging\offline\win\requirements_win32.txt
)
%PY% -m pip install --no-index --find-links="%WF%" -r "%RF%"
if errorlevel 1 goto :err
%PY% -c "import numpy,pandas,matplotlib,openpyxl,fitz,docx,PIL,tkinter;print('self-check OK')"
if errorlevel 1 goto :err
if "%ARCH%"=="x64" (
    %PY% -c "import rapidocr_onnxruntime;print('OCR self-check OK')" 2>nul
    if errorlevel 1 echo [WARN] OCR module import failed - OCR tab will show a hint.
) else (
    echo [INFO] 32-bit system: OCR needs system Tesseract (optional).
)

echo.
echo ==============================================
echo  Install finished.
echo  Double-click "QiDong.bat" or "启动工作台.bat" to run.
echo ==============================================
pause
exit /b 0

:err
echo.
echo Install FAILED. Please check the messages above.
pause
exit /b 1