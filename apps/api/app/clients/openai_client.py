import asyncio
import json
from pathlib import Path

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.settings import settings
from app.schemas.metadata import ExtractedMetadata


class OpenAIClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        root = Path(__file__).resolve().parents[4]
        self._extraction_prompt = (root / "docs" / "prompts" / "extraction" / "v1.txt").read_text(encoding="utf-8")
        self._rag_prompt = (root / "docs" / "prompts" / "rag" / "v1.txt").read_text(encoding="utf-8")

    async def _retry(self, fn):
        delay = 1.0
        last_exc: Exception | None = None
        for _ in range(5):
            try:
                return await fn()
            except (RateLimitError, APITimeoutError, APIError) as exc:
                last_exc = exc
                await asyncio.sleep(delay)
                delay *= 2
        if last_exc is None:
            raise RuntimeError("retry loop ended without exception or result")
        raise last_exc

    async def extract_metadata(self, text: str) -> ExtractedMetadata:
        async def _call():
            return await self._client.chat.completions.create(
                model=settings.openai_metadata_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self._extraction_prompt},
                    {"role": "user", "content": text[:12000]},
                ],
            )

        completion = await self._retry(_call)
        content = completion.choices[0].message.content or "{}"
        data = json.loads(content)
        return ExtractedMetadata.model_validate(data)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        async def _call():
            return await self._client.embeddings.create(model=settings.openai_embedding_model, input=texts)

        response = await self._retry(_call)
        return [item.embedding for item in response.data]

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query])
        return vectors[0]

    async def answer_with_context(self, *, query: str, contexts: list[str]) -> str:
        context_block = "\n\n".join(contexts)

        async def _call():
            return await self._client.chat.completions.create(
                model=settings.openai_metadata_model,
                messages=[
                    {"role": "system", "content": self._rag_prompt},
                    {
                        "role": "user",
                        "content": f"Sporsmal: {query}\n\nKontekst:\n{context_block}",
                    },
                ],
            )

        completion = await self._retry(_call)
        return completion.choices[0].message.content or ""
