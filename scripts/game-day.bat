@echo off
rem Game night: the desk, live odds every 30 minutes with closing prices at tip, and injury alerts.
rem Each runs in its own window; close a window to stop it. Watchers stop by themselves after the last tip.
cd /d "%~dp0.."
start "HKX" ".venv\Scripts\python.exe" -m tipoff.api
start "Odds watcher" ".venv\Scripts\python.exe" -m tipoff.snapshot --watch --every 30
start "Injury watcher" ".venv\Scripts\python.exe" -m tipoff.injuries --watch --every 3
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8000/#/tonight"
