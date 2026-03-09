export type HealthResponse = { status: "live" | "ready" };
export type DocumentStatus =
  | "PENDING"
  | "UPLOADED"
  | "QUEUED"
  | "PROCESSING"
  | "METADATA_EXTRACTED"
  | "EMBEDDED"
  | "COMPLETED"
  | "FAILED";

export interface UploadInitResponse {
  document_id: string;
  storage_path: string;
  upload_url: string;
  status: DocumentStatus;
}

export interface UploadConfirmResponse {
  document_id: string;
  status: DocumentStatus;
}

export interface DocumentListItem {
  id: string;
  file_name: string;
  status: DocumentStatus;
  last_error: string | null;
  uploaded_at: string | null;
  processing_completed_at: string | null;
}

export interface DocumentListResponse {
  documents: DocumentListItem[];
}

export interface SearchResult {
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
  snippet: string;
  file_name: string;
}

export interface SearchResponse {
  results: SearchResult[];
}

export interface ChatSource {
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
}

export interface MetadataResponse {
  document_id: string;
  validation_status: string;
  review_status: string;
  last_edited_by: string | null;
  dato: string | null;
  parter: string[] | null;
  belop: number | null;
  valuta: string | null;
  nokkelvilkar: string[] | null;
  extraction_model: string | null;
  extraction_prompt_version: string | null;
  is_manually_edited: boolean;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API request failed for ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function apiGetAuth<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`API request failed for ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function apiPostAuth<T>(path: string, token: string, body: object): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API request failed for ${path}: ${response.status} ${text}`);
  }
  return (await response.json()) as T;
}

async function apiPatchAuth<T>(path: string, token: string, body: object): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API request failed for ${path}: ${response.status} ${text}`);
  }
  return (await response.json()) as T;
}

export function getLiveHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/health/live");
}

export function getReadyHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/health/ready");
}

export function listDocuments(token: string): Promise<DocumentListResponse> {
  return apiGetAuth<DocumentListResponse>("/documents", token);
}

export function uploadInit(
  token: string,
  payload: { file_name: string; mime_type: string; file_size: number },
): Promise<UploadInitResponse> {
  return apiPostAuth<UploadInitResponse>("/upload/init", token, payload);
}

export async function uploadToSignedUrl(uploadUrl: string, file: File): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": file.type || "application/pdf" },
    body: file,
  });
  if (!response.ok) {
    throw new Error(`Signed URL upload failed: ${response.status}`);
  }
}

export function uploadConfirm(token: string, documentId: string): Promise<UploadConfirmResponse> {
  return apiPostAuth<UploadConfirmResponse>("/upload/confirm", token, { document_id: documentId });
}

export function semanticSearch(token: string, query: string, limit = 5): Promise<SearchResponse> {
  return apiPostAuth<SearchResponse>("/search", token, { query, limit });
}

export function ragChat(
  token: string,
  query: string,
  topK = 5,
  documentIds?: string[],
): Promise<ChatResponse> {
  return apiPostAuth<ChatResponse>("/chat", token, {
    query,
    top_k: topK,
    document_ids: documentIds,
  });
}

export function getMetadata(token: string, documentId: string): Promise<MetadataResponse> {
  return apiGetAuth<MetadataResponse>(`/metadata/${documentId}`, token);
}

export function patchMetadata(
  token: string,
  documentId: string,
  payload: {
    dato?: string | null;
    parter?: string[] | null;
    belop?: number | null;
    valuta?: string | null;
    nokkelvilkar?: string[] | null;
    review_status?: string;
  },
): Promise<MetadataResponse> {
  return apiPatchAuth<MetadataResponse>(`/metadata/${documentId}`, token, payload);
}
