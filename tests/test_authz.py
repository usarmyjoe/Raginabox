"""AuthZ: what may you see / do? Identity is proven; now check entitlements."""
import json

from conftest import Q_NETNOTES, Q_PUBLIC, Q_RUNBOOK, USERS, USERS_FILE


def docs(api, hdr, user, q):
    r = api.get("/search", params={"q": q}, headers=hdr(user))
    assert r.status_code == 200
    return {h["doc_id"] for h in r.json()}


def test_public_user_sees_public(api, hdr):
    assert "public/vlan-basics.md" in docs(api, hdr, "bob", Q_PUBLIC)


def test_bob_never_sees_restricted(api, hdr):
    for q in (Q_RUNBOOK, Q_NETNOTES, "restricted", "10.20.99.0/24 sealed admin account"):
        assert not any(d.startswith("restricted/") for d in docs(api, hdr, "bob", q)), q


def test_clearance_level_separates_carol_from_alice(api, hdr):
    """Same group, different clearance: carol (1) gets the runbook (level 1) but not network notes (level 2)."""
    assert "restricted/incident-runbook.md" in docs(api, hdr, "carol", Q_RUNBOOK)
    assert "restricted/network-notes.md" not in docs(api, hdr, "carol", Q_NETNOTES)
    assert "restricted/network-notes.md" in docs(api, hdr, "alice", Q_NETNOTES)


def test_client_cannot_self_assert_entitlements(api, hdr):
    """Entitlements come from the server's user store, never from request params/headers/body."""
    r = api.get("/search", params={"q": Q_RUNBOOK, "groups": "restricted", "clearance": 9, "user": "alice"},
                headers={**hdr("bob"), "X-Groups": "restricted", "X-User": "alice"})
    assert not any(h["doc_id"].startswith("restricted/") for h in r.json())


def test_entitlement_change_is_immediate(api, hdr):
    """Server-side lookup: promote bob, his EXISTING token gains access on the next request."""
    h = hdr("bob")
    assert "restricted/incident-runbook.md" not in {x["doc_id"] for x in api.get("/search", params={"q": Q_RUNBOOK}, headers=h).json()}
    USERS_FILE.write_text(json.dumps({**USERS, "bob": {**USERS["bob"], "groups": ["public", "restricted"], "clearance": 1}}))
    assert "restricted/incident-runbook.md" in {x["doc_id"] for x in api.get("/search", params={"q": Q_RUNBOOK}, headers=h).json()}


def test_ask_sources_respect_acl(api, hdr):
    r = api.post("/ask", json={"q": Q_RUNBOOK}, headers=hdr("bob"))
    assert r.status_code == 200
    assert not any(s.startswith("restricted/") for s in r.json()["sources"])


def test_admin_endpoint_requires_admin_role(api, hdr):
    assert api.post("/admin/ingest").status_code == 401
    assert api.post("/admin/ingest", headers=hdr("bob")).status_code == 403
    assert api.post("/admin/ingest", headers=hdr("carol")).status_code == 403
    assert api.post("/admin/ingest", headers=hdr("alice")).status_code == 200
