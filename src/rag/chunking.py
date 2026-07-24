def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks of `chunk_size` words.

    `overlap` words are shared between consecutive chunks so that context
    (e.g. a sentence split across a chunk boundary) isn't lost entirely at
    the seam.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap

    return chunks
