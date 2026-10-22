"""A small shared status file, so the desk can show what the background jobs are doing:
the paper trader's heartbeat and the Odds API credits left after the latest pull by any process."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "status.json"


def path():
    return Path(os.environ.get("TIPOFF_STATUS") or DEFAULT)  # tests point this elsewhere


def read():
    try:
        return json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update(**kv):
    try:
        s = read()
        s.update(kv)
        tmp = path().with_suffix(".tmp")
        tmp.write_text(json.dumps(s), encoding="utf-8")
        os.replace(tmp, path())
    except OSError:
        pass  # status is a convenience; never let it break a pull or the trader


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
