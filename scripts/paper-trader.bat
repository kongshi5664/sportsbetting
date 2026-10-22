@echo off
rem Game night, hands-off (scheduled daily around 4pm): the desk, injury alerts, and the paper trader,
rem which bets pretend money an hour before each game and takes closing prices. Stops after the last tip.
cd /d "%~dp0.."
start "Tip-Off Desk" ".venv\Scripts\python.exe" -m tipoff.api
start "Injury watcher" ".venv\Scripts\python.exe" -m tipoff.injuries --watch --every 3
".venv\Scripts\python.exe" -m tipoff.paper
