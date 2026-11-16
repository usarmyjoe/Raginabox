"""AuthN: who are you? Every case here must end in 401."""
import time

import jwt

import auth
from conftest import USERS, USERS_FILE, b64
import json


def test_no_token(api):
    assert api.get("/whoami").status_code == 401


def test_garbage_token(api):
    assert api.get("/whoami", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401


def test_wrong_scheme(api, token):
    assert api.get("/whoami", headers={"Authorization": f"Basic {token('bob')}"}).status_code == 401


def test_tampered_payload_keeps_old_signature(api, token):
    """Take bob's token, swap the subject to alice, keep bob's signature."""
    h, _, sig = token("bob").split(".")
    forged_payload = b64({"sub": "alice", "iss": auth.ISS, "aud": auth.AUD, "iat": int(time.time()),
                          "exp": int(time.time()) + 900})
    assert api.get("/whoami", headers={"Authorization": f"Bearer {h}.{forged_payload}.{sig}"}).status_code == 401


def test_alg_none_rejected(api):
    now = int(time.time())
    tok = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'alice', 'iss': auth.ISS, 'aud': auth.AUD, 'iat': now, 'exp': now + 900})}."
    assert api.get("/whoami", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_wrong_key_rejected(api):
    now = int(time.time())
    tok = jwt.encode({"sub": "alice", "iss": auth.ISS, "aud": auth.AUD, "iat": now, "exp": now + 900},
                     "attacker-key-" + "y" * 40, algorithm="HS256")
    assert api.get("/whoami", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_expired_rejected(api):
    now = int(time.time())
    tok = jwt.encode({"sub": "bob", "iss": auth.ISS, "aud": auth.AUD, "iat": now - 2000, "exp": now - 1000},
                     auth.SECRET, algorithm="HS256")
    assert api.get("/whoami", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_wrong_audience_rejected(api):
    now = int(time.time())
    tok = jwt.encode({"sub": "bob", "iss": auth.ISS, "aud": "some-other-service", "iat": now, "exp": now + 900},
                     auth.SECRET, algorithm="HS256")
    assert api.get("/whoami", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_removed_user_token_dies_immediately(api, token):
    tok = token("bob")
    assert api.get("/whoami", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    USERS_FILE.write_text(json.dumps({k: v for k, v in USERS.items() if k != "bob"}))
    assert api.get("/whoami", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_disabled_user_cannot_login_or_use_token(api, token):
    tok = token("bob")
    USERS_FILE.write_text(json.dumps({**USERS, "bob": {**USERS["bob"], "disabled": True}}))
    assert api.post("/login", json={"user": "bob", "password": "bob-pw"}).status_code == 401
    assert api.get("/whoami", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_login_wrong_password(api):
    assert api.post("/login", json={"user": "bob", "password": "nope"}).status_code == 401


def test_login_unknown_user_same_error(api):
    a = api.post("/login", json={"user": "ghost", "password": "x"})
    b = api.post("/login", json={"user": "bob", "password": "x"})
    assert (a.status_code, a.json()) == (b.status_code, b.json())  # no user enumeration


def test_login_then_use_token(api):
    r = api.post("/login", json={"user": "bob", "password": "bob-pw"})
    assert r.status_code == 200
    me = api.get("/whoami", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.json()["sub"] == "bob"
