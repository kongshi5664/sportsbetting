"""Shared-password sign-in for the desk.

Set TIPOFF_PASSWORD in .env and every /api call needs a signed session cookie, issued by
POST /api/login. Sessions last 30 days per device. Changing the password signs everyone out,
because each token is bound to a hash of the password it was issued under.

Without a password the desk only answers requests made directly on this computer; anything
arriving from another machine or through a tunnel is refused until a password is set.
"""
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

COOKIE = "tod_session"
SESSION_SECONDS = 30 * 24 * 3600
FAIL_WINDOW = 15 * 60
FAILS_PER_CLIENT = 8     # wrong guesses per device per 15 minutes
FAILS_OVERALL = 40       # across everyone, in case client addresses are spoofed

_fails: dict[str, list[float]] = {}
LOCAL = {"127.0.0.1", "::1", "localhost"}
FORWARD_HEADERS = ("x-forwarded-for", "cf-connecting-ip", "forwarded", "x-real-ip", "tailscale-funnel-request")


def password():
    return os.environ.get("TIPOFF_PASSWORD") or None


def _secret(root: Path) -> bytes:
    if os.environ.get("TIPOFF_SECRET"):
        return os.environ["TIPOFF_SECRET"].encode()
    path = root / "data" / ".session_secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode()


def _sign(root, msg: str) -> str:
    return hmac.new(_secret(root), msg.encode(), hashlib.sha256).hexdigest()


def _pw_tag() -> str:
    return hashlib.sha256((password() or "").encode()).hexdigest()[:16]


def issue(root) -> str:
    exp = str(int(time.time()) + SESSION_SECONDS)
    return f"{exp}.{_sign(root, exp + ':' + _pw_tag())}"


def valid(root, token) -> bool:
    if not token or "." not in token:
        return False
    exp, sig = token.split(".", 1)
    if not exp.isdigit() or int(exp) < time.time():
        return False
    return hmac.compare_digest(sig, _sign(root, exp + ":" + _pw_tag()))


def check(given: str) -> bool:
    pw = password()
    return bool(pw) and hmac.compare_digest(given.encode(), pw.encode())


def client_id(request) -> str:
    for h in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
        if request.headers.get(h):
            return request.headers[h].split(",")[0].strip()
    return request.client.host if request.client else "?"


def is_local(request) -> bool:
    """Made directly on this computer: loopback address and no proxy or tunnel in between."""
    host = request.client.host if request.client else ""
    return host in LOCAL and not any(h in request.headers for h in FORWARD_HEADERS)


def throttled(who: str) -> bool:
    cutoff = time.time() - FAIL_WINDOW
    for k in list(_fails):
        _fails[k] = [t for t in _fails[k] if t > cutoff]
    return len(_fails.get(who, [])) >= FAILS_PER_CLIENT or sum(map(len, _fails.values())) >= FAILS_OVERALL


def note_failure(who: str):
    _fails.setdefault(who, []).append(time.time())
