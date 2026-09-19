@echo off
rem Launch ZhuanShu Workbench (Windows 7)
cd /d "%~dp0"
set PY=python
py -3.8 -c "import sys" >nul 2>&1
if not errorlevel 1 set PY=py -3.8
start "" %PY% main.py