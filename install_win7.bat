@echo off
chcp 65001 >nul
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
set "PYEXE="
set "PYCMD="
py -3.8 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3.8"
if not defined PYCMD (
    python -c "import sys,os;sys.exit(0 if sys.version_info[:2]==(3,8) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
)
if defined PYCMD goto :deps

rem ---------- 3. install bundled Python 3.8.10 to the USER directory (no admin needed) ----------
if "%ARCH%"=="x64" (
    set "PT=%LocalAppData%\Programs\Python\Python38"
    set "PP=packaging\offline\win\python-3.8.10-amd64.exe"
) else (
    set "PT=%LocalAppData%\Programs\Python\Python38-32"
    set "PP=packaging\offline\win\python-3.8.10.exe"
)
echo Installing bundled Python 3.8.10 (%ARCH%) to %PT% ...
echo This does NOT need administrator rights.
start /w "" "%PP%" /quiet InstallAllUsers=0 TargetDir="%PT%" Include_launcher=0 PrependPath=0 Include_test=0 Shortcuts=0 AssociateFiles=0 Include_pip=1
if exist "%PT%\python.exe" (
    set "PYEXE=%PT%\python.exe"
) else (
    echo [ERROR] Bundled Python 3.8 did not install to %PT%.
    echo         Please run this file again with administrator rights.
    goto :err
)
"%PYEXE%" -c "import sys;sys.exit(0 if sys.version_info[:2]==(3,8) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] %PT% exists but is not Python 3.8. Aborting to avoid version mismatch.
    goto :err
)

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
if defined PYEXE (
    "%PYEXE%" -m pip install --no-index --find-links="%WF%" -r "%RF%"
    if errorlevel 1 goto :err
    "%PYEXE%" -c "import numpy,pandas,matplotlib,openpyxl,fitz,docx,PIL,tkinter;print('self-check OK')"
    if errorlevel 1 goto :err
    if "%ARCH%"=="x64" (
        "%PYEXE%" -c "import rapidocr_onnxruntime;print('OCR self-check OK')" 2>nul
        if errorlevel 1 echo [WARN] OCR module import failed - OCR tab will show a hint.
    ) else (
        echo [INFO] 32-bit system: OCR needs system Tesseract (optional).
    )
) else (
    %PYCMD% -m pip install --no-index --find-links="%WF%" -r "%RF%"
    if errorlevel 1 goto :err
    %PYCMD% -c "import numpy,pandas,matplotlib,openpyxl,fitz,docx,PIL,tkinter;print('self-check OK')"
    if errorlevel 1 goto :err
    if "%ARCH%"=="x64" (
        %PYCMD% -c "import rapidocr_onnxruntime;print('OCR self-check OK')" 2>nul
        if errorlevel 1 echo [WARN] OCR module import failed - OCR tab will show a hint.
    ) else (
        echo [INFO] 32-bit system: OCR needs system Tesseract (optional).
    )
)

echo.
echo ==============================================
echo  Install finished.
echo  Double-click "QiDong.bat" to run.
echo ==============================================
pause
exit /b 0

:err
echo.
echo Install FAILED. Please check the messages above.
pause
exit /b 1
