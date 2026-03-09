from dataclasses import dataclass


@dataclass
class ChunkCandidate:
    text: str
    page_from: int
    page_to: int
    token_count: int


def recursive_character_split(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end]
        if end < len(normalized):
            last_space = chunk.rfind(" ")
            if last_space > chunk_size // 2:
                end = start + last_space
                chunk = normalized[start:end]
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def split_pages_into_chunks(
    page_texts: list[tuple[int, str]], *, chunk_size: int, overlap: int
) -> list[ChunkCandidate]:
    results: list[ChunkCandidate] = []
    for page_number, page_text in page_texts:
        for part in recursive_character_split(page_text, chunk_size=chunk_size, overlap=overlap):
            results.append(
                ChunkCandidate(
                    text=part,
                    page_from=page_number,
                    page_to=page_number,
                    token_count=max(1, len(part.split())),
                )
            )
    return results
