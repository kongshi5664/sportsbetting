@echo off
rem Morning routine: last night's box scores (free; needed to grade bets and keep projections current),
rem then one odds pull for today's games, which becomes the opening line (about 5 credits per game).
rem Schedule it daily around 10am in Windows Task Scheduler (Start in: the project folder).
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m tipoff.backfill_stats --seasons 2026-27
".venv\Scripts\python.exe" -m tipoff.snapshot
