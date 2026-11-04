@echo off
rem ============================================================
rem ZhuanShu Workbench - Launcher (Win7 / Win10 / Win11)
rem Prefers the bundled Python 3.8 installed by install_win7.bat,
rem falls back to a system Python 3.8 if present.
rem If core deps are missing, automatically installs them from the
rem bundled offline wheels (no internet needed), then starts.
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ---- 1. 选定 Python（完整路径模式 EXE 或 命令模式 CMD） ----
set "PYEXE="
set "PYCMD="

rem Prefer bundled Python 3.8 (installed into the user directory)
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "BPY=%LocalAppData%\Programs\Python\Python38\python.exe"
) else (
    set "BPY=%LocalAppData%\Programs\Python\Python38-32\python.exe"
)
if exist "%BPY%" (
    set "PYEXE=%BPY%"
    goto :boot
)

rem Fall back to a system Python 3.8 via the py launcher
py -3.8 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYCMD=py -3.8"
    goto :boot
)

rem Fall back to a system "python" that reports 3.8
python -c "import sys;sys.exit(0 if sys.version_info[:2]==(3,8) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYCMD=python"
    goto :boot
)

echo [ERROR] Python 3.8 not found. Please run install_win7.bat first.
pause
exit /b 1

:boot
rem ---- 2. 依赖自检；缺失则用随包离线 wheel 自动补装（无需联网） ----
if defined PYEXE (
    "%PYEXE%" -c "import docx,fitz,PIL,openpyxl,matplotlib" >nul 2>&1
) else (
    %PYCMD% -c "import docx,fitz,PIL,openpyxl,matplotlib" >nul 2>&1
)
if not errorlevel 1 goto :run

echo 正在检测并补装离线依赖（首次运行约需 1-3 分钟，请耐心等待）...
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set "WF=packaging\offline\win\wheels_win64"
    set "RF=packaging\offline\win\requirements_win64.txt"
) else (
    set "WF=packaging\offline\win\wheels_win32"
    set "RF=packaging\offline\win\requirements_win32.txt"
)
if defined PYEXE (
    "%PYEXE%" -m pip install --no-index --find-links="%WF%" -r "%RF%" >nul 2>&1
    "%PYEXE%" -c "import docx,fitz,PIL,openpyxl,matplotlib,numpy,pandas" >nul 2>&1
) else (
    %PYCMD% -m pip install --no-index --find-links="%WF%" -r "%RF%" >nul 2>&1
    %PYCMD% -c "import docx,fitz,PIL,openpyxl,matplotlib,numpy,pandas" >nul 2>&1
)
if errorlevel 1 (
    echo [ERROR] 离线依赖补装失败，请手动双击 install_win7.bat 查看详细错误。
    pause
    exit /b 1
)
echo 依赖就绪，正在启动...

:run
if defined PYEXE (
    start "" "%PYEXE%" main.py
) else (
    start "ZhuanShu Workbench" %PYCMD% main.py
)
exit /b 0
