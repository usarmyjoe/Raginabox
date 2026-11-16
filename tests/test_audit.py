"""Can you reconstruct who did what, and who was refused?"""
from conftest import Q_RUNBOOK


def test_denials_are_logged(api, hdr, audit_events):
    api.post("/login", json={"user": "bob", "password": "wrong"})
    api.post("/admin/ingest", headers=hdr("bob"))
    api.get("/whoami", headers={"Authorization": "Bearer junk"})
    events = audit_events()
    assert any(e["event"] == "login_fail" and e["user"] == "bob" for e in events)
    assert any(e["event"] == "forbidden" and e["sub"] == "bob" for e in events)
    assert any(e["event"] == "auth_fail" for e in events)


def test_searches_log_who_and_which_docs(api, hdr, audit_events):
    api.get("/search", params={"q": Q_RUNBOOK}, headers=hdr("alice"))
    e = [x for x in audit_events() if x["event"] == "search" and x["sub"] == "alice"][-1]
    assert "restricted/incident-runbook.md" in e["docs"]


def test_audit_never_records_passwords_or_tokens(api, hdr, audit_events):
    api.post("/login", json={"user": "bob", "password": "super-secret-attempt"})
    api.get("/whoami", headers=hdr("bob"))
    blob = str(audit_events())
    assert "super-secret-attempt" not in blob and "Bearer" not in blob and "eyJ" not in blob
