import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from app.core.db import get_db_pool
from app.core.settings import settings
from app.schemas.documents import DocumentListItem, DocumentStatus, MetadataResponse, SearchResult


class DocumentRepository:
    @dataclass
    class ChunkRow:
        text: str
        embedding: list[float]
        page_from: int
        page_to: int
        token_count: int

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{value:.8f}" for value in values) + "]"

    async def create_document(
        self,
        *,
        tenant_id: str,
        user_id: str,
        storage_path: str,
        file_name: str,
        mime_type: str,
        file_size: int,
        status: DocumentStatus = DocumentStatus.PENDING,
    ) -> UUID:
        pool = get_db_pool()
        query = """
        insert into documents (
          tenant_id, user_id, file_name, mime_type, file_size, storage_bucket, storage_path, status
        )
        values ($1, $2::uuid, $3, $4, $5, $6, $7, $8::document_status)
        returning id
        """
        async with pool.acquire() as conn:
            document_id = await conn.fetchval(
                query,
                tenant_id,
                user_id,
                file_name,
                mime_type,
                file_size,
                settings.supabase_storage_bucket,
                storage_path,
                status.value,
            )
            return UUID(str(document_id))

    async def confirm_upload(self, *, tenant_id: str, document_id: UUID) -> None:
        pool = get_db_pool()
        query = """
        update documents
        set status = 'UPLOADED',
            uploaded_at = now(),
            updated_at = now()
        where id = $1 and tenant_id = $2
        """
        async with pool.acquire() as conn:
            await conn.execute(query, document_id, tenant_id)

    async def set_status(self, *, tenant_id: str, document_id: UUID, status: DocumentStatus) -> None:
        pool = get_db_pool()
        query = """
        update documents
        set status = $1::document_status,
            processing_started_at = case when $1::text = 'PROCESSING' then now() else processing_started_at end,
            processing_completed_at = case when $1::text in ('COMPLETED','FAILED') then now() else processing_completed_at end,
            updated_at = now()
        where id = $2 and tenant_id = $3
        """
        async with pool.acquire() as conn:
            await conn.execute(query, status.value, document_id, tenant_id)

    async def add_processing_event(
        self,
        *,
        tenant_id: str,
        document_id: UUID,
        phase: str,
        status: str,
        message: str | None = None,
        payload: dict | None = None,
    ) -> None:
        pool = get_db_pool()
        query = """
        insert into document_processing_events (document_id, tenant_id, phase, status, message, payload)
        values ($1, $2, $3, $4, $5, $6::jsonb)
        """
        payload_json = json.dumps(payload) if payload is not None else None
        async with pool.acquire() as conn:
            await conn.execute(query, document_id, tenant_id, phase, status, message, payload_json)

    async def set_failed(
        self,
        *,
        tenant_id: str,
        document_id: UUID,
        last_error: str,
        error_code: str | None = None,
    ) -> None:
        pool = get_db_pool()
        query = """
        update documents
        set status = 'FAILED',
            retry_count = retry_count + 1,
            last_error = $1,
            processing_completed_at = now(),
            updated_at = now()
        where id = $2 and tenant_id = $3
        """
        message = f"{error_code}: {last_error}" if error_code else last_error
        async with pool.acquire() as conn:
            await conn.execute(query, message, document_id, tenant_id)

    async def get_document_for_processing(self, *, tenant_id: str, document_id: UUID) -> dict | None:
        pool = get_db_pool()
        query = """
        select id, tenant_id, user_id, file_name, mime_type, file_size, storage_bucket, storage_path, status
        from documents
        where id = $1 and tenant_id = $2
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, document_id, tenant_id)
            return dict(row) if row else None

    async def queue_reprocess(self, *, tenant_id: str, document_id: UUID) -> tuple[bool, int | None]:
        pool = get_db_pool()
        fetch_sql = """
        select status::text as status, version
        from documents
        where id = $1 and tenant_id = $2
        for update
        """
        update_sql = """
        update documents
        set status = 'QUEUED',
            version = version + 1,
            last_error = null,
            processing_started_at = null,
            processing_completed_at = null,
            updated_at = now()
        where id = $1 and tenant_id = $2
        returning version
        """
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(fetch_sql, document_id, tenant_id)
                if row is None:
                    return False, None
                if row["status"] in {"QUEUED", "PROCESSING"}:
                    return False, int(row["version"])
                updated = await conn.fetchrow(update_sql, document_id, tenant_id)
                return True, int(updated["version"]) if updated else None

    async def list_documents(self, *, tenant_id: str, limit: int = 50) -> list[DocumentListItem]:
        pool = get_db_pool()
        query = """
        select id, file_name, status::text as status, last_error,
               uploaded_at::text as uploaded_at,
               processing_completed_at::text as processing_completed_at
        from documents
        where tenant_id = $1
        order by created_at desc
        limit $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, tenant_id, limit)
        return [
            DocumentListItem(
                id=row["id"],
                file_name=row["file_name"],
                status=row["status"],
                last_error=row["last_error"],
                uploaded_at=row["uploaded_at"],
                processing_completed_at=row["processing_completed_at"],
            )
            for row in rows
        ]

    async def get_metadata(self, *, tenant_id: str, document_id: UUID) -> MetadataResponse | None:
        pool = get_db_pool()
        query = """
        select
          m.document_id,
          m.validation_status,
          m.review_status,
          m.last_edited_by::text as last_edited_by,
          m.dato::text as dato,
          m.parter,
          m.belop::float as belop,
          m.valuta,
          m.nokkelvilkar,
          m.extraction_model,
          m.extraction_prompt_version,
          m.is_manually_edited
        from document_metadata m
        join documents d on d.id = m.document_id
        where m.document_id = $1 and m.tenant_id = $2 and d.tenant_id = $2
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, document_id, tenant_id)
        if not row:
            return None
        return MetadataResponse(
            document_id=row["document_id"],
            validation_status=row["validation_status"],
            review_status=row["review_status"],
            last_edited_by=row["last_edited_by"],
            dato=row["dato"],
            parter=row["parter"],
            belop=row["belop"],
            valuta=row["valuta"],
            nokkelvilkar=row["nokkelvilkar"],
            extraction_model=row["extraction_model"],
            extraction_prompt_version=row["extraction_prompt_version"],
            is_manually_edited=row["is_manually_edited"],
        )

    async def update_metadata_manual(
        self,
        *,
        tenant_id: str,
        document_id: UUID,
        user_id: str,
        dato: str | None,
        parter: list[str] | None,
        belop: float | None,
        valuta: str | None,
        nokkelvilkar: list[str] | None,
        review_status: str,
    ) -> bool:
        pool = get_db_pool()
        query = """
        update document_metadata
        set dato = $1::date,
            parter = $2::jsonb,
            belop = $3,
            valuta = $4,
            nokkelvilkar = $5,
            review_status = $6,
            last_edited_by = $7::uuid,
            is_manually_edited = true,
            updated_at = now()
        where document_id = $8 and tenant_id = $9
        """
        parter_json = json.dumps(parter) if parter is not None else None
        async with pool.acquire() as conn:
            result = await conn.execute(
                query,
                dato,
                parter_json,
                belop,
                valuta,
                nokkelvilkar,
                review_status,
                user_id,
                document_id,
                tenant_id,
            )
        return result.endswith("1")

    async def semantic_search(self, *, tenant_id: str, query: str, limit: int) -> list[SearchResult]:
        _ = query
        pool = get_db_pool()
        sql = """
        select
          c.document_id,
          c.id as chunk_id,
          c.chunk_index,
          0.0::float as score,
          left(c.text_content, 400) as snippet,
          d.file_name
        from document_chunks c
        join documents d on d.id = c.document_id
        where c.tenant_id = $1
        order by c.created_at desc
        limit $2
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, tenant_id, limit)
        return [
            SearchResult(
                document_id=row["document_id"],
                chunk_id=row["chunk_id"],
                chunk_index=row["chunk_index"],
                score=row["score"],
                snippet=row["snippet"],
                file_name=row["file_name"],
            )
            for row in rows
        ]

    async def semantic_search_by_embedding(
        self, *, tenant_id: str, query_embedding: list[float], limit: int
    ) -> list[SearchResult]:
        pool = get_db_pool()
        sql = """
        select
          c.document_id,
          c.id as chunk_id,
          c.chunk_index,
          (1 - (c.embedding <=> $2::vector))::float as score,
          left(c.text_content, 400) as snippet,
          d.file_name
        from document_chunks c
        join documents d on d.id = c.document_id
        where c.tenant_id = $1
        order by c.embedding <=> $2::vector
        limit $3
        """
        vector = self._vector_literal(query_embedding)
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, tenant_id, vector, limit)
        return [
            SearchResult(
                document_id=row["document_id"],
                chunk_id=row["chunk_id"],
                chunk_index=row["chunk_index"],
                score=row["score"],
                snippet=row["snippet"],
                file_name=row["file_name"],
            )
            for row in rows
        ]

    async def semantic_search_rpc(
        self,
        *,
        tenant_id: str,
        query_embedding: list[float],
        limit: int,
        document_ids: list[UUID] | None = None,
    ) -> list[SearchResult]:
        pool = get_db_pool()
        vector = self._vector_literal(query_embedding)
        ids = document_ids if document_ids else None
        sql = """
        select
          r.document_id,
          r.chunk_id,
          r.chunk_index,
          r.score,
          r.snippet,
          r.file_name
        from public.search_document_chunks($1::vector, $2) r
        where ($3::uuid[] is null or r.document_id = any($3::uuid[]))
        order by r.score desc
        limit $2
        """
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("select set_config('request.jwt.claim.tenant_id', $1, true)", tenant_id)
                rows = await conn.fetch(sql, vector, limit, ids)
        return [
            SearchResult(
                document_id=row["document_id"],
                chunk_id=row["chunk_id"],
                chunk_index=row["chunk_index"],
                score=row["score"],
                snippet=row["snippet"],
                file_name=row["file_name"],
            )
            for row in rows
        ]

    async def upsert_metadata(
        self,
        *,
        tenant_id: str,
        document_id: UUID,
        dato: date | None,
        parter: list[str] | None,
        belop: Decimal | None,
        valuta: str | None,
        nokkelvilkar: list[str] | None,
    ) -> None:
        pool = get_db_pool()
        sql = """
        insert into document_metadata (
          document_id, tenant_id, dato, parter, belop, valuta, nokkelvilkar,
          validation_status, review_status, schema_version, extraction_model, extraction_prompt_version
        )
        values (
          $1, $2, $3, $4::jsonb, $5, $6, $7,
          'Validated', 'ai_extracted', 'v1', $8, $9
        )
        on conflict (document_id) do update set
          dato = excluded.dato,
          parter = excluded.parter,
          belop = excluded.belop,
          valuta = excluded.valuta,
          nokkelvilkar = excluded.nokkelvilkar,
          validation_status = excluded.validation_status,
          extraction_model = excluded.extraction_model,
          extraction_prompt_version = excluded.extraction_prompt_version,
          updated_at = now()
        """
        parter_json = json.dumps(parter) if parter is not None else None
        async with pool.acquire() as conn:
            await conn.execute(
                sql,
                document_id,
                tenant_id,
                dato,
                parter_json,
                belop,
                valuta,
                nokkelvilkar,
                settings.openai_metadata_model,
                settings.extraction_prompt_version,
            )

    async def replace_chunks(
        self,
        *,
        tenant_id: str,
        document_id: UUID,
        chunks: list[ChunkRow],
    ) -> None:
        pool = get_db_pool()
        delete_sql = "delete from document_chunks where tenant_id = $1 and document_id = $2"
        insert_sql = """
        insert into document_chunks (
          document_id, tenant_id, chunk_index, text_content, embedding, content_hash,
          token_count, page_from, page_to, embedding_model, chunking_version
        )
        values ($1, $2, $3, $4, $5::vector, $6, $7, $8, $9, $10, $11)
        """
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(delete_sql, tenant_id, document_id)
                for idx, chunk in enumerate(chunks):
                    await conn.execute(
                        insert_sql,
                        document_id,
                        tenant_id,
                        idx,
                        chunk.text,
                        self._vector_literal(chunk.embedding),
                        sha256(chunk.text.encode("utf-8")).hexdigest(),
                        chunk.token_count,
                        chunk.page_from,
                        chunk.page_to,
                        settings.openai_embedding_model,
                        settings.chunking_version,
                    )
