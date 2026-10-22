@echo off
rem NFL weekly review (Tuesdays suit it: the week's games are in): grades anything finished, then
rem writes reports\nfl\review-DATE.md. Proposals also appear in the desk's Rulebook with NFL selected.
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m tipoff.review --league nfl
pause
