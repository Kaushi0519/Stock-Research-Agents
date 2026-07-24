import pytest

from src.rag.chunking import chunk_text


def test_chunk_text_empty_string():
    assert chunk_text("") == []


def test_chunk_text_short_text_single_chunk():
    text = "This is a short piece of text."
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_splits_long_text_with_overlap():
    words = [f"word{i}" for i in range(500)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=200, overlap=40)

    assert len(chunks) == 3
    assert chunks[0].split()[0] == "word0"
    assert chunks[0].split()[-1] == "word199"
    assert chunks[1].split()[0] == "word160"
    assert chunks[0].split()[-40:] == chunks[1].split()[:40]


def test_chunk_text_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("some text here", chunk_size=10, overlap=10)
