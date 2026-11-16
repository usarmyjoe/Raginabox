"""Index hygiene is a security control too: stale chunks = data that should be gone but is still retrievable."""
import rag
from conftest import principal

ALICE = principal("alice")


def doc_ids(q):
    return {h.payload["doc_id"] for h in rag.retrieve(ALICE, q, k=20)}


def test_first_ingest_then_noop(corpus_copy):
    assert rag.ingest()["added"] == 4
    assert rag.ingest() == {"added": 0, "updated": 0, "removed": 0, "unchanged": 4}


def test_edited_doc_has_no_stale_chunks(corpus_copy):
    """Doc SHRINKS: chunk ids from the old version would linger unless the old version is deleted first."""
    rag.ingest()
    f = corpus_copy / "public" / "backups.md"
    f.write_text(f.read_text().split("## Retention")[0].replace("3 copies", "three zebra copies"))
    assert rag.ingest()["updated"] == 1
    texts = " ".join(h.payload["text"] for h in rag.retrieve(ALICE, "snapshots retention daily weekly monthly zebra", k=20)
                     if h.payload["doc_id"] == "public/backups.md")
    assert "zebra" in texts and "monthly for 12 months" not in texts


def test_deleted_doc_is_removed_from_index(corpus_copy):
    rag.ingest()
    (corpus_copy / "restricted" / "network-notes.md").unlink()
    assert rag.ingest()["removed"] == 1
    assert "restricted/network-notes.md" not in doc_ids("quarantine VLAN address range 10.20.99.0/24")


def test_acl_metadata_comes_from_folder_and_frontmatter(corpus_copy):
    rag.ingest()
    meta = {h.payload["doc_id"]: (h.payload["group"], h.payload["level"])
            for q in ("quarantine VLAN", "backup restore", "break-glass") for h in rag.retrieve(ALICE, q, k=20)}
    assert meta["restricted/network-notes.md"] == ("restricted", 2)
    assert meta["restricted/incident-runbook.md"] == ("restricted", 1)
    assert meta["public/backups.md"] == ("public", 0)


def test_new_doc_without_frontmatter_defaults_to_level_zero_in_its_folder(corpus_copy):
    """Safe-default question: an unlabeled file in restricted/ must NOT become public."""
    (corpus_copy / "restricted" / "new.md").write_text("# New\n\nplutonium inventory spreadsheet location")
    rag.ingest()
    hit = [h for h in rag.retrieve(ALICE, "plutonium inventory spreadsheet", k=20) if h.payload["doc_id"].endswith("new.md")][0]
    assert hit.payload["group"] == "restricted"          # group still protects it
    from conftest import principal as pr
    assert not [h for h in rag.retrieve(pr("bob"), "plutonium inventory spreadsheet", k=20) if "new.md" in h.payload["doc_id"]]


def test_chunks_carry_breadcrumbs(corpus_copy):
    rag.ingest()
    h = rag.retrieve(ALICE, "mDNS reflector Avahi", k=5)[0]
    assert h.payload["text"].startswith("public/vlan-basics.md > VLAN basics > Discovery across VLANs")
