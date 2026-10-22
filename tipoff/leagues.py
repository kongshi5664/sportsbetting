"""One config per league, so the same pricing, rules, paper trader and desk run on any sport.

Everything sport-specific lives here: the Odds API sport key and prop markets, which box-score
column each market grades against, how stats are named, team codes, the ESPN feed path, which
stats are priced with a normal vs. a negative binomial, and where the league's data and rules live.
Each league has its own SQLite database and rules file, so one league's paper trader never touches
another's bets. NBA's config is exactly what the code used before leagues existed.

    from tipoff.leagues import get
    nfl = get("nfl")
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


@dataclass(frozen=True)
class League:
    id: str
    label: str
    sport_key: str                    # The Odds API sport key
    markets: tuple                    # prop markets pulled by default (over/under only)
    market_stat: dict                 # market -> player_games column it grades against
    stat_label: dict                  # stat -> "Points" (board, ticket)
    team_codes: dict                  # Odds API full team name -> box-score code
    espn_path: str                    # site.api.espn.com/apis/site/v2/sports/<espn_path>
    espn_codes: dict                  # ESPN abbreviation -> box-score code, where they differ
    normal_stats: dict                # stat -> (sd floor as a share of the mean, absolute sd floor); others: neg. binomial
    opp_stats: tuple                  # stats adjusted for what the opponent's defense allows
    stat_columns: tuple               # player_games stat columns (SQL type INTEGER)
    team_columns: tuple               # team_games stat columns
    db_file: str                      # under data/
    rules_file: str                   # under the project root
    env: str                          # env var prefix for overrides: <ENV>_DB, <ENV>_RULES
    min_games: int = 5                # games of history before a player is priced
    recent_games: int = 10            # "recent form" window
    season_full: int = 20             # games of this season before the season mean gets full weight
    opp_window: int = 20              # opponent games used for the matchup factor
    opp_min: int = 8                  # ...and the fewest that count
    league_window: int = 600          # team-games behind the league average
    has_minutes: bool = True          # minutes-based features (trend, back-to-backs)
    periods: int = 4
    period_minutes: float = 12
    ot_minutes: float = 5
    ntfy_tag: str = "basketball"
    stat_words: dict = field(default_factory=dict)  # stat -> lower-case words for sentences

    @property
    def game_minutes(self):
        return self.periods * self.period_minutes

    @property
    def db_path(self) -> Path:
        return Path(os.environ.get(f"{self.env}_DB") or DATA / self.db_file)

    @property
    def rules_path(self) -> Path:
        return Path(os.environ.get(f"{self.env}_RULES") or ROOT / self.rules_file)

    def words(self, stat):
        return self.stat_words.get(stat) or self.stat_label.get(stat, stat).lower()

    def status_key(self, key):
        """Keys in data/status.json: NBA keeps the original names, other leagues are prefixed."""
        return key if self.id == "nba" else f"{self.id}_{key}"


NBA = League(
    id="nba", label="NBA", sport_key="basketball_nba",
    markets=("player_points", "player_rebounds", "player_assists", "player_threes", "player_blocks"),
    market_stat={"player_points": "pts", "player_rebounds": "reb", "player_assists": "ast",
                 "player_threes": "fg3m", "player_blocks": "blk"},
    stat_label={"pts": "Points", "reb": "Rebounds", "ast": "Assists", "fg3m": "Threes", "blk": "Blocks"},
    team_codes={
        "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN", "Charlotte Hornets": "CHA",
        "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
        "Detroit Pistons": "DET", "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
        "Los Angeles Clippers": "LAC", "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
        "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
        "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
        "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
        "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
    },
    espn_path="basketball/nba",
    espn_codes={"WSH": "WAS", "GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA"},
    normal_stats={"pts": (0.35, 2.0)},
    opp_stats=("pts", "reb", "ast"),
    stat_columns=("pts", "reb", "ast", "blk", "stl", "fg3m", "tov"),
    team_columns=("pts", "opp_pts", "reb", "ast"),
    db_file="tipoff.db", rules_file="rules.json", env="TIPOFF",
)

NFL = League(
    id="nfl", label="NFL", sport_key="americanfootball_nfl",
    # Hard Rock's NFL over/unders (verified 2026-10-22). Touchdown-scorer props are Yes-only: no
    # Under to de-vig, so they are left out on purpose.
    markets=("player_pass_yds", "player_pass_attempts", "player_rush_yds", "player_rush_attempts",
             "player_reception_yds", "player_receptions"),
    market_stat={"player_pass_yds": "pass_yds", "player_pass_attempts": "pass_att",
                 "player_rush_yds": "rush_yds", "player_rush_attempts": "rush_att",
                 "player_reception_yds": "rec_yds", "player_receptions": "rec"},
    stat_label={"pass_yds": "Pass yards", "pass_att": "Pass attempts", "rush_yds": "Rush yards",
                "rush_att": "Rush attempts", "rec_yds": "Receiving yards", "rec": "Receptions"},
    team_codes={  # box-score codes are nflverse's (LA for the Rams)
        "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
        "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
        "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
        "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
        "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
        "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
        "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ",
        "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
        "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN",
        "Washington Commanders": "WAS",
    },
    espn_path="football/nfl",
    espn_codes={"WSH": "WAS", "LAR": "LA"},
    # Yards are priced with a normal; attempts and receptions are counts (negative binomial).
    # Floors are rough game-to-game spreads (a QB's passing yards swing ~30% of his mean, a
    # receiver's ~60%): six games is too few to trust a sample standard deviation on its own.
    normal_stats={"pass_yds": (0.28, 30.0), "rush_yds": (0.5, 12.0), "rec_yds": (0.6, 12.0)},
    opp_stats=("pass_yds", "pass_att", "rush_yds", "rush_att", "rec_yds", "rec"),
    stat_columns=("pass_yds", "pass_att", "pass_cmp", "rush_yds", "rush_att", "rec_yds", "rec", "targets"),
    team_columns=("pts", "opp_pts", "pass_yds", "pass_att", "rush_yds", "rush_att", "rec_yds", "rec"),
    db_file="nfl.db", rules_file="rules.nfl.json", env="TIPOFF_NFL",
    # About 17 games a season: shorter windows, and three games of history are enough to price.
    min_games=3, recent_games=6, season_full=8, opp_window=8, opp_min=4, league_window=256,
    has_minutes=False, periods=4, period_minutes=15, ot_minutes=10, ntfy_tag="football",
)

LEAGUES = {l.id: l for l in (NBA, NFL)}

# Every league's stat keys are distinct, so pricing can look a stat's distribution up directly.
NORMAL_STATS = {s: v for l in LEAGUES.values() for s, v in l.normal_stats.items()}


def get(league_id=None) -> League:
    """The league with this id (default NBA). Unknown ids are an error, never a silent NBA."""
    if league_id is None or isinstance(league_id, League):
        return league_id or NBA
    try:
        return LEAGUES[league_id.lower()]
    except KeyError:
        raise SystemExit(f"Unknown league '{league_id}'. Choose from: {', '.join(LEAGUES)}.")


def for_market(market) -> League:
    """The league a prop market belongs to (markets are unique across leagues)."""
    return next((l for l in LEAGUES.values() if market in l.market_stat), NBA)


def stat_of(market):
    return for_market(market).market_stat.get(market)


def stat_words(stat):
    """'pts' -> 'points', 'rec_yds' -> 'receiving yards' (stat keys are unique across leagues)."""
    lg = next((l for l in LEAGUES.values() if stat in l.stat_label), None)
    return lg.words(stat) if lg else stat


def stat_name(stat):
    """'pts' -> 'Points', 'rec_yds' -> 'Receiving yards'."""
    lg = next((l for l in LEAGUES.values() if stat in l.stat_label), None)
    return lg.stat_label[stat] if lg else stat


def add_argument(ap):
    """The shared --league flag for command-line tools."""
    ap.add_argument("--league", default="nba", choices=sorted(LEAGUES), help="which league (default nba)")
