@echo off
rem ============================================================
rem Build a portable no-install folder (Windows 7, 64/32-bit)
rem Uses workbench.spec (app NAME is defined inside the spec file,
rem so this .bat is pure ASCII and immune to codepage issues).
rem Requires Python 3.8 on THIS machine (run install_win7.bat first).
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"

set "PYEXE="
set "PYCMD="
py -3.8 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3.8"
if not defined PYCMD (
    python -c "import sys;sys.exit(0 if sys.version_info[:2]==(3,8) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
    rem 未找到系统 python3.8：尝试内置 Python38
    if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
        set "BPY=%LocalAppData%\Programs\Python\Python38\python.exe"
    ) else (
        set "BPY=%LocalAppData%\Programs\Python\Python38-32\python.exe"
    )
    if exist "%BPY%" set "PYEXE=%BPY%"
)
if not defined PYEXE if not defined PYCMD (
    echo [ERROR] Python 3.8 not found. Please run install_win7.bat first.
    pause
    exit /b 1
)

if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    set BW=packaging\build_wheels_win
) else (
    set BW=packaging\build_wheels_win32
)

echo Installing PyInstaller 5.13.2 from offline wheels ...
if defined PYEXE (
    "%PYEXE%" -m pip install --no-index --find-links="%BW%" "pyinstaller==5.13.2"
    if errorlevel 1 goto :err
) else (
    %PYCMD% -m pip install --no-index --find-links="%BW%" "pyinstaller==5.13.2"
    if errorlevel 1 goto :err
)

echo Building (onedir, portable folder) ...
if defined PYEXE (
    "%PYEXE%" -m PyInstaller --noconfirm --clean workbench.spec
    if errorlevel 1 goto :err
) else (
    %PYCMD% -m PyInstaller --noconfirm --clean workbench.spec
    if errorlevel 1 goto :err
)

echo Running dependency self-check on the built program ...
if defined PYEXE (
    "%PYEXE%" packaging\win_selfcheck.py
) else (
    %PYCMD% packaging\win_selfcheck.py
)
if errorlevel 1 (
    echo [ERROR] Dependency self-check failed. See output above.
    goto :err
)

if /i "%~1"=="/onefile" (
    echo Building single-file exe ...
    if defined PYEXE (
        "%PYEXE%" -m PyInstaller --noconfirm --clean --onefile workbench.spec
    ) else (
        %PYCMD% -m PyInstaller --noconfirm --clean --onefile workbench.spec
    )
    if errorlevel 1 goto :err
)

echo.
echo Build finished. See the dist\ folder for the output.
echo Data is stored next to it in data\workbench.db (auto-created).
pause
exit /b 0

:err
echo Build FAILED. See messages above.
pause
exit /b 1
