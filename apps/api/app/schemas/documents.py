from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    METADATA_EXTRACTED = "METADATA_EXTRACTED"
    EMBEDDED = "EMBEDDED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class UploadRequest(BaseModel):
    storage_path: str = Field(min_length=3)
    file_name: str = Field(min_length=1)
    mime_type: str
    file_size: int = Field(gt=0)


class UploadResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus


class UploadInitRequest(BaseModel):
    file_name: str = Field(min_length=1)
    mime_type: str
    file_size: int = Field(gt=0)


class UploadInitResponse(BaseModel):
    document_id: UUID
    storage_path: str
    upload_url: str
    status: DocumentStatus


class UploadConfirmRequest(BaseModel):
    document_id: UUID


class UploadConfirmResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    document_id: UUID
    chunk_id: UUID
    chunk_index: int
    score: float
    snippet: str
    file_name: str


class SearchResponse(BaseModel):
    results: list[SearchResult]


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    document_ids: list[UUID] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ChatSource(BaseModel):
    document_id: UUID
    chunk_id: UUID
    chunk_index: int
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]


class DocumentListItem(BaseModel):
    id: UUID
    file_name: str
    status: DocumentStatus
    last_error: str | None = None
    uploaded_at: str | None = None
    processing_completed_at: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class MetadataResponse(BaseModel):
    document_id: UUID
    validation_status: str
    review_status: str
    last_edited_by: str | None
    dato: str | None = None
    parter: list[str] | None = None
    belop: float | None = None
    valuta: str | None = None
    nokkelvilkar: list[str] | None = None
    extraction_model: str | None = None
    extraction_prompt_version: str | None = None
    is_manually_edited: bool


class MetadataUpdateRequest(BaseModel):
    dato: str | None = None
    parter: list[str] | None = None
    belop: float | None = None
    valuta: str | None = None
    nokkelvilkar: list[str] | None = None
    review_status: str = Field(default="user_overridden")
