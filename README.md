# DocsAI

MVP scaffold for AI-driven document automation with:

- `apps/web`: Next.js frontend
- `apps/api`: FastAPI + Celery worker
- `supabase/migrations`: PostgreSQL/pgvector schema

## Quick start

1. Copy `.env.example` to `.env` and fill values.
2. Start Redis:
   - `docker compose up -d redis`
3. Start API:
   - `cd apps/api`
   - `uvicorn app.main:app --reload --port 8000`
4. Start worker:
   - `cd apps/api`
   - `celery -A app.tasks.celery_app.celery_app worker --loglevel=info`
5. Start web:
   - `pnpm install`
   - `pnpm dev:web`

## Upload flow (MVP)

- `POST /upload/init`: validates ingest rules and returns signed upload URL.
- Upload file directly to Supabase Storage using returned URL.
- `POST /upload/confirm`: verifies object exists, sets `QUEUED`, and enqueues worker.
- Worker then runs: PDF text extraction -> metadata extraction -> chunk embeddings -> status `COMPLETED`.

## Search and chat

- `POST /search`: creates query embedding and runs pgvector similarity via `search_document_chunks` RPC.
- `POST /chat`: retrieves top-k chunks and generates grounded answer with `sources[]`.

## Metadata and status

- `GET /documents`: tenant-scoped document list with processing status.
- `GET /metadata/{id}`: fetch extracted metadata.
- `PATCH /metadata/{id}`: manual metadata override (`review_status`, `is_manually_edited`).

## Observability and safety

- `GET /metrics`: in-memory counters/timers for upload/search/chat/processing.
- Correlation ID supported through `x-correlation-id` request/response header.
- Simple rate limiter protects `/upload/init`, `/upload/confirm`, `/search`, `/chat`.

## Smoke test

- `API_BASE_URL=http://localhost:8000 infra/scripts/smoke-test.sh`
