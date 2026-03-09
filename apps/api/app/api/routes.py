from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.auth.dependencies import AuthContext, get_auth_context
from app.clients.openai_client import OpenAIClient
from app.clients.storage import StorageClient
from app.core.metrics import metrics
from app.core.settings import settings
from app.repositories.documents import DocumentRepository
from app.schemas.common import ErrorCode
from app.schemas.documents import (
    ChatRequest,
    ChatResponse,
    ChatSource,
    DocumentListResponse,
    DocumentStatus,
    MetadataResponse,
    MetadataUpdateRequest,
    ReprocessResponse,
    SearchRequest,
    SearchResponse,
    UploadConfirmRequest,
    UploadConfirmResponse,
    UploadInitRequest,
    UploadInitResponse,
    UploadRequest,
    UploadResponse,
)
from app.tasks.process_document import process_document
from app.utils.errors import FileTooLargeError, UnsupportedFileTypeError

router = APIRouter()
repo = DocumentRepository()
storage_client = StorageClient()
openai_client = OpenAIClient()


def _validate_ingest_rules(*, mime_type: str, file_size: int) -> None:
    if mime_type != "application/pdf":
        raise UnsupportedFileTypeError("Only PDF is supported in MVP")
    if file_size > settings.max_upload_size_mb * 1024 * 1024:
        raise FileTooLargeError(f"File exceeds max size ({settings.max_upload_size_mb} MB)")


def _build_storage_path(*, tenant_id: str, user_id: str, file_name: str) -> str:
    ext = Path(file_name).suffix or ".pdf"
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{tenant_id}/{user_id}/{timestamp}-{uuid4()}{ext}"


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/health/ready")
async def health_ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/metrics")
async def get_metrics() -> dict[str, object]:
    return metrics.snapshot()


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(auth: AuthContext = Depends(get_auth_context)) -> DocumentListResponse:
    documents = await repo.list_documents(tenant_id=auth.tenant_id, limit=100)
    return DocumentListResponse(documents=documents)


@router.post("/upload/init", response_model=UploadInitResponse)
async def upload_init(
    payload: UploadInitRequest,
    auth: AuthContext = Depends(get_auth_context),
    _x_correlation_id: str | None = Header(default=None),
) -> UploadInitResponse:
    metrics.inc("upload_init_total")
    try:
        _validate_ingest_rules(mime_type=payload.mime_type, file_size=payload.file_size)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.UNSUPPORTED_FILE_TYPE, "message": str(exc)},
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.UPLOAD_FAILED, "message": str(exc)},
        ) from exc

    storage_path = _build_storage_path(tenant_id=auth.tenant_id, user_id=auth.user_id, file_name=payload.file_name)
    document_id = await repo.create_document(
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        storage_path=storage_path,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
    )
    await repo.add_processing_event(
        tenant_id=auth.tenant_id,
        document_id=document_id,
        phase="UPLOAD",
        status="INIT",
        message="Signed upload URL created",
    )
    upload_url = await storage_client.create_signed_upload_url(storage_path)
    return UploadInitResponse(
        document_id=document_id,
        storage_path=storage_path,
        upload_url=upload_url,
        status=DocumentStatus.PENDING,
    )


@router.post("/upload/confirm", response_model=UploadConfirmResponse)
async def upload_confirm(
    payload: UploadConfirmRequest,
    auth: AuthContext = Depends(get_auth_context),
    x_correlation_id: str | None = Header(default=None),
) -> UploadConfirmResponse:
    metrics.inc("upload_confirm_total")
    doc = await repo.get_document_for_processing(tenant_id=auth.tenant_id, document_id=payload.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.DOCUMENT_NOT_FOUND, "message": "Document not found for tenant"},
        )

    exists = await storage_client.object_exists(doc["storage_path"])
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.UPLOAD_FAILED, "message": "Uploaded object not found in storage"},
        )

    await repo.confirm_upload(tenant_id=auth.tenant_id, document_id=payload.document_id)
    await repo.set_status(tenant_id=auth.tenant_id, document_id=payload.document_id, status=DocumentStatus.QUEUED)
    await repo.add_processing_event(
        tenant_id=auth.tenant_id,
        document_id=payload.document_id,
        phase="QUEUE",
        status="QUEUED",
        message="Document queued after upload confirmation",
        payload={"correlation_id": x_correlation_id},
    )
    process_document.delay(auth.tenant_id, str(payload.document_id), x_correlation_id)
    return UploadConfirmResponse(document_id=payload.document_id, status=DocumentStatus.QUEUED)


