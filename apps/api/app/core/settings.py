from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    api_port: int = 8000
    max_upload_size_mb: int = 25

    redis_url: str
    supabase_db_url: str

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwks_url: str
    supabase_storage_bucket: str = "documents"
    signed_upload_ttl_seconds: int = 600

    openai_api_key: str
    openai_metadata_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    extraction_prompt_version: str = "v1"
    chunking_version: str = "recursive_char_v1"
    chunk_size_chars: int = 800
    chunk_overlap_chars: int = 100

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
