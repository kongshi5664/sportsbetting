@echo off
rem Weekly review: grades anything finished, then writes reports\review-DATE.md.
rem Proposals also appear in the desk's Rulebook, where you apply or set them aside.
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m tipoff.review
pause
