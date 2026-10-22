@echo off
rem Opening lines: one odds pull for today's games (about 5 credits per game).
rem Schedule it daily around 10am in Windows Task Scheduler (Start in: the project folder).
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m tipoff.snapshot
