import jwt
import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

import auth
import rag

app = FastAPI(title="mini-rag")


class Login(BaseModel):
    user: str
    password: str


class Ask(BaseModel):
    q: str


def principal(authorization: str = Header(default="")) -> auth.Principal:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    try:
        return auth.verify_token(token)
    except jwt.PyJWTError as e:
        rag.audit(event="auth_fail", reason=type(e).__name__)
        raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})


def require_role(role: str):
    def dep(p: auth.Principal = Depends(principal)):
        if role not in p.roles:
            rag.audit(event="forbidden", sub=p.sub, need=role)
            raise HTTPException(403, "forbidden")
        return p
    return dep


@app.post("/login")
def login(body: Login):
    if not auth.authenticate(body.user, body.password):
        rag.audit(event="login_fail", user=body.user)
        raise HTTPException(401, "bad credentials")
    rag.audit(event="login", user=body.user)
    return {"token": auth.issue_token(body.user)}


@app.get("/whoami")
def whoami(p: auth.Principal = Depends(principal)):
    return p


@app.get("/search")
def search(q: str, p: auth.Principal = Depends(principal)):
    try:
        hits = rag.retrieve(p, q)
    except requests.RequestException:
        raise HTTPException(502, "backend unavailable")
    rag.audit(event="search", sub=p.sub, q=q, docs=[h.payload["doc_id"] for h in hits])
    return [{"doc_id": h.payload["doc_id"], "heading": h.payload["heading"], "score": h.score,
             "text": h.payload["text"]} for h in hits]


@app.post("/ask")
def ask(body: Ask, p: auth.Principal = Depends(principal)):
    try:
        hits = rag.retrieve(p, body.q)
        answer = rag.generate(body.q, hits)
    except requests.RequestException:
        raise HTTPException(502, "backend unavailable")
    docs = [h.payload["doc_id"] for h in hits]
    rag.audit(event="ask", sub=p.sub, q=body.q, docs=docs)
    return {"answer": answer, "sources": docs}


@app.post("/admin/ingest")
def admin_ingest(p: auth.Principal = Depends(require_role("admin"))):
    stats = rag.ingest()
    rag.audit(event="ingest", sub=p.sub, **stats)
    return stats
