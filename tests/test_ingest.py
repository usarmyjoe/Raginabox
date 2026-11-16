import rag


def texts(q, doc=None):
    return " ".join(h.payload["text"] for h in rag.retrieve(q, k=20) if doc is None or h.payload["doc_id"] == doc)


def test_first_ingest_then_noop(corpus_copy):
    assert rag.ingest()["added"] == 4
    assert rag.ingest() == {"added": 0, "updated": 0, "removed": 0, "unchanged": 4}


def test_edited_doc_has_no_stale_chunks(corpus_copy):
    """Doc SHRINKS: chunk ids from the old version would linger unless the old version is deleted first."""
    rag.ingest()
    f = corpus_copy / "backups.md"
    f.write_text(f.read_text().split("## Retention")[0].replace("3 copies", "three zebra copies"))
    assert rag.ingest()["updated"] == 1
    t = texts("snapshots retention daily weekly monthly zebra", "backups.md")
    assert "zebra" in t and "monthly for 12 months" not in t


def test_deleted_doc_is_removed_from_index(corpus_copy):
    rag.ingest()
    (corpus_copy / "network-notes.md").unlink()
    assert rag.ingest()["removed"] == 1
    assert "network-notes.md" not in {h.payload["doc_id"] for h in rag.retrieve("quarantine VLAN address range", k=20)}


def test_chunks_carry_breadcrumbs(corpus_copy):
    rag.ingest()
    h = rag.retrieve("mDNS reflector Avahi", k=5)[0]
    assert h.payload["text"].startswith("vlan-basics.md > VLAN basics > Discovery across VLANs")


def test_fenced_code_hashes_are_not_headings():
    chunks = rag.chunk_doc("x.md", "# Title\n\n```\n# not a heading\n```\n\n## Real\n\nbody")
    assert [c["heading"] for c in chunks] == ["Title", "Title > Real"]
