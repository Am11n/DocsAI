# Security and compliance baseline (MVP)

- All OpenAI calls are server-side only.
- Raw document text is never sent from API to client except short snippets in search results.
- Signed upload URLs must be short-lived (`SIGNED_UPLOAD_TTL_SECONDS`).
- Upload/search/chat endpoints are rate-limited.
- File MIME and max size are validated server-side.
- Metadata edits are persisted with `last_edited_by` and `is_manually_edited` for auditability.
- Secrets remain server-side in environment variables only.

## Data governance

- Keep all documents in configured Supabase region.
- Maintain document deletion flow (document row deletion cascades chunks/metadata/events).
- Retention period should be configured per environment before production rollout.
