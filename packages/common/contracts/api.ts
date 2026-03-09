export type ErrorCode =
  | "UPLOAD_FAILED"
  | "UNSUPPORTED_FILE_TYPE"
  | "TEXT_EXTRACTION_FAILED"
  | "METADATA_VALIDATION_FAILED"
  | "EMBEDDING_FAILED"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "DOCUMENT_NOT_FOUND"
  | "NEEDS_OCR";

export interface ApiError {
  code: ErrorCode;
  message: string;
}
