"""NFL point-spread model: a betting helper that flags games, never places bets.

    python -m tipoff.nfl_spreads.load --seasons 2006-2026        # nflverse schedules/lines + team-game EPA
    python -m tipoff.nfl_spreads.backtest                        # walk-forward baseline, reports/nfl/
    python -m tipoff.nfl_spreads.experiment rest qb_change       # baseline vs baseline + factor(s)

Modules:
  data.py        tables nfl_games and nfl_team_game_epa in data/nfl.db; parsing and pbp aggregation
  load.py        the download/load CLI (free nflverse files, cached under data/raw/nflverse/)
  ratings.py     point-in-time EPA power ratings (recency-weighted, preseason regression)
  factors.py     factor registry: small pre-game feature functions that only see the past
  cover.py       P(cover)/P(push) from the empirical margin distribution (key numbers 3, 7, ...)
  model.py       margin model: HFA + scale x rating difference + factor terms, fitted on past seasons
  harness.py     walk-forward by season, evaluation against the closing spread, reports
  backtest.py / experiment.py   command lines

Sign convention (nflverse): `spread_line` is the market's expected HOME margin. Positive means the
home team is favoured (spread_line 8.5 = "home -8.5"). `result` = home score - away score. The
home side covers when result > spread_line, the away side when result < spread_line, a push when
equal. Our fair spread uses the same convention: a predicted home margin.
"""
