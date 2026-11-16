"""AuthN: password check + signed token. AuthZ state (groups/clearance/roles) is looked up
server-side on EVERY request, so editing users.json takes effect immediately (no stale claims)."""
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

import jwt  # PyJWT

USERS_FILE = Path(os.getenv("USERS_FILE", "/users.json"))
SECRET = os.environ["JWT_SECRET"]  # no default on purpose: fail fast if unset
ISS = AUD = "mini-rag"
TTL = int(os.getenv("TOKEN_TTL_SECONDS", "900"))
ITER = int(os.getenv("PBKDF2_ITER", "200000"))


@dataclass(frozen=True)
class Principal:
    sub: str
    groups: tuple
    clearance: int
    roles: tuple


def hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2_sha256${ITER}${salt.hex()}${h.hex()}"


def _check_pw(pw: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        cand = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
    except ValueError:
        return False
    return hmac.compare_digest(cand.hex(), h)


def load_users() -> dict:
    return json.loads(USERS_FILE.read_text())


_DUMMY = hash_pw("dummy")  # unknown users cost the same time as wrong passwords


def authenticate(user: str, pw: str) -> bool:
    u = load_users().get(user)
    ok = _check_pw(pw, u["pw"] if u else _DUMMY)
    return bool(u) and not u.get("disabled", False) and ok


def issue_token(sub: str) -> str:
    now = int(time.time())
    claims = {"sub": sub, "iss": ISS, "aud": AUD, "iat": now, "exp": now + TTL}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def verify_token(token: str) -> Principal:
    claims = jwt.decode(
        token, SECRET, algorithms=["HS256"], issuer=ISS, audience=AUD,
        options={"require": ["exp", "iat", "sub"]},
    )
    u = load_users().get(claims["sub"])
    if not u or u.get("disabled", False):
        raise jwt.InvalidTokenError("unknown or disabled user")
    return Principal(claims["sub"], tuple(u["groups"]), int(u["clearance"]), tuple(u.get("roles", [])))
