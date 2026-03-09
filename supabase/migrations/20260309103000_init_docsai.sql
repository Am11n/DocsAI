create extension if not exists vector;
create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'document_status') then
    create type document_status as enum (
      'PENDING',
      'UPLOADED',
      'QUEUED',
      'PROCESSING',
      'METADATA_EXTRACTED',
      'EMBEDDED',
      'COMPLETED',
      'FAILED'
    );
  end if;
end $$;

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  user_id uuid not null,
  file_name text not null,
  mime_type text not null,
  file_size bigint not null check (file_size > 0),
  storage_bucket text not null,
  storage_path text not null,
  status document_status not null default 'PENDING',
  retry_count int not null default 0,
  last_error text null,
  uploaded_at timestamptz null,
  processing_started_at timestamptz null,
  processing_completed_at timestamptz null,
  version int not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists document_metadata (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  tenant_id text not null,
  dato date null,
  parter jsonb null,
  belop numeric null,
  valuta text null,
  nokkelvilkar text[] null,
  validation_status text not null default 'Pending',
  review_status text not null default 'ai_extracted',
  last_edited_by uuid null,
  confidence_score numeric null,
  schema_version text not null default 'v1',
  extraction_model text null,
  extraction_prompt_version text null,
  is_manually_edited boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_id)
);

create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  tenant_id text not null,
  chunk_index int not null,
  text_content text not null,
  embedding vector(1536) not null,
  content_hash text null,
  token_count int null,
  page_from int null,
  page_to int null,
  embedding_model text not null default 'text-embedding-3-small',
  chunking_version text not null default 'recursive_char_v1',
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create table if not exists document_processing_events (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  tenant_id text not null,
  phase text not null,
  status text not null,
  message text null,
  payload jsonb null,
  created_at timestamptz not null default now()
);

create index if not exists idx_documents_tenant_status on documents (tenant_id, status);
create index if not exists idx_document_chunks_tenant_document on document_chunks (tenant_id, document_id);
create index if not exists idx_document_events_tenant_document on document_processing_events (tenant_id, document_id);
create index if not exists idx_document_chunks_embedding_hnsw
  on document_chunks using hnsw (embedding vector_cosine_ops);

create or replace function public.current_tenant_id()
returns text
language sql
stable
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.tenant_id', true), ''),
    nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'tenant_id', '')
  );
$$;

alter table documents enable row level security;
alter table document_metadata enable row level security;
alter table document_chunks enable row level security;
alter table document_processing_events enable row level security;

drop policy if exists tenant_isolation_documents on documents;
create policy tenant_isolation_documents
  on documents
  using (tenant_id = public.current_tenant_id())
  with check (tenant_id = public.current_tenant_id());

drop policy if exists tenant_isolation_document_metadata on document_metadata;
create policy tenant_isolation_document_metadata
  on document_metadata
  using (tenant_id = public.current_tenant_id())
  with check (tenant_id = public.current_tenant_id());

drop policy if exists tenant_isolation_document_chunks on document_chunks;
create policy tenant_isolation_document_chunks
  on document_chunks
  using (tenant_id = public.current_tenant_id())
  with check (tenant_id = public.current_tenant_id());

drop policy if exists tenant_isolation_document_processing_events on document_processing_events;
create policy tenant_isolation_document_processing_events
  on document_processing_events
  using (tenant_id = public.current_tenant_id())
  with check (tenant_id = public.current_tenant_id());

create or replace function public.search_document_chunks(
  query_embedding vector(1536),
  match_limit int default 5
)
returns table (
  document_id uuid,
  chunk_id uuid,
  chunk_index int,
  score float,
  snippet text,
  file_name text
)
language sql
stable
as $$
  select
    c.document_id,
    c.id as chunk_id,
    c.chunk_index,
    1 - (c.embedding <=> query_embedding) as score,
    left(c.text_content, 400) as snippet,
    d.file_name
  from document_chunks c
  join documents d on d.id = c.document_id
  where c.tenant_id = public.current_tenant_id()
  order by c.embedding <=> query_embedding
  limit greatest(match_limit, 1);
$$;
