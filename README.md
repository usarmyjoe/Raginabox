# Raginabox

A deliberately small RAG (retrieval-augmented generation) service you can run on a laptop. Markdown in, questions out.

FastAPI + Qdrant (vector store) + Ollama (local embedding and chat models, CPU is fine). Under 200 lines of RAG code in `app/rag.py`.

## Branches

| Branch | What it is |
|---|---|
| `main` | The plain RAG. No auth, no access control, default Docker networking. |
| `security` | Same RAG plus authN/authZ, ACL-aware retrieval, containment, audit logging and a test suite for each. See `git diff main..security`. |

## Quick start

```sh
pip install -r requirements-dev.txt
pytest -q                                  # offline: hashing embedder, on-disk Qdrant, ~1 s

docker compose up -d ollama
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull llama3.2:1b
docker compose up -d --build
docker compose exec app python cli.py ingest

curl -s "localhost:8000/search?q=quarantine+VLAN"
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{"q":"What does 3-2-1 mean for backups?"}'
```

Drop `.md` or `.txt` files in `corpus/` and re-run `ingest`. It only re-embeds what changed and removes what you deleted.

## How it works

1. **Chunk:** split on markdown headings, then into windows of `CHUNK_CHARS`. Every chunk is prefixed with `file > heading path` (the breadcrumb).
2. **Embed:** Ollama `/api/embed`. Documents and queries use different prefixes (a `nomic-embed-text` convention).
3. **Store:** Qdrant, one collection per embedding model, so swapping models never mixes vector spaces.
4. **Retrieve:** top-k cosine similarity.
5. **Generate:** the chunks go into a numbered context, and the model must cite `[n]` or say it doesn't know.

Ingest is idempotent. Edited docs are deleted and re-added, so a shrinking doc leaves no stale chunks.

## Layout

```
app/rag.py      core pipeline
app/server.py   HTTP API: /search /ask /ingest /health
app/cli.py      ingest | wipe
corpus/         your documents
tests/          offline tests
```
