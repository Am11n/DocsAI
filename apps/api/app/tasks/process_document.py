import asyncio
from uuid import UUID

import fitz
import structlog
from pydantic import ValidationError

from app.clients.openai_client import OpenAIClient
from app.clients.storage import StorageClient
from app.core.db import init_db_pool
from app.core.settings import settings
from app.repositories.documents import DocumentRepository
from app.schemas.common import ErrorCode
from app.schemas.documents import DocumentStatus
from app.services.chunking import split_pages_into_chunks
from app.tasks.celery_app import celery_app
from app.utils.errors import (
    DocumentNotFoundError,
    EmbeddingGenerationError,
    MetadataExtractionError,
    NeedsOCRError,
    PasswordProtectedPDFError,
)

logger = structlog.get_logger(__name__)
repo = DocumentRepository()
storage_client = StorageClient()
openai_client = OpenAIClient()


def _extract_page_texts_from_pdf(data: bytes) -> list[tuple[int, str]]:
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise PasswordProtectedPDFError("PDF is password protected")
        page_texts: list[tuple[int, str]] = []
        for index, page in enumerate(doc):
            page_texts.append((index + 1, page.get_text("text")))
        full_text = "\n".join(text for _, text in page_texts).strip()
        if not full_text:
            raise NeedsOCRError("PDF has no extractable text layer")
        return page_texts


