"""Test harness: offline embedder, local Qdrant, throwaway users. Env is set BEFORE app modules import."""
import base64
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="minirag-"))
os.environ.update(
    EMBED_BACKEND="fake",
    QDRANT_URL=str(TMP / "qdrant"),
    QDRANT_API_KEY="",
    JWT_SECRET="test-secret-" + "x" * 40,
    PBKDF2_ITER="1000",
    USERS_FILE=str(TMP / "users.json"),
    CORPUS_DIR=str(ROOT / "corpus"),
    AUDIT_LOG=str(TMP / "audit.jsonl"),
)
sys.path.insert(0, str(ROOT / "app"))

import auth  # noqa: E402
import rag  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from server import app  # noqa: E402

USERS = {
    "alice": {"pw": auth.hash_pw("alice-pw"), "groups": ["public", "restricted"], "clearance": 2, "roles": ["admin"]},
    "carol": {"pw": auth.hash_pw("carol-pw"), "groups": ["public", "restricted"], "clearance": 1, "roles": []},
    "bob": {"pw": auth.hash_pw("bob-pw"), "groups": ["public"], "clearance": 0, "roles": []},
}
USERS_FILE = TMP / "users.json"
USERS_FILE.write_text(json.dumps(USERS))

# queries that should land on specific docs
Q_RUNBOOK = "break-glass admin account when the identity provider is down"
Q_NETNOTES = "quarantine VLAN address range 10.20.99.0/24"
Q_PUBLIC = "why put IoT devices on separate VLANs"


def b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def principal(name: str) -> auth.Principal:
    u = USERS[name]
    return auth.Principal(name, tuple(u["groups"]), u["clearance"], tuple(u["roles"]))


@pytest.fixture(scope="session", autouse=True)
def _ingested():
    rag.ingest()


@pytest.fixture(autouse=True)
def _restore_users():
    yield
    USERS_FILE.write_text(json.dumps(USERS))  # tests may edit users.json


@pytest.fixture
def api():
    return TestClient(app)


@pytest.fixture
def token():
    return auth.issue_token


@pytest.fixture
def hdr(token):
    return lambda name: {"Authorization": f"Bearer {token(name)}"}


@pytest.fixture
def audit_events():
    def read():
        p = Path(os.environ["AUDIT_LOG"])
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []
    return read


@pytest.fixture
def corpus_copy(tmp_path, monkeypatch):
    """Isolated corpus + collection so ingest tests can edit docs freely."""
    dst = tmp_path / "corpus"
    shutil.copytree(ROOT / "corpus", dst)
    monkeypatch.setattr(rag, "CORPUS", dst)
    monkeypatch.setattr(rag, "COLLECTION", "docs__iso_" + tmp_path.name.replace("-", "_"))
    return dst