@router.post("/documents/{document_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_document(
    document_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    x_correlation_id: str | None = Header(default=None),
) -> ReprocessResponse:
    queued, version = await repo.queue_reprocess(tenant_id=auth.tenant_id, document_id=document_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.DOCUMENT_NOT_FOUND, "message": "Document not found for tenant"},
        )
    if not queued:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": ErrorCode.UPLOAD_FAILED, "message": "Document is already queued or processing"},
        )
    await repo.add_processing_event(
        tenant_id=auth.tenant_id,
        document_id=document_id,
        phase="REPROCESS",
        status="QUEUED",
        message="Document reprocessing requested",
        payload={"correlation_id": x_correlation_id, "version": version},
    )
    process_document.delay(auth.tenant_id, str(document_id), x_correlation_id)
    return ReprocessResponse(document_id=document_id, status=DocumentStatus.QUEUED, version=version)


@router.post("/upload", response_model=UploadResponse, deprecated=True)
async def upload_document_legacy(
    payload: UploadRequest,
    auth: AuthContext = Depends(get_auth_context),
) -> UploadResponse:
    try:
        _validate_ingest_rules(mime_type=payload.mime_type, file_size=payload.file_size)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCode.UPLOAD_FAILED, "message": str(exc)},
        ) from exc
    document_id = await repo.create_document(
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        storage_path=payload.storage_path,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
    )
    await repo.confirm_upload(tenant_id=auth.tenant_id, document_id=document_id)
    await repo.set_status(tenant_id=auth.tenant_id, document_id=document_id, status=DocumentStatus.QUEUED)
    return UploadResponse(document_id=document_id, status=DocumentStatus.QUEUED)


@router.post("/search", response_model=SearchResponse)
async def search(payload: SearchRequest, auth: AuthContext = Depends(get_auth_context)) -> SearchResponse:
    metrics.inc("search_total")
    with metrics.timer("search_ms"):
        query_embedding = await openai_client.embed_query(payload.query)
        results = await repo.semantic_search_rpc(
            tenant_id=auth.tenant_id,
            query_embedding=query_embedding,
            limit=payload.limit,
        )
    return SearchResponse(results=results)


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, auth: AuthContext = Depends(get_auth_context)) -> ChatResponse:
    metrics.inc("chat_total")
    with metrics.timer("chat_ms"):
        query_embedding = await openai_client.embed_query(payload.query)
        results = await repo.semantic_search_rpc(
            tenant_id=auth.tenant_id,
            query_embedding=query_embedding,
            limit=payload.top_k,
            document_ids=payload.document_ids,
        )
        contexts = [
            f"[chunk_id={r.chunk_id} document_id={r.document_id} score={r.score:.4f}] {r.snippet}" for r in results
        ]
        answer = await openai_client.answer_with_context(query=payload.query, contexts=contexts)
        sources = [
            ChatSource(
                document_id=r.document_id,
                chunk_id=r.chunk_id,
                chunk_index=r.chunk_index,
                score=r.score,
            )
            for r in results
        ]
    return ChatResponse(answer=answer, sources=sources)


@router.get("/metadata/{document_id}", response_model=MetadataResponse)
async def get_metadata(document_id: UUID, auth: AuthContext = Depends(get_auth_context)) -> MetadataResponse:
    metadata = await repo.get_metadata(tenant_id=auth.tenant_id, document_id=document_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.DOCUMENT_NOT_FOUND, "message": "Metadata not found for tenant document"},
        )
    return metadata


@router.patch("/metadata/{document_id}", response_model=MetadataResponse)
async def patch_metadata(
    document_id: UUID,
    payload: MetadataUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
) -> MetadataResponse:
    updated = await repo.update_metadata_manual(
        tenant_id=auth.tenant_id,
        document_id=document_id,
        user_id=auth.user_id,
        dato=payload.dato,
        parter=payload.parter,
        belop=payload.belop,
        valuta=payload.valuta,
        nokkelvilkar=payload.nokkelvilkar,
        review_status=payload.review_status,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.DOCUMENT_NOT_FOUND, "message": "Metadata row not found for document"},
        )
    metadata = await repo.get_metadata(tenant_id=auth.tenant_id, document_id=document_id)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.DOCUMENT_NOT_FOUND, "message": "Metadata not found after update"},
        )
    return metadata
