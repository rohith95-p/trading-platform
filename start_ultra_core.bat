@echo off
cd /d "C:\projects\ultra_core"
call venv\Scripts\activate.bat 2>nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo Starting Ultra Core Watchdog...
python scripts\watchdog.py
