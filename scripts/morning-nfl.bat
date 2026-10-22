@echo off
rem NFL mornings (schedule daily around 10am, after "TipOff Morning"):
rem   1. this season's NFL box scores from nflverse (free; grading and projections need them)
rem   2. grade, then recap every NFL game day that is fully graded and not yet recapped
rem      (nflverse can land a day after the games, so Sunday's recap may come Monday or Tuesday)
rem No odds pull here: the NFL paper trader pulls each game an hour before kickoff (about 6 credits a game).
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m tipoff.backfill_stats --league nfl --seasons 2026
".venv\Scripts\python.exe" -m tipoff.journal --league nfl --recap --catch-up
