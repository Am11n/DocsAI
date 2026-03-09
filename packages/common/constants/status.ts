export const DOCUMENT_STATUSES = [
  "PENDING",
  "UPLOADED",
  "QUEUED",
  "PROCESSING",
  "METADATA_EXTRACTED",
  "EMBEDDED",
  "COMPLETED",
  "FAILED",
] as const;

export type DocumentStatus = (typeof DOCUMENT_STATUSES)[number];
