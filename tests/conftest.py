"""Offline harness: hashing embedder + on-disk Qdrant. Env is set BEFORE app modules import."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="raginabox-"))
os.environ.update(EMBED_BACKEND="fake", QDRANT_URL=str(TMP / "qdrant"), CORPUS_DIR=str(ROOT / "corpus"))
sys.path.insert(0, str(ROOT / "app"))

import rag  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from server import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ingested():
    rag.ingest()


@pytest.fixture
def api():
    return TestClient(app)


@pytest.fixture
def corpus_copy(tmp_path, monkeypatch):
    """Isolated corpus + collection so ingest tests can edit docs freely."""
    dst = tmp_path / "corpus"
    shutil.copytree(ROOT / "corpus", dst)
    monkeypatch.setattr(rag, "CORPUS", dst)
    monkeypatch.setattr(rag, "COLLECTION", "docs__iso_" + tmp_path.name.replace("-", "_"))
    return dst
