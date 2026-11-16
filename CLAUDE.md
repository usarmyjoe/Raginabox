# Raginabox

A small RAG (retrieval-augmented generation) service used as a **practice lab for RAG security controls**. The RAG itself is intentionally minimal; do not spend effort on retrieval quality, performance or UI.

## Branches
- `main`: plain RAG. No auth, no ACLs, default Docker networking. Keep it that way.
- `security`: authN/authZ, ACL-aware retrieval, containment, audit, and a test for every control. Branch from `main`; rebase on `main` when the RAG core changes.

Rule: anything security-specific lives on `security` only. If a change is useful to both, make it on `main` first, then rebase `security`.

## Commands
- Tests (offline, ~1 s): `pip install -r requirements-dev.txt && pytest -q`
- Stack: see README. `EMBED_BACKEND=fake` swaps in a hashing embedder and `QDRANT_URL=<path>` uses on-disk Qdrant, which is how tests run without Docker or models.

## Working style
- Terse. Working code and tests over explanation. Say when unsure instead of guessing.
- On `security`, treat controls as test-driven: write the failing test first, then the control.
- Mutation-check security tests: break a control on purpose and confirm a test fails. Layers must be tested in isolation, because defense in depth can mask a broken layer.

## Ideas queued for the `security` branch
- Login throttling and lockout; swap the local JWT issuer for Keycloak OIDC (JWKS verification)
- Per-document `allow:` lists and a `tenant` field
- Reindex when an ACL changes without a content change (not handled today)
- Close the `app` egress gap (proxy with an allowlist); pin images by digest
- Prompt-injection exercises: poisoned doc, markdown-image exfiltration
- Never verified live: the compose stack and `scripts/verify-containment.sh` were authored without a Docker daemon.
