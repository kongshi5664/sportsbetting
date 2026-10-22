@echo off
rem NFL game days, hands-off (schedule daily at 8am: London games kick off at 9:30am ET, and it exits
rem right away on days without NFL games). Bets pretend money an hour before each kickoff from
rem data\nfl.db and rules.nfl.json, records every prop, and takes closing prices. Stops after the last kickoff.
rem One desk serves every league, so it only starts the desk if nothing is listening on port 8000 yet.
cd /d "%~dp0.."
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul || start "HKX" ".venv\Scripts\python.exe" -m tipoff.api
rem The injury watcher starts two minutes later, once the trader has stored today's NFL games.
start "NFL injury watcher" cmd /c "timeout /t 120 /nobreak >nul & .venv\Scripts\python.exe -m tipoff.injuries --league nfl --watch --every 3"
".venv\Scripts\python.exe" -m tipoff.paper --league nfl