async def _process_document_async(tenant_id: str, doc_uuid: UUID, correlation_id: str | None) -> None:
    await repo.set_status(tenant_id=tenant_id, document_id=doc_uuid, status=DocumentStatus.PROCESSING)
    await repo.add_processing_event(
        tenant_id=tenant_id,
        document_id=doc_uuid,
        phase="PROCESSING",
        status=DocumentStatus.PROCESSING.value,
        message="Worker started document processing",
        payload={"correlation_id": correlation_id},
    )

    document = await repo.get_document_for_processing(tenant_id=tenant_id, document_id=doc_uuid)
    if document is None:
        raise DocumentNotFoundError("Document not found for processing")

    content = await storage_client.download_object(document["storage_path"])
    page_texts = _extract_page_texts_from_pdf(content)
    full_text = "\n".join(text for _, text in page_texts)

    try:
        metadata = await openai_client.extract_metadata(full_text)
    except ValidationError as exc:
        raise MetadataExtractionError(f"Invalid metadata JSON schema: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise MetadataExtractionError(f"Metadata extraction failed: {exc}") from exc

    await repo.upsert_metadata(
        tenant_id=tenant_id,
        document_id=doc_uuid,
        dato=metadata.dato,
        parter=metadata.parter,
        belop=metadata.belop,
        valuta=metadata.valuta,
        nokkelvilkar=metadata.nokkelvilkar,
    )

    await repo.set_status(tenant_id=tenant_id, document_id=doc_uuid, status=DocumentStatus.METADATA_EXTRACTED)
    await repo.add_processing_event(
        tenant_id=tenant_id,
        document_id=doc_uuid,
        phase="METADATA",
        status=DocumentStatus.METADATA_EXTRACTED.value,
        message="Metadata extracted and validated",
    )

    chunk_candidates = split_pages_into_chunks(
        page_texts,
        chunk_size=settings.chunk_size_chars,
        overlap=settings.chunk_overlap_chars,
    )
    try:
        embeddings = await openai_client.embed_texts([chunk.text for chunk in chunk_candidates])
    except Exception as exc:  # noqa: BLE001
        raise EmbeddingGenerationError(f"Embedding generation failed: {exc}") from exc

    chunk_rows = [
        DocumentRepository.ChunkRow(
            text=chunk.text,
            embedding=embedding,
            page_from=chunk.page_from,
            page_to=chunk.page_to,
            token_count=chunk.token_count,
        )
        for chunk, embedding in zip(chunk_candidates, embeddings, strict=True)
    ]
    await repo.replace_chunks(tenant_id=tenant_id, document_id=doc_uuid, chunks=chunk_rows)

    await repo.set_status(tenant_id=tenant_id, document_id=doc_uuid, status=DocumentStatus.EMBEDDED)
    await repo.add_processing_event(
        tenant_id=tenant_id,
        document_id=doc_uuid,
        phase="EMBEDDING",
        status=DocumentStatus.EMBEDDED.value,
        message="Document chunks embedded and stored",
        payload={"chunk_count": len(chunk_rows)},
    )
    await repo.set_status(tenant_id=tenant_id, document_id=doc_uuid, status=DocumentStatus.COMPLETED)
    await repo.add_processing_event(
        tenant_id=tenant_id,
        document_id=doc_uuid,
        phase="COMPLETE",
        status=DocumentStatus.COMPLETED.value,
        message="Document processing completed",
    )


def _map_error_code(exc: Exception) -> ErrorCode:
    if isinstance(exc, NeedsOCRError):
        return ErrorCode.NEEDS_OCR
    if isinstance(exc, PasswordProtectedPDFError):
        return ErrorCode.TEXT_EXTRACTION_FAILED
    if isinstance(exc, MetadataExtractionError):
        return ErrorCode.METADATA_VALIDATION_FAILED
    if isinstance(exc, EmbeddingGenerationError):
        return ErrorCode.EMBEDDING_FAILED
    if isinstance(exc, DocumentNotFoundError):
        return ErrorCode.DOCUMENT_NOT_FOUND
    return ErrorCode.UPLOAD_FAILED


@celery_app.task(bind=True, max_retries=5, retry_backoff=True)
def process_document(self, tenant_id: str, document_id: str, correlation_id: str | None = None) -> None:
    doc_uuid = UUID(document_id)
    asyncio.run(init_db_pool())
    logger.info(
        "document_processing_started",
        tenant_id=tenant_id,
        document_id=str(doc_uuid),
        correlation_id=correlation_id,
        status=DocumentStatus.PROCESSING.value,
    )
    try:
        asyncio.run(_process_document_async(tenant_id, doc_uuid, correlation_id))
        logger.info(
            "document_processing_completed",
            tenant_id=tenant_id,
            document_id=str(doc_uuid),
            correlation_id=correlation_id,
            status=DocumentStatus.COMPLETED.value,
        )
    except (
        NeedsOCRError,
        PasswordProtectedPDFError,
        DocumentNotFoundError,
        MetadataExtractionError,
        EmbeddingGenerationError,
    ) as exc:
        code = _map_error_code(exc)
        asyncio.run(
            repo.set_failed(
                tenant_id=tenant_id,
                document_id=doc_uuid,
                last_error=str(exc),
                error_code=code.value,
            )
        )
        asyncio.run(
            repo.add_processing_event(
                tenant_id=tenant_id,
                document_id=doc_uuid,
                phase="FAILED",
                status=DocumentStatus.FAILED.value,
                message=str(exc),
                payload={"correlation_id": correlation_id, "error_code": code.value},
            )
        )
        logger.warning(
            "document_processing_failed_non_retryable",
            tenant_id=tenant_id,
            document_id=str(doc_uuid),
            correlation_id=correlation_id,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        code = _map_error_code(exc)
        asyncio.run(
            repo.set_failed(
                tenant_id=tenant_id,
                document_id=doc_uuid,
                last_error=str(exc),
                error_code=code.value,
            )
        )
        asyncio.run(
            repo.add_processing_event(
                tenant_id=tenant_id,
                document_id=doc_uuid,
                phase="FAILED",
                status=DocumentStatus.FAILED.value,
                message=str(exc),
                payload={"correlation_id": correlation_id, "retry": True, "error_code": code.value},
            )
        )
        logger.exception(
            "document_processing_failed_retryable",
            tenant_id=tenant_id,
            document_id=str(doc_uuid),
            correlation_id=correlation_id,
            error=str(exc),
        )
        raise
