"""Plain RAG core: chunk -> embed -> store -> retrieve -> generate. No auth, no access control.
(The `security` branch layers those on; see README.)"""
import hashlib
import os
import re
import uuid
from pathlib import Path

import requests
from qdrant_client import QdrantClient, models

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")  # http(s) URL, or a local path (tests)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:1b")
BACKEND = os.getenv("EMBED_BACKEND", "ollama")  # "fake" = offline hashing embedder for tests
CORPUS = Path(os.getenv("CORPUS_DIR", "/corpus"))
MAX_CHARS = int(os.getenv("CHUNK_CHARS", "1200"))
OVERLAP_UNITS = int(os.getenv("CHUNK_OVERLAP_UNITS", "1"))  # sentences/blocks repeated at the start of the next chunk
TOP_K = int(os.getenv("TOP_K", "5"))
COLLECTION = "docs__" + ("fake" if BACKEND == "fake" else re.sub(r"\W+", "_", EMBED_MODEL))

SYSTEM = (
    "Answer using ONLY the numbered context. Cite sources like [1]. "
    "If the context does not contain the answer, say you don't know."
)

_client = None


def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL) if QDRANT_URL.startswith("http") else QdrantClient(path=QDRANT_URL)
    return _client


# ---------- embedding ----------
def _fake_vec(text: str, dim: int = 256) -> list:
    v = [0.0] * dim
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / n for x in v]


def embed(texts: list, query: bool = False) -> list:
    if BACKEND == "fake":
        return [_fake_vec(t) for t in texts]
    prefix = "search_query: " if query else "search_document: "  # nomic-embed-text convention
    out = []
    for i in range(0, len(texts), 16):
        r = requests.post(f"{OLLAMA_URL}/api/embed",
                          json={"model": EMBED_MODEL, "input": [prefix + t for t in texts[i:i + 16]]},
                          timeout=300)
        r.raise_for_status()
        out += r.json()["embeddings"]
    return out


# ---------- chunking ----------
_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")


def _sections(text: str):
    """Split on markdown headings (ignoring ``` fences); yield (heading_path, body)."""
    stack, buf, out, fence = [], [], [], False

    def flush():
        body = "\n".join(buf).strip()
        if body:
            out.append((" > ".join(stack), body))

    for line in text.splitlines():
        if line.strip().startswith("```"):
            fence = not fence
        m = None if fence else _HEAD.match(line)
        if m:
            flush()
            buf.clear()
            stack[:] = stack[:len(m.group(1)) - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()
    return out


_SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(\[])')  # known limit: splits after "Dr." before a name
_ATOMIC = re.compile(r"^\s*(```|[-*+]\s|\d+[.)]\s|\|)")  # code, list and table blocks stay whole


def _units(body: str) -> list:
    """Smallest pieces we never cut: a sentence, a fenced code block, or a list/table block."""
    units = []
    for i, seg in enumerate(re.split(r"(```.*?```)", body, flags=re.S)):
        if i % 2:  # fenced code
            parts = [seg.strip()]
        else:
            parts = []
            for block in re.split(r"\n\s*\n", seg):
                block = block.strip()
                if block:
                    parts += [block] if _ATOMIC.match(block) else [s.strip() for s in _SENT.split(block) if s.strip()]
        for p in parts:
            units += [p[j:j + MAX_CHARS] for j in range(0, len(p), MAX_CHARS)]  # oversized unit: hard split
    return units


def _windows(body: str) -> list:
    """Pack whole units up to MAX_CHARS; each new chunk starts with the last OVERLAP_UNITS of the previous one."""
    chunks, cur = [], []
    for u in _units(body):
        if cur and sum(len(x) + 1 for x in cur) + len(u) > MAX_CHARS:
            chunks.append("\n".join(cur))
            tail = cur[-OVERLAP_UNITS:] if OVERLAP_UNITS else []
            cur = tail if sum(len(x) + 1 for x in tail) + len(u) <= MAX_CHARS else []
        cur = cur + [u]
    if cur:
        chunks.append("\n".join(cur))
    return chunks or [body]


def chunk_doc(doc_id: str, raw: str) -> list:
    h = hashlib.sha256(raw.encode()).hexdigest()
    chunks = []
    for heading, body in _sections(raw):
        for piece in _windows(body):
            crumb = f"{doc_id} > {heading}" if heading else doc_id  # breadcrumb helps retrieval
            chunks.append({"doc_id": doc_id, "doc_hash": h, "heading": heading, "text": f"{crumb}\n\n{piece}"})
    return chunks


# ---------- index management ----------
def _ensure_collection(dim: int):
    c = client()
    if not c.collection_exists(COLLECTION):
        c.create_collection(COLLECTION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))


def _indexed() -> dict:
    c, docs, offset = client(), {}, None
    if not c.collection_exists(COLLECTION):
        return docs
    while True:
        pts, offset = c.scroll(COLLECTION, limit=512, offset=offset, with_payload=["doc_id", "doc_hash"])
        for p in pts:
            docs[p.payload["doc_id"]] = p.payload["doc_hash"]
        if offset is None:
            return docs


def _delete(doc_id: str):
    client().delete(COLLECTION, points_selector=models.FilterSelector(filter=models.Filter(
        must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])))


def ingest() -> dict:
    """Idempotent: skips unchanged docs, replaces edited ones (no stale chunks), drops deleted ones."""
    docs = {p.relative_to(CORPUS).as_posix(): p for p in sorted(CORPUS.rglob("*")) if p.suffix in {".md", ".txt"}}
    have = _indexed()
    stats = {"added": 0, "updated": 0, "removed": 0, "unchanged": 0}
    for doc_id in set(have) - set(docs):
        _delete(doc_id)
        stats["removed"] += 1
    for doc_id, path in docs.items():
        chunks = chunk_doc(doc_id, path.read_text(encoding="utf-8"))
        if chunks and have.get(doc_id) == chunks[0]["doc_hash"]:
            stats["unchanged"] += 1
            continue
        if doc_id in have:
            _delete(doc_id)
            stats["updated"] += 1
        else:
            stats["added"] += 1
        if not chunks:
            continue
        vecs = embed([c["text"] for c in chunks])
        _ensure_collection(len(vecs[0]))
        client().upsert(COLLECTION, points=[
            models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{i}")), vector=v, payload=c)
            for i, (c, v) in enumerate(zip(chunks, vecs))])
    return stats


def wipe():
    client().delete_collection(COLLECTION)


# ---------- retrieval + generation ----------
def retrieve(query: str, k: int = TOP_K) -> list:
    if not client().collection_exists(COLLECTION):
        return []
    return client().query_points(COLLECTION, query=embed([query], query=True)[0],
                                 limit=k, with_payload=True).points


def generate(query: str, hits: list) -> str:
    if BACKEND == "fake":
        return "(fake backend: no LLM)"
    ctx = "\n\n".join(f"[{i + 1}] {h.payload['text']}" for i, h in enumerate(hits))
    r = requests.post(f"{OLLAMA_URL}/api/chat", timeout=600, json={
        "model": LLM_MODEL, "stream": False, "options": {"temperature": 0.1},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {query}"}]})
    r.raise_for_status()
    return r.json()["message"]["content"]
