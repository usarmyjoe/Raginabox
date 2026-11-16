def test_health(api):
    assert api.get("/health").json() == {"ok": True}


def test_search_finds_the_right_doc(api):
    hits = api.get("/search", params={"q": "why put IoT devices on separate VLANs"}).json()
    assert hits[0]["doc_id"] == "vlan-basics.md"


def test_ask_returns_answer_and_sources(api):
    r = api.post("/ask", json={"q": "What does the 3-2-1 backup rule mean?"}).json()
    assert "backups.md" in r["sources"] and r["answer"]


def test_ingest_endpoint_is_idempotent(api):
    s = api.post("/ingest").json()
    assert s["added"] == 0 and s["updated"] == 0
