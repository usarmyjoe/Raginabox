import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import rag

app = FastAPI(title="Raginabox")


class Ask(BaseModel):
    q: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/search")
def search(q: str):
    try:
        hits = rag.retrieve(q)
    except requests.RequestException:
        raise HTTPException(502, "backend unavailable")
    return [{"doc_id": h.payload["doc_id"], "heading": h.payload["heading"], "score": h.score,
             "text": h.payload["text"]} for h in hits]


@app.post("/ask")
def ask(body: Ask):
    try:
        hits = rag.retrieve(body.q)
        answer = rag.generate(body.q, hits)
    except requests.RequestException:
        raise HTTPException(502, "backend unavailable")
    return {"answer": answer, "sources": [h.payload["doc_id"] for h in hits]}


@app.post("/ingest")
def ingest():
    return rag.ingest()
