import pytest

import rag

PROSE = " ".join(f"Sentence number {i} talks about topic {i}." for i in range(1, 21))


@pytest.fixture
def small(monkeypatch):
    monkeypatch.setattr(rag, "MAX_CHARS", 140)
    monkeypatch.setattr(rag, "OVERLAP_UNITS", 1)


def test_every_chunk_fits(small):
    for c in rag._windows(PROSE):
        assert len(c) <= rag.MAX_CHARS


def test_no_mid_sentence_cuts(small):
    chunks = rag._windows(PROSE)
    assert len(chunks) > 1
    for c in chunks:
        assert c[0].isupper() and c.rstrip().endswith(".")
    for i in range(1, 21):
        assert any(f"Sentence number {i} talks about topic {i}." in c for c in chunks)


def test_overlap_repeats_last_unit(small):
    chunks = rag._windows(PROSE)
    for a, b in zip(chunks, chunks[1:]):
        assert a.splitlines()[-1] == b.splitlines()[0]


def test_zero_overlap_means_no_repeats(small, monkeypatch):
    monkeypatch.setattr(rag, "OVERLAP_UNITS", 0)
    lines = [ln for c in rag._windows(PROSE) for ln in c.splitlines()]
    assert len(lines) == len(set(lines)) == 20


def test_code_fence_is_kept_whole(small):
    code = "```\nline one\n\nline two after a blank line\n```"
    chunks = rag._windows(f"Intro sentence here. {code}\n\nOutro sentence here.")
    assert any(code in c for c in chunks)


def test_list_block_is_one_unit(small):
    lst = "- First item. Has two sentences.\n- Second item. Also two sentences."
    assert any(lst in c for c in rag._windows(f"Before the list.\n\n{lst}\n\nAfter the list."))


def test_oversized_unit_is_hard_split(small):
    chunks = rag._windows("x" * 500)
    assert len(chunks) == 4 and all(len(c) <= rag.MAX_CHARS for c in chunks)


def test_lowercase_after_abbreviation_is_not_a_boundary():
    assert rag._units("Use e.g. the router for this.") == ["Use e.g. the router for this."]


@pytest.mark.xfail(strict=True, reason="known limit of the regex splitter: capitalised word after an abbreviation")
def test_abbreviation_before_name_is_not_a_boundary():
    assert rag._units("Ask Dr. Smith about it.") == ["Ask Dr. Smith about it."]


def test_overlap_is_dropped_when_it_would_overflow(small):
    """Units near MAX_CHARS: carrying the tail would push the chunk past the limit, so it must be skipped."""
    big = " ".join(("Word" * 24) + "." for _ in range(6))  # 97-char sentences, MAX 140
    chunks = rag._windows(big)
    assert len(chunks) == 6 and all(len(c) <= rag.MAX_CHARS for c in chunks)
