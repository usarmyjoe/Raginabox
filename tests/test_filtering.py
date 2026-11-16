"""Retrieval-layer controls, tested without HTTP: the filter AND the post-filter safety net."""
import pytest

import rag
from conftest import Q_NETNOTES, Q_PUBLIC, Q_RUNBOOK, principal

QUERIES = [Q_PUBLIC, Q_RUNBOOK, Q_NETNOTES, "backup restore testing", "firewall exceptions NAS port 445",
           "sealed admin account", "mDNS across VLANs", "retention snapshots", "addressing plan", "golden image"]


@pytest.mark.parametrize("user", ["alice", "carol", "bob"])
def test_every_hit_is_entitled(user):
    """Property: for any query, nothing outside the user's groups/clearance is ever returned."""
    p = principal(user)
    for q in QUERIES:
        for h in rag.retrieve(p, q, k=20):
            assert h.payload["group"] in p.groups
            assert h.payload["level"] <= p.clearance


def test_user_with_no_groups_gets_nothing():
    from auth import Principal
    assert rag.retrieve(Principal("nobody", (), 99, ()), Q_PUBLIC) == []


def test_post_filter_catches_a_broken_query_filter(monkeypatch, audit_events):
    """Simulate the classic bug: someone 'simplifies' build_filter and drops the ACL. The output re-check must hold."""
    monkeypatch.setattr(rag, "build_filter", lambda p: None)
    hits = rag.retrieve(principal("bob"), Q_RUNBOOK, k=20)
    assert not any(h.payload["group"] == "restricted" for h in hits)
    assert any(e["event"] == "acl_violation_after_filter" and e["sub"] == "bob" for e in audit_events())


@pytest.mark.parametrize("user", ["alice", "carol", "bob"])
def test_query_filter_alone_is_sufficient(monkeypatch, user):
    """Layer 1 on its own: with the post-check neutered, the query filter must still enforce everything.
    (Without this test, the post-check would silently mask a broken filter.)"""
    monkeypatch.setattr(rag, "_allowed", lambda p, payload: True)
    p = principal(user)
    for q in QUERIES:
        for h in rag.retrieve(p, q, k=20):
            assert h.payload["group"] in p.groups and h.payload["level"] <= p.clearance


def test_group_filter_alone_blocks_level_zero_restricted_doc(corpus_copy, monkeypatch):
    """Isolates the GROUP clause: a restricted doc with level 0 passes the clearance test, so only the group filter stops bob."""
    (corpus_copy / "restricted" / "open-level.md").write_text("# Open level\n\nplutonium inventory spreadsheet location")
    rag.ingest()
    monkeypatch.setattr(rag, "_allowed", lambda p, payload: True)
    hits = rag.retrieve(principal("bob"), "plutonium inventory spreadsheet", k=20)
    assert not any("open-level.md" in h.payload["doc_id"] for h in hits)
