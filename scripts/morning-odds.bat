@echo off
rem Morning routine (scheduled daily around 10am):
rem   1. last night's box scores (free; grading and projections need them)
rem   2. grade last night and write the paper trader's recap (pushed to your phone if NTFY_TOPIC is set)
rem   3. one odds pull for today's games, which becomes the opening line (about 5 credits per game)
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m tipoff.backfill_stats --seasons 2026-27
".venv\Scripts\python.exe" -m tipoff.journal --recap
".venv\Scripts\python.exe" -m tipoff.snapshot
